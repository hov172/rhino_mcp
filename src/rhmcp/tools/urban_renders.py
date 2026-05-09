"""AI render pipeline using fal.ai FLUX.1 ControlNet."""
from __future__ import annotations

import base64
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_current_renders: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FAL_CANNY_URL = "https://fal.run/fal-ai/flux-dev-canny"
_FAL_FLUX_URL = "https://fal.run/fal-ai/flux-dev"

_VIEW_SUFFIXES: dict[str, str] = {
    "Perspective": "eye-level street view, urban context, pedestrians, daytime, photorealistic",
    "Top": "aerial plan view, rooftop gardens, surrounding streets visible, photorealistic",
    "Front": "elevation view, street level, symmetrical facade, architectural quality",
    "Back": "rear elevation, building profile, clear sky background",
    "Right": "side elevation, building profile, clear sky background",
    "Left": "side elevation, building profile, clear sky background",
}
_DEFAULT_SUFFIX = "architectural exterior, photorealistic"
_DEFAULT_NEGATIVE = "cartoon, sketch, low quality, blurry, distorted, interior"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_named_view(view_name: str) -> str:
    """Activate the named Rhino viewport and return a base64 PNG string."""
    rhino.plugin_result("set_active_view", {"view_name": view_name})
    result = rhino.plugin_result("capture_viewport", {"path": None, "width": 1200, "height": 900})
    if result.get("ok"):
        b64 = result.get("result", {}).get("image_data", "")
        if b64:
            return b64
    return ""


def _fal_img2img(
    image_b64: str,
    prompt: str,
    negative_prompt: str,
    strength: float,
    seed: int | None,
    url: str = _FAL_CANNY_URL,
) -> tuple[str, str, int]:
    """
    Submit base64 image to fal.ai for img2img render.
    Returns (rendered_b64, fal_request_id, seed_used).
    Raises on HTTP/network error (caller handles retry).
    """
    fal_key = os.environ.get("FAL_KEY", "")
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "image_url": f"data:image/png;base64,{image_b64}",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "strength": strength,
        "num_images": 1,
    }
    if seed is not None:
        payload["seed"] = seed

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        img_url = data["images"][0]["url"]
        request_id = data.get("request_id", "")
        seed_used = int(data.get("seed") or seed or 0)
        img_resp = client.get(img_url)
        img_resp.raise_for_status()
        rendered_b64 = base64.b64encode(img_resp.content).decode()

    return rendered_b64, request_id, seed_used


def _fal_text2img(prompt: str, seed: int | None) -> tuple[str, str, int]:
    """Text-to-image via fal-ai/flux-dev. Returns (b64, request_id, seed)."""
    fal_key = os.environ.get("FAL_KEY", "")
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {"prompt": prompt, "num_images": 1}
    if seed is not None:
        payload["seed"] = seed

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(_FAL_FLUX_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        img_url = data["images"][0]["url"]
        request_id = data.get("request_id", "")
        seed_used = int(data.get("seed") or seed or 0)
        img_resp = client.get(img_url)
        img_resp.raise_for_status()
        return base64.b64encode(img_resp.content).decode(), request_id, seed_used


def reset() -> None:
    """Reset module state. Called by urban_clear_massing."""
    global _current_renders
    _current_renders = {}


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Render Urban Views", destructiveHint=False))
    def urban_render_views(
        views: list[str] | None = None,
        strength: float = 0.65,
        style_override: str | None = None,
        seed: int | None = None,
    ) -> list[dict[str, object]]:
        """
        Capture Rhino viewports and render them with AI (fal.ai FLUX.1 ControlNet).
        Returns a list of RenderResult dicts — one per view.
        Falls back to raw Rhino captures if fal.ai is unavailable.
        """
        from rhmcp.tools.urban_design_language import _current_design_language

        if views is None:
            views = ["Perspective", "Top", "Front", "Right"]

        base_prompt = (
            _current_design_language.get("diffusion_prompt", "architectural render, photorealistic")
            if _current_design_language
            else "architectural render, photorealistic, 8k"
        )
        negative = (
            _current_design_language.get("negative_prompt", _DEFAULT_NEGATIVE)
            if _current_design_language
            else _DEFAULT_NEGATIVE
        )

        if not os.environ.get("FAL_KEY"):
            return [{"view": v, "ok": False, "error": "FAL_KEY not set",
                     "original_b64": "", "rendered_b64": "", "prompt_used": "",
                     "seed": 0, "model": "", "fal_request_id": ""} for v in views]

        results = []
        for view in views:
            original_b64 = _capture_named_view(view)
            if not original_b64:
                results.append({
                    "view": view, "ok": False, "error": f"failed to capture viewport '{view}'",
                    "original_b64": "", "rendered_b64": "", "prompt_used": "",
                    "negative_prompt": negative, "seed": seed or 0,
                    "strength": strength, "model": "", "fal_request_id": "",
                })
                continue
            suffix = _VIEW_SUFFIXES.get(view, _DEFAULT_SUFFIX)
            prompt = f"{base_prompt}, {suffix}"
            if style_override:
                prompt = f"{prompt}, {style_override}"

            rendered_b64 = ""
            request_id = ""
            seed_used = seed or 0
            error = None
            ok = True

            try:
                rendered_b64, request_id, seed_used = _fal_img2img(
                    original_b64, prompt, negative, strength, seed
                )
            except Exception:
                try:
                    rendered_b64, request_id, seed_used = _fal_img2img(
                        original_b64, prompt, negative, max(0.1, strength - 0.1), seed
                    )
                except Exception as second_err:
                    ok = False
                    error = str(second_err)

            result: dict[str, Any] = {
                "view": view,
                "ok": ok,
                "original_b64": original_b64,
                "rendered_b64": rendered_b64,
                "prompt_used": prompt,
                "negative_prompt": negative,
                "seed": seed_used,
                "strength": strength,
                "model": "fal-ai/flux-dev-canny",
                "fal_request_id": request_id,
            }
            if error:
                result["error"] = error
            _current_renders[view] = result
            results.append(result)

        return results

    @mcp.tool(annotations=ToolAnnotations(title="Render Style Preview", readOnlyHint=True))
    def urban_render_style_preview(
        style_prompt: str,
        seed: int | None = None,
    ) -> dict[str, object]:
        """
        Quick text-to-image style preview via fal.ai FLUX.1 (no Rhino model needed).
        Use to explore design directions before generating the full massing.
        """
        if not os.environ.get("FAL_KEY"):
            return {"ok": False, "error": "FAL_KEY not set"}
        try:
            image_b64, request_id, seed_used = _fal_text2img(style_prompt, seed)
            return {"ok": True, "image_b64": image_b64, "prompt_used": style_prompt,
                    "seed": seed_used, "fal_request_id": request_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @mcp.tool(annotations=ToolAnnotations(title="Get Current Renders", readOnlyHint=True))
    def urban_get_renders() -> dict[str, object]:
        """Return all AI renders produced this session, keyed by view name."""
        return dict(_current_renders)
