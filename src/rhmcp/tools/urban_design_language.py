"""Urban design language generation via Claude API."""
from __future__ import annotations
from rhmcp.tools_helpers.workflow_state import current as state

import json
import os
from typing import Any

import anthropic
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# State is stored in the current actor/project/instance scope
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ZERO: dict[str, Any] = {
    "style_name": "",
    "facade_vocabulary": [],
    "material_palette": [],
    "colour_story": {"primary": "#7DD3FC", "secondary": "#1E293B", "accent": "#F1F5F9"},
    "landscape_character": "",
    "diffusion_prompt": "",
    "negative_prompt": "cartoon, sketch, low quality, blurry, distorted, oversaturated",
    "executive_summary": "",
}

_SCHEMA_KEYS = set(_ZERO.keys())

_CLIMATE_SEEDS: dict[str, str] = {
    "London": "Northern European, temperate, red brick tradition, Victorian and contemporary mix",
    "New York": "North American urban, diverse, glass and steel, brownstone tradition",
    "Dubai": "Middle Eastern, desert climate, modern luxury, glass facades, shading devices",
    "Tokyo": "Japanese urban, compact, precision detailing, contemporary",
    "Sydney": "Australian coastal, light-filled, timber and concrete, subtropical",
    "Singapore": "Tropical, greenery integration, shade canopies, contemporary Southeast Asian",
    "Berlin": "Central European, Bauhaus influence, brick and render, modernist",
}

_FAR_CHARACTER: dict[str, str] = {
    "low": "intimate low-rise neighbourhood scale, human-proportioned, fine-grained",
    "mid": "mid-rise urban character, active street edges, balcony culture",
    "high": "high-rise bold statement, iconic silhouette, panoramic views",
}

_TYPOLOGY_RHYTHM: dict[str, str] = {
    "tower": "singular iconic tower form, strong vertical expression",
    "podium_tower": "podium base activates street, tower rises as focal point",
    "courtyard": "enclosed courtyard character, inward-facing, sheltered outdoor space",
    "perimeter_block": "solid urban block, continuous street wall, private rear garden",
    "street_grid": "urban grain, multiple plots, varied streetscape",
}

_SYSTEM_PROMPT = (
    "You are an expert architectural design consultant. "
    "Generate a design language for a building project based on the brief. "
    "Return ONLY valid JSON matching this exact schema — no markdown, no explanation:\n"
    '{\n'
    '  "style_name": "3-5 word name e.g. Contemporary Nordic Mixed-Use",\n'
    '  "facade_vocabulary": ["descriptor1", ..., "descriptor6"],\n'
    '  "material_palette": [{"name": "...", "hex": "#RRGGBB", "role": "..."}, ...],\n'
    '  "colour_story": {"primary": "#RRGGBB", "secondary": "#RRGGBB", "accent": "#RRGGBB"},\n'
    '  "landscape_character": "one sentence ground-level description",\n'
    '  "diffusion_prompt": "optimised FLUX.1 architectural render prompt",\n'
    '  "negative_prompt": "SD negative prompt",\n'
    '  "executive_summary": "2-3 sentences describing design direction for a client"\n'
    "}"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_user_prompt(
    brief: str, typology: str, far: float, climate_zone: str, style_hints: str | None
) -> str:
    climate = _CLIMATE_SEEDS.get(climate_zone, climate_zone)
    far_char = (
        _FAR_CHARACTER["high"] if far > 4.5
        else _FAR_CHARACTER["mid"] if far > 2.0
        else _FAR_CHARACTER["low"]
    )
    rhythm = _TYPOLOGY_RHYTHM.get(typology, typology)
    hints = f"\nStyle hints: {style_hints}" if style_hints else ""
    return (
        f"Site brief: {brief}\n"
        f"Typology: {typology} — {rhythm}\n"
        f"Target FAR: {far} — {far_char}\n"
        f"Climate/location: {climate_zone} — {climate}{hints}\n\n"
        "Generate a cohesive design language for this project."
    )


def _build_diffusion_prompt(dl: dict[str, Any]) -> str:
    vocab = ", ".join(str(v) for v in dl.get("facade_vocabulary", [])[:4])
    materials = " ".join(
        m["name"] for m in dl.get("material_palette", [])[:2] if isinstance(m, dict)
    )
    style = dl.get("style_name", "architectural")
    return (
        f"architectural render, {style}, {vocab}, {materials}, "
        "photorealistic, 8k, golden hour, urban context"
    ).strip(", ")


def reset() -> None:
    """Reset module state. Called by urban_clear_massing."""
    state().current_design_language = None


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Generate Design Language", destructiveHint=False))
    def urban_generate_design_language(
        brief: str,
        typology: str,
        far: float,
        climate_zone: str,
        style_hints: str | None = None,
    ) -> dict[str, object]:
        """Generate an AI-driven design language (style, materials, colour palette,
        diffusion prompt) from the site brief using Claude.

        Returns a DesignLanguage dict with style_name,..."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"ok": False, "error": "ANTHROPIC_API_KEY not set", **_ZERO}

        client = anthropic.Anthropic(api_key=api_key)
        user_prompt = _build_user_prompt(brief, typology, far, climate_zone, style_hints)

        def _call() -> dict[str, Any]:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return json.loads(msg.content[0].text)

        try:
            result = _call()
        except json.JSONDecodeError:
            try:
                result = _call()
            except Exception as exc:
                return {"ok": False, "error": str(exc), **_ZERO}
        except Exception as exc:
            return {"ok": False, "error": str(exc), **_ZERO}

        state().current_design_language = result
        return {"ok": True, **result}

    @mcp.tool(annotations=ToolAnnotations(title="Update Design Language Field", destructiveHint=False))
    def urban_update_design_language(
        field: str,
        value: str | list | dict,
    ) -> dict[str, object]:
        """Patch a single field of the current design language.
        Re-derives diffusion_prompt if style_name, facade_vocabulary,
        material_palette, or colour_story changes.
        For structured..."""
        if state().current_design_language is None:
            return {"ok": False, "error": "No design language set. Call urban_generate_design_language first."}
        if field not in _SCHEMA_KEYS:
            return {"ok": False, "error": f"Unknown field: {field!r}. Valid: {sorted(_SCHEMA_KEYS)}"}
        state().current_design_language[field] = value
        updated_prompt = field in ("material_palette", "facade_vocabulary", "colour_story", "style_name")
        if updated_prompt:
            state().current_design_language["diffusion_prompt"] = _build_diffusion_prompt(state().current_design_language)
        return {"ok": True, "field": field, "value": value, "diffusion_prompt_updated": updated_prompt}

    @mcp.tool(annotations=ToolAnnotations(title="Get Design Language", readOnlyHint=True))
    def urban_get_design_language() -> dict[str, object]:
        """
        Return the current session design language, or zero-safe defaults if none
        has been generated yet.
        """
        if state().current_design_language is None:
            return {"ok": True, "set": False, **_ZERO}
        return {"ok": True, "set": True, **state().current_design_language}
