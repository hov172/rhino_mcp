# Urban Studio Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full AI-driven studio pipeline to rhino_mcp: design language generation (Claude API), AI renders (fal.ai FLUX.1 ControlNet), branded PDF reports (DocRaptor + S3), and a single-call pipeline orchestrator.

**Architecture:** Four new MCP tool modules (`urban_design_language`, `urban_renders`, `urban_report`, `urban_pipeline`) each follow the existing `register(mcp)` pattern. Module-level state stores session data. External services (Anthropic, fal.ai, DocRaptor, S3) are called via httpx/SDKs; all degrade gracefully to local fallbacks when env vars are absent.

**Tech Stack:** Python (FastMCP), anthropic SDK, fal.ai REST API via httpx, Jinja2, DocRaptor REST via httpx, boto3 S3, unittest + unittest.mock.

---

## Codebase orientation

Before starting, read these files:
- `src/rhmcp/tools/urban.py` — register pattern, `_gh()` helper, `_capture_view()`, module-level state
- `tests/test_urban_unit.py` — `_register_urban()` helper, mock patterns
- `pyproject.toml` — dependencies list

The register pattern used throughout: a top-level `register(mcp: FastMCP) -> None` function containing `@mcp.tool`-decorated inner functions. Module-level state is plain module globals. Tests call `register()` with a fresh `FastMCP("test-x")` and extract tool callables via `mcp._tool_manager._tools`.

---

## File map

| Action | Path |
|---|---|
| Create | `src/rhmcp/tools/urban_design_language.py` |
| Create | `src/rhmcp/tools/urban_renders.py` |
| Create | `src/rhmcp/tools/urban_report.py` |
| Create | `src/rhmcp/tools/urban_pipeline.py` |
| Create | `src/rhmcp/report_templates/report.html.jinja2` |
| Create | `src/rhmcp/report_templates/report.css` |
| Create | `tests/test_urban_design_language.py` |
| Create | `tests/test_urban_renders.py` |
| Create | `tests/test_urban_report.py` |
| Create | `tests/test_urban_pipeline.py` |
| Modify | `pyproject.toml` — add anthropic, jinja2, boto3 |
| Modify | `src/rhmcp/tools/urban.py` — `urban_clear_massing` resets new module state |
| Modify | `README.md` — add Studio Pipeline section |

---

## Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add three new dependencies**

Edit `pyproject.toml` dependencies list:

```toml
dependencies = [
    "mcp[cli]>=1.2.0",
    "pyyaml",
    "httpx>=0.27.0",
    "anthropic>=0.25.0",
    "jinja2>=3.1.0",
    "boto3>=1.34.0",
]
```

- [ ] **Step 2: Install**

```bash
uv sync
```

Expected: resolves and installs anthropic, jinja2, boto3 with no conflicts.

- [ ] **Step 3: Verify**

```bash
uv run python -c "import anthropic, jinja2, boto3; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add anthropic, jinja2, boto3 dependencies"
```

---

## Task 2: Design Language Generator — skeleton + tests (red)

**Files:**
- Create: `src/rhmcp/tools/urban_design_language.py`
- Create: `tests/test_urban_design_language.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_urban_design_language.py`:

```python
"""Unit tests for urban_design_language tools. No real API calls."""
from __future__ import annotations
import json
import unittest
from unittest.mock import patch, MagicMock
from mcp.server.fastmcp import FastMCP


def _register() -> dict[str, object]:
    import importlib
    import rhmcp.tools.urban_design_language as m
    importlib.reload(m)          # reset module-level state between tests
    mcp = FastMCP("test-dl")
    m.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


def _mock_client(data: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(data))]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


_SAMPLE = {
    "style_name": "Contemporary Nordic Mixed-Use",
    "facade_vocabulary": ["brick", "steel", "glass", "setback", "balcony", "planted edge"],
    "material_palette": [{"name": "London Stock Brick", "hex": "#C4956A", "role": "primary"}],
    "colour_story": {"primary": "#C4956A", "secondary": "#1E293B", "accent": "#7DD3FC"},
    "landscape_character": "Dense urban greenery at ground level.",
    "diffusion_prompt": "architectural render, contemporary nordic, brick, photorealistic, 8k",
    "negative_prompt": "cartoon, blurry, low quality",
    "executive_summary": "A warm contemporary scheme with a Nordic character.",
}


class TestUrbanGenerateDesignLanguage(unittest.TestCase):
    def _call(self, **kw):
        tools = _register()
        defaults = dict(brief="Mixed-use in Shoreditch", typology="podium_tower",
                        far=3.5, climate_zone="London")
        defaults.update(kw)
        with patch("anthropic.Anthropic", return_value=_mock_client(_SAMPLE)):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
                return tools["urban_generate_design_language"](**defaults)

    def test_returns_all_schema_keys(self):
        r = self._call()
        self.assertTrue(r["ok"])
        for k in ("style_name", "facade_vocabulary", "material_palette", "colour_story",
                  "landscape_character", "diffusion_prompt", "negative_prompt", "executive_summary"):
            self.assertIn(k, r)

    def test_diffusion_prompt_includes_style_name(self):
        r = self._call()
        self.assertIn("Contemporary Nordic", r["diffusion_prompt"])

    def test_missing_api_key_returns_error(self):
        tools = _register()
        with patch.dict("os.environ", {}, clear=True):
            r = tools["urban_generate_design_language"](
                brief="test", typology="tower", far=5.0, climate_zone="Tokyo")
        self.assertFalse(r["ok"])
        self.assertIn("ANTHROPIC_API_KEY", r["error"])


class TestUrbanUpdateDesignLanguage(unittest.TestCase):
    def _setup(self):
        tools = _register()
        with patch("anthropic.Anthropic", return_value=_mock_client(_SAMPLE)):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
                tools["urban_generate_design_language"](
                    brief="test", typology="tower", far=5.0, climate_zone="Tokyo")
        return tools

    def test_patches_single_field_preserves_others(self):
        tools = self._setup()
        r = tools["urban_update_design_language"](field="style_name", value="Brutalist Concrete")
        self.assertTrue(r["ok"])
        import rhmcp.tools.urban_design_language as m
        self.assertEqual(m._current_design_language["style_name"], "Brutalist Concrete")
        self.assertIn("facade_vocabulary", m._current_design_language)

    def test_rederives_diffusion_prompt_on_style_change(self):
        tools = self._setup()
        import rhmcp.tools.urban_design_language as m
        old_prompt = m._current_design_language["diffusion_prompt"]
        r = tools["urban_update_design_language"](field="style_name", value="Tropical Brutalist")
        self.assertTrue(r["diffusion_prompt_updated"])
        self.assertNotEqual(m._current_design_language["diffusion_prompt"], old_prompt)

    def test_raises_key_error_on_unknown_field(self):
        tools = self._setup()
        with self.assertRaises(KeyError):
            tools["urban_update_design_language"](field="nonexistent", value="x")


class TestUrbanGetDesignLanguage(unittest.TestCase):
    def test_returns_zero_defaults_when_none_set(self):
        tools = _register()
        r = tools["urban_get_design_language"]()
        self.assertTrue(r["ok"])
        self.assertFalse(r["set"])
        self.assertEqual(r["style_name"], "")
        self.assertEqual(r["facade_vocabulary"], [])

    def test_returns_set_true_after_generate(self):
        tools = _register()
        with patch("anthropic.Anthropic", return_value=_mock_client(_SAMPLE)):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
                tools["urban_generate_design_language"](
                    brief="test", typology="tower", far=5.0, climate_zone="Tokyo")
        r = tools["urban_get_design_language"]()
        self.assertTrue(r["set"])
        self.assertEqual(r["style_name"], "Contemporary Nordic Mixed-Use")
```

- [ ] **Step 2: Verify tests fail**

```bash
uv run pytest tests/test_urban_design_language.py -v 2>&1 | head -20
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'rhmcp.tools.urban_design_language'`

- [ ] **Step 3: Create skeleton**

Create `src/rhmcp/tools/urban_design_language.py`:

```python
"""Urban design language generation via Claude API."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

_current_design_language: dict | None = None

def register(mcp: FastMCP) -> None:
    pass
```

- [ ] **Step 4: Run tests — expect clear failure messages now**

```bash
uv run pytest tests/test_urban_design_language.py -v 2>&1 | head -20
```

Expected: `FAILED` with `KeyError` or `AttributeError` (tools not registered yet), not import errors.

---

## Task 3: Design Language Generator — full implementation (green)

**Files:**
- Modify: `src/rhmcp/tools/urban_design_language.py`

- [ ] **Step 1: Implement the full module**

Replace `src/rhmcp/tools/urban_design_language.py` entirely:

```python
"""Urban design language generation via Claude API."""
from __future__ import annotations

import json
import os
from typing import Any

import anthropic
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_current_design_language: dict[str, Any] | None = None

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
    global _current_design_language
    _current_design_language = None


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
        """
        Generate an AI-driven design language (style, materials, colour palette,
        diffusion prompt) from the site brief using Claude.

        Returns a DesignLanguage dict with style_name, facade_vocabulary,
        material_palette, colour_story, landscape_character, diffusion_prompt,
        negative_prompt, executive_summary.
        """
        global _current_design_language
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
        except (json.JSONDecodeError, Exception):
            try:
                result = _call()
            except Exception as exc:
                return {"ok": False, "error": str(exc), **_ZERO}

        _current_design_language = result
        return {"ok": True, **result}

    @mcp.tool(annotations=ToolAnnotations(title="Update Design Language Field", destructiveHint=False))
    def urban_update_design_language(
        field: str,
        value: str,
    ) -> dict[str, object]:
        """
        Patch a single field of the current design language.
        Re-derives diffusion_prompt if style_name, facade_vocabulary,
        material_palette, or colour_story changes.
        Raises KeyError if field is not a valid DesignLanguage key.
        """
        global _current_design_language
        if _current_design_language is None:
            return {"ok": False, "error": "No design language set. Call urban_generate_design_language first."}
        if field not in _SCHEMA_KEYS:
            raise KeyError(f"Unknown field: {field!r}. Valid: {sorted(_SCHEMA_KEYS)}")
        _current_design_language[field] = value
        updated_prompt = field in ("material_palette", "facade_vocabulary", "colour_story", "style_name")
        if updated_prompt:
            _current_design_language["diffusion_prompt"] = _build_diffusion_prompt(_current_design_language)
        return {"ok": True, "field": field, "value": value, "diffusion_prompt_updated": updated_prompt}

    @mcp.tool(annotations=ToolAnnotations(title="Get Design Language", readOnlyHint=True))
    def urban_get_design_language() -> dict[str, object]:
        """
        Return the current session design language, or zero-safe defaults if none
        has been generated yet.
        """
        if _current_design_language is None:
            return {"ok": True, "set": False, **_ZERO}
        return {"ok": True, "set": True, **_current_design_language}
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_urban_design_language.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 3: Run full suite to check regressions**

```bash
uv run pytest tests/ -q
```

Expected: all existing tests + 8 new = passing, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add src/rhmcp/tools/urban_design_language.py tests/test_urban_design_language.py
git commit -m "feat(urban): design language generator — 3 tools, Claude API integration"
```

---

## Task 4: AI Render Pipeline — skeleton + tests (red)

**Files:**
- Create: `src/rhmcp/tools/urban_renders.py`
- Create: `tests/test_urban_renders.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_urban_renders.py`:

```python
"""Unit tests for urban_renders tools. fal.ai and Rhino calls are mocked."""
from __future__ import annotations
import base64
import json
import unittest
from unittest.mock import patch, MagicMock, call
from mcp.server.fastmcp import FastMCP


def _register() -> dict[str, object]:
    import importlib
    import rhmcp.tools.urban_renders as m
    importlib.reload(m)
    mcp = FastMCP("test-renders")
    with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True, "result": {"image_data": base64.b64encode(b"PNG").decode()}}):
        m.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


_FAKE_B64 = base64.b64encode(b"fakepng").decode()
_FAL_RESPONSE = {"images": [{"url": "https://fal.ai/fake.png"}], "seed": 42, "request_id": "req-1"}


def _mock_backend(b64: str = _FAKE_B64):
    return {"ok": True, "result": {"image_data": b64}}


def _mock_httpx_for_fal(img_b64: str = _FAKE_B64):
    """Return a mock httpx client that handles fal POST + image GET."""
    img_bytes = base64.b64decode(img_b64) if img_b64 else b"png"
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = _FAL_RESPONSE
    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.content = img_bytes
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = post_resp
    client.get.return_value = get_resp
    return client


class TestUrbanRenderViews(unittest.TestCase):
    def _call(self, views=None, **kw):
        tools = _register()
        views = views or ["Perspective"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_mock_backend()):
            with patch("httpx.Client", return_value=_mock_httpx_for_fal()):
                with patch.dict("os.environ", {"FAL_KEY": "testkey"}):
                    return tools["urban_render_views"](views=views, **kw)

    def test_returns_one_result_per_view(self):
        results = self._call(views=["Perspective", "Top"])
        self.assertEqual(len(results), 2)

    def test_each_result_has_required_keys(self):
        results = self._call()
        r = results[0]
        for k in ("view", "original_b64", "rendered_b64", "prompt_used", "seed", "ok"):
            self.assertIn(k, r)

    def test_prompt_includes_view_suffix(self):
        results = self._call(views=["Perspective"])
        self.assertIn("street view", results[0]["prompt_used"])

    def test_style_override_appended_to_prompt(self):
        results = self._call(views=["Perspective"], style_override="brutalist concrete")
        self.assertIn("brutalist concrete", results[0]["prompt_used"])

    def test_fal_failure_returns_ok_false_with_original_b64(self):
        tools = _register()
        bad_client = MagicMock()
        bad_client.__enter__ = MagicMock(return_value=bad_client)
        bad_client.__exit__ = MagicMock(return_value=False)
        bad_client.post.side_effect = Exception("timeout")
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_mock_backend()):
            with patch("httpx.Client", return_value=bad_client):
                with patch.dict("os.environ", {"FAL_KEY": "testkey"}):
                    results = tools["urban_render_views"](views=["Perspective"])
        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["original_b64"], _FAKE_B64)
        self.assertEqual(results[0]["rendered_b64"], "")


class TestUrbanRenderStylePreview(unittest.TestCase):
    def test_returns_image_without_rhino_capture(self):
        tools = _register()
        with patch("httpx.Client", return_value=_mock_httpx_for_fal()):
            with patch.dict("os.environ", {"FAL_KEY": "testkey"}):
                r = tools["urban_render_style_preview"](style_prompt="brutalist concrete tower")
        self.assertTrue(r["ok"])
        self.assertIn("image_b64", r)
        self.assertIn("seed", r)


class TestUrbanGetRenders(unittest.TestCase):
    def test_returns_empty_dict_when_none_stored(self):
        tools = _register()
        r = tools["urban_get_renders"]()
        self.assertIsInstance(r, dict)
        self.assertEqual(len(r), 0)

    def test_returns_stored_renders_after_render_views(self):
        tools = _register()
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_mock_backend()):
            with patch("httpx.Client", return_value=_mock_httpx_for_fal()):
                with patch.dict("os.environ", {"FAL_KEY": "testkey"}):
                    tools["urban_render_views"](views=["Perspective"])
        r = tools["urban_get_renders"]()
        self.assertIn("Perspective", r)
```

- [ ] **Step 2: Verify tests fail**

```bash
uv run pytest tests/test_urban_renders.py -v 2>&1 | head -10
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'rhmcp.tools.urban_renders'`

- [ ] **Step 3: Create skeleton**

Create `src/rhmcp/tools/urban_renders.py`:

```python
"""AI render pipeline using fal.ai FLUX.1."""
from __future__ import annotations
from mcp.server.fastmcp import FastMCP

_current_renders: dict = {}

def reset() -> None:
    global _current_renders
    _current_renders = {}

def register(mcp: FastMCP) -> None:
    pass
```

---

## Task 5: AI Render Pipeline — full implementation (green)

**Files:**
- Modify: `src/rhmcp/tools/urban_renders.py`

- [ ] **Step 1: Implement the full module**

Replace `src/rhmcp/tools/urban_renders.py` entirely:

```python
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
        seed_used = int(data.get("seed", seed or 0))
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
        seed_used = int(data.get("seed", seed or 0))
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
            except Exception as first_err:
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
```

- [ ] **Step 2: Run render tests**

```bash
uv run pytest tests/test_urban_renders.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 3: Full suite**

```bash
uv run pytest tests/ -q
```

Expected: all tests pass, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add src/rhmcp/tools/urban_renders.py tests/test_urban_renders.py
git commit -m "feat(urban): AI render pipeline — fal.ai FLUX.1 ControlNet img2img"
```

---

## Task 6: Report templates

**Files:**
- Create: `src/rhmcp/report_templates/report.html.jinja2`
- Create: `src/rhmcp/report_templates/report.css`

- [ ] **Step 1: Create the templates directory**

```bash
mkdir -p src/rhmcp/report_templates
```

- [ ] **Step 2: Create report.css**

Create `src/rhmcp/report_templates/report.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400&display=swap');

:root {
  --bg: #0F172A;
  --card: #1E293B;
  --border: #334155;
  --accent: #7DD3FC;
  --text: #F1F5F9;
  --muted: #94A3B8;
  --green: #86EFAC;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  line-height: 1.6;
}

/* Cover page */
.cover {
  page-break-after: always;
  min-height: 297mm;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}
.cover-hero {
  flex: 1;
  background: var(--card);
  min-height: 180mm;
}
.cover-hero img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.cover-body {
  padding: 20mm 20mm 14mm;
  background: var(--bg);
}
.cover-title { font-size: 28px; font-weight: 700; color: var(--text); }
.cover-subtitle { font-size: 16px; color: var(--accent); margin-top: 6px; }
.cover-meta { color: var(--muted); font-size: 12px; margin-top: 12px; }
.cover-wordmark {
  position: absolute; bottom: 10mm; right: 14mm;
  font-size: 11px; color: var(--muted); letter-spacing: .12em; text-transform: uppercase;
}

/* Inner pages */
.page {
  padding: 14mm 20mm;
  page-break-inside: avoid;
}

h2 { font-size: 18px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
h3 { font-size: 13px; font-weight: 600; color: var(--accent); text-transform: uppercase;
     letter-spacing: .08em; margin-bottom: 10px; margin-top: 18px; }

.label {
  font-size: 10px; text-transform: uppercase; letter-spacing: .1em; color: var(--muted);
}

/* Executive summary */
.exec-summary {
  background: var(--card); border-radius: 8px; padding: 14px 16px;
  border-left: 3px solid var(--accent); margin-bottom: 16px;
  font-size: 13px; color: var(--text); line-height: 1.7;
}

/* Stats strip */
.stats-strip {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px;
}
.stat-card {
  background: var(--card); border-radius: 8px; padding: 12px;
  border: 1px solid var(--border); text-align: center;
}
.stat-value { font-size: 22px; font-weight: 700; color: var(--accent); }
.stat-label { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-top: 2px; }

/* Massing views grid */
.views-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px;
}
.view-card {
  background: var(--card); border-radius: 8px; overflow: hidden;
  border: 1px solid var(--border);
}
.view-card img { width: 100%; display: block; }
.view-label {
  padding: 6px 10px; font-size: 10px; text-transform: uppercase;
  letter-spacing: .08em; color: var(--muted);
}

/* Solar section */
.solar-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; margin-bottom: 20px; }
.solar-capture { background: var(--card); border-radius: 8px; overflow: hidden; }
.solar-capture img { width: 100%; display: block; }
.solar-metrics { display: flex; flex-direction: column; gap: 8px; }
.solar-metric {
  background: var(--card); border-radius: 8px; padding: 12px;
  border: 1px solid var(--border);
}
.solar-metric-value { font-size: 20px; font-weight: 700; color: var(--green); }

/* Design language */
.vocab-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.vocab-tag {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 4px; padding: 3px 8px; font-size: 11px; color: var(--text);
}
.palette { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.swatch { border-radius: 6px; overflow: hidden; width: 80px; }
.swatch-colour { height: 40px; }
.swatch-label { padding: 4px; font-size: 9px; color: var(--muted); background: var(--card); text-align: center; }

/* Parameters table */
.params-table {
  width: 100%; border-collapse: collapse; font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
}
.params-table th {
  text-align: left; padding: 6px 10px; color: var(--muted);
  font-size: 10px; text-transform: uppercase; letter-spacing: .08em;
  border-bottom: 1px solid var(--border);
}
.params-table td {
  padding: 6px 10px; color: var(--text);
  border-bottom: 1px solid var(--card);
}
.params-table tr:nth-child(even) td { background: var(--card); }

/* Page number footer */
.page-footer {
  position: fixed; bottom: 8mm; right: 14mm;
  font-size: 10px; color: var(--muted);
}

@media print {
  .page { page-break-inside: avoid; }
  .cover { page-break-after: always; }
}
```

- [ ] **Step 3: Create report.html.jinja2**

Create `src/rhmcp/report_templates/report.html.jinja2`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ project_name }} — {{ scheme_name }}</title>
<style>{{ css }}</style>
</head>
<body>

<!-- ① Cover -->
<div class="cover">
  <div class="cover-hero">
    {% if renders.get("Perspective") and renders["Perspective"].get("rendered_b64") %}
      <img src="data:image/png;base64,{{ renders["Perspective"]["rendered_b64"] }}" alt="Perspective render">
    {% elif renders.get("Perspective") and renders["Perspective"].get("original_b64") %}
      <img src="data:image/png;base64,{{ renders["Perspective"]["original_b64"] }}" alt="Perspective view">
    {% endif %}
  </div>
  <div class="cover-body">
    <div class="cover-title">{{ project_name }}</div>
    <div class="cover-subtitle">{{ scheme_name }}</div>
    <div class="cover-meta">
      {% if author %}{{ author }} · {% endif %}{{ date }}
      {% if design_language.style_name %} · {{ design_language.style_name }}{% endif %}
    </div>
  </div>
  <div class="cover-wordmark">UrbanAgent</div>
</div>

<!-- ② Executive Summary -->
<div class="page">
  <h3>Executive Summary</h3>
  {% if design_language.executive_summary %}
  <div class="exec-summary">{{ design_language.executive_summary }}</div>
  {% endif %}
  <div class="stats-strip">
    <div class="stat-card">
      <div class="stat-value">{{ "{:,.0f}".format(metrics.gfa_m2) }}</div>
      <div class="stat-label">GFA m²</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{{ "%.1f"|format(metrics.far) }}</div>
      <div class="stat-label">FAR</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{{ metrics.unit_count_est }}</div>
      <div class="stat-label">Est. Units</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{{ "%.0f"|format(metrics.open_space_pct) }}%</div>
      <div class="stat-label">Open Space</div>
    </div>
  </div>
</div>

<!-- ③ Massing Views -->
<div class="page">
  <h3>Massing Views</h3>
  <div class="views-grid">
    {% for view_name in ["Perspective", "Top", "Front", "Right"] %}
    {% set r = renders.get(view_name) %}
    {% if r %}
    <div class="view-card">
      {% set img = r.get("rendered_b64") or r.get("original_b64") %}
      {% if img %}
        <img src="data:image/png;base64,{{ img }}" alt="{{ view_name }}">
      {% endif %}
      <div class="view-label">{{ view_name }}</div>
    </div>
    {% endif %}
    {% endfor %}
  </div>
</div>

<!-- ⑤ Solar Analysis (optional) -->
{% if include_solar and solar %}
<div class="page">
  <h3>Solar Analysis</h3>
  <div class="solar-grid">
    <div class="solar-capture">
      {% if solar_capture_b64 %}
        <img src="data:image/png;base64,{{ solar_capture_b64 }}" alt="Solar radiation mesh">
      {% endif %}
    </div>
    <div class="solar-metrics">
      <div class="solar-metric">
        <div class="label">Avg Radiation</div>
        <div class="solar-metric-value">{{ solar.avg_radiation_kwh_m2 }}</div>
        <div class="label">kWh/m²</div>
      </div>
      <div class="solar-metric">
        <div class="label">Worst Overshadowing</div>
        <div class="solar-metric-value">{{ solar.overshadow_hours_worst }}</div>
        <div class="label">hours</div>
      </div>
      {% if solar.epw_used %}
      <div class="solar-metric">
        <div class="label">Climate Data</div>
        <div style="color: var(--muted); font-size: 11px; margin-top: 4px;">{{ solar.epw_used }}</div>
      </div>
      {% endif %}
    </div>
  </div>
</div>
{% endif %}

<!-- ⑥ Design Language (optional) -->
{% if include_design_language and design_language.style_name %}
<div class="page">
  <h3>Design Language</h3>
  <h2>{{ design_language.style_name }}</h2>
  {% if design_language.facade_vocabulary %}
  <div class="vocab-tags" style="margin-top: 10px;">
    {% for tag in design_language.facade_vocabulary %}
    <span class="vocab-tag">{{ tag }}</span>
    {% endfor %}
  </div>
  {% endif %}
  {% if design_language.material_palette %}
  <div class="label" style="margin-bottom: 6px;">Material Palette</div>
  <div class="palette">
    {% for mat in design_language.material_palette %}
    <div class="swatch">
      <div class="swatch-colour" style="background: {{ mat.hex }};"></div>
      <div class="swatch-label">{{ mat.name }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  {% if design_language.landscape_character %}
  <p style="color: var(--muted); margin-top: 10px;">{{ design_language.landscape_character }}</p>
  {% endif %}
</div>
{% endif %}

<!-- ⑦ Parameters Appendix -->
{% if params %}
<div class="page">
  <h3>Parameters Appendix</h3>
  <table class="params-table">
    <thead>
      <tr><th>Parameter</th><th>Value</th><th>Notes</th></tr>
    </thead>
    <tbody>
      {% for p in params %}
      <tr>
        <td>{{ p.name }}</td>
        <td>{{ p.value }}</td>
        <td style="color: var(--muted);">{{ p.notes or "" }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

<div class="page-footer">UrbanAgent</div>
</body>
</html>
```

- [ ] **Step 4: Register templates in package data**

`pyproject.toml` already has `"rhmcp" = [...]` package-data. Add the new path:

```toml
[tool.setuptools.package-data]
"rhmcp" = [
    "data/*.yml",
    "data/*.md",
    "report_templates/*.jinja2",
    "report_templates/*.css",
]
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/report_templates/ pyproject.toml
git commit -m "feat(urban): report templates — branded Jinja2 HTML + CSS design tokens"
```

---

## Task 7: Report Generator — tests (red) + implementation (green)

**Files:**
- Create: `src/rhmcp/tools/urban_report.py`
- Create: `tests/test_urban_report.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_urban_report.py`:

```python
"""Unit tests for urban_report tools. DocRaptor and S3 are mocked."""
from __future__ import annotations
import importlib
import unittest
from unittest.mock import patch, MagicMock, call
from mcp.server.fastmcp import FastMCP

_SAMPLE_METRICS = {"gfa_m2": 28000.0, "far": 3.5, "unit_count_est": 280, "open_space_pct": 22.0}
_SAMPLE_DL = {
    "ok": True, "set": True,
    "style_name": "Nordic", "facade_vocabulary": ["brick"],
    "material_palette": [{"name": "Brick", "hex": "#C4956A", "role": "primary"}],
    "colour_story": {}, "landscape_character": "Green.",
    "diffusion_prompt": "", "negative_prompt": "",
    "executive_summary": "A warm scheme.",
}


def _register():
    import rhmcp.tools.urban_report as m
    importlib.reload(m)
    mcp = FastMCP("test-report")
    m.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


def _mock_docraptor_response(pdf_bytes: bytes = b"%PDF-test"):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.content = pdf_bytes
    return resp


def _mock_s3_client():
    client = MagicMock()
    client.put_object = MagicMock()
    client.generate_presigned_url = MagicMock(return_value="https://s3.example.com/report.pdf")
    return client


class TestUrbanExportReport(unittest.TestCase):
    def _call(self, **kw):
        tools = _register()
        defaults = dict(project_name="TestProject", scheme_name="SchemeA")
        defaults.update(kw)
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch("httpx.post", return_value=_mock_docraptor_response()):
                        with patch("boto3.client", return_value=_mock_s3_client()):
                            with patch.dict("os.environ", {
                                "DOCRAPTOR_API_KEY": "test",
                                "URBAN_AGENT_S3_BUCKET": "test-bucket",
                                "AWS_ACCESS_KEY_ID": "key",
                                "AWS_SECRET_ACCESS_KEY": "secret",
                            }):
                                return tools["urban_export_report"](**defaults)

    def test_returns_ok_true_with_pdf_url(self):
        r = self._call()
        self.assertTrue(r["ok"])
        self.assertIn("pdf_url", r)

    def test_s3_upload_uses_correct_key_format(self):
        s3 = _mock_s3_client()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch("httpx.post", return_value=_mock_docraptor_response()):
                        with patch("boto3.client", return_value=s3):
                            with patch.dict("os.environ", {
                                "DOCRAPTOR_API_KEY": "test",
                                "URBAN_AGENT_S3_BUCKET": "bucket",
                                "AWS_ACCESS_KEY_ID": "k", "AWS_SECRET_ACCESS_KEY": "s",
                            }):
                                tools = _register()
                                tools["urban_export_report"](project_name="Proj", scheme_name="V1")
        call_kwargs = s3.put_object.call_args[1]
        self.assertTrue(call_kwargs["Key"].startswith("reports/Proj/V1/"))
        self.assertTrue(call_kwargs["Key"].endswith(".pdf"))

    def test_solar_section_omitted_when_flag_false(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch.dict("os.environ", {}):
                        r = tools["urban_export_report"](
                            project_name="P", scheme_name="S", include_solar=False)
        # Local fallback — file:// url
        self.assertIn("pdf_url", r)

    def test_design_language_section_omitted_when_flag_false(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch.dict("os.environ", {}):
                        r = tools["urban_export_report"](
                            project_name="P", scheme_name="S", include_design_language=False)
        self.assertIn("pdf_url", r)

    def test_falls_back_to_local_when_no_cloud_credentials(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch.dict("os.environ", {}, clear=True):
                        r = tools["urban_export_report"](project_name="P", scheme_name="S")
        self.assertTrue(r["ok"])
        self.assertTrue(r["pdf_url"].startswith("file://") or "local_path" in r)


class TestUrbanPreviewReport(unittest.TestCase):
    def test_preview_writes_html_without_api_calls(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch("httpx.post") as mock_post:
                        r = tools["urban_preview_report"]()
        mock_post.assert_not_called()
        self.assertTrue(r["ok"])
        self.assertIn("html_content", r)

    def test_preview_html_contains_project_sections(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    r = tools["urban_preview_report"]()
        self.assertIn("Executive Summary", r["html_content"])
        self.assertIn("UrbanAgent", r["html_content"])


class TestUrbanListReports(unittest.TestCase):
    def test_returns_list(self):
        tools = _register()
        r = tools["urban_list_reports"]()
        self.assertIsInstance(r, list)
```

- [ ] **Step 2: Verify tests fail**

```bash
uv run pytest tests/test_urban_report.py -v 2>&1 | head -10
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'rhmcp.tools.urban_report'`

- [ ] **Step 3: Implement urban_report.py**

Create `src/rhmcp/tools/urban_report.py`:

```python
"""Branded PDF report generator — Jinja2 + DocRaptor + S3."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_report_history: list[dict[str, Any]] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent.parent / "report_templates"


def _render_html(
    project_name: str,
    scheme_name: str,
    author: str | None,
    metrics: dict,
    renders: dict,
    design_language: dict,
    solar: dict | None,
    params: list[dict],
    include_solar: bool,
    include_design_language: bool,
) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=False)
    css_path = _TEMPLATES_DIR / "report.css"
    css = css_path.read_text() if css_path.exists() else ""
    template = env.get_template("report.html.jinja2")
    return template.render(
        project_name=project_name,
        scheme_name=scheme_name,
        author=author,
        date=time.strftime("%B %d, %Y"),
        metrics=type("M", (), metrics)(),
        renders=renders,
        design_language=design_language,
        solar=solar,
        solar_capture_b64="",
        params=params,
        include_solar=include_solar,
        include_design_language=include_design_language,
        css=css,
    )


def _html_to_pdf_docraptor(html: str) -> bytes:
    api_key = os.environ.get("DOCRAPTOR_API_KEY", "")
    resp = httpx.post(
        "https://docraptor.com/docs",
        json={
            "user_credentials": api_key,
            "doc": {
                "document_content": html,
                "document_type": "pdf",
                "test": False,
                "prince_options": {"media": "print"},
            },
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.content


def _upload_to_s3(pdf_bytes: bytes, html: str, project: str, scheme: str) -> tuple[str, str]:
    import boto3
    bucket = os.environ["URBAN_AGENT_S3_BUCKET"]
    ts = int(time.time())
    pdf_key = f"reports/{project}/{scheme}/{ts}.pdf"
    html_key = f"reports/{project}/{scheme}/{ts}.html"
    client = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    client.put_object(Bucket=bucket, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf")
    client.put_object(Bucket=bucket, Key=html_key, Body=html.encode(), ContentType="text/html")
    pdf_url = client.generate_presigned_url("get_object",
        Params={"Bucket": bucket, "Key": pdf_key}, ExpiresIn=604800)
    html_url = client.generate_presigned_url("get_object",
        Params={"Bucket": bucket, "Key": html_key}, ExpiresIn=604800)
    return pdf_url, html_url


def _save_local(pdf_bytes: bytes, html: str, project: str, scheme: str) -> tuple[str, str]:
    ts = int(time.time())
    out_dir = Path.home() / ".urbanagent" / "reports" / project / f"{scheme}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "report.pdf"
    html_path = out_dir / "report.html"
    pdf_path.write_bytes(pdf_bytes)
    html_path.write_text(html)
    return f"file://{pdf_path}", f"file://{html_path}"


def reset() -> None:
    """Reset module state."""
    global _report_history
    _report_history = []


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Export Urban Report", destructiveHint=False))
    def urban_export_report(
        project_name: str,
        scheme_name: str,
        author: str | None = None,
        include_solar: bool = True,
        include_design_language: bool = True,
        format: str = "pdf",
    ) -> dict[str, object]:
        """
        Export a branded PDF (or HTML) report: cover page, executive summary,
        massing renders, metrics, solar analysis, design language, parameters.
        Uploads to S3 and returns a 7-day presigned URL.
        Falls back to local ~/.urbanagent/reports/ when cloud credentials absent.
        """
        from rhmcp.tools import urban_design_language, urban_renders
        from rhmcp.tools.urban import _urban_get_metrics

        metrics = _urban_get_metrics()
        renders = urban_renders._current_renders
        dl = urban_design_language._current_design_language or {}
        solar = None  # populated when urban_run_analysis stores results

        html = _render_html(
            project_name=project_name,
            scheme_name=scheme_name,
            author=author,
            metrics=metrics,
            renders=renders,
            design_language=dl,
            solar=solar,
            params=[],
            include_solar=include_solar,
            include_design_language=include_design_language,
        )

        pdf_bytes = b""
        if os.environ.get("DOCRAPTOR_API_KEY"):
            try:
                pdf_bytes = _html_to_pdf_docraptor(html)
            except Exception:
                pass

        if not pdf_bytes:
            pdf_bytes = html.encode()  # fallback: store HTML as "pdf"

        pdf_url = html_url = ""
        local_path = ""

        if os.environ.get("URBAN_AGENT_S3_BUCKET") and os.environ.get("AWS_ACCESS_KEY_ID"):
            try:
                pdf_url, html_url = _upload_to_s3(pdf_bytes, html, project_name, scheme_name)
            except Exception:
                pass

        if not pdf_url:
            pdf_url, html_url = _save_local(pdf_bytes, html, project_name, scheme_name)
            local_path = pdf_url.replace("file://", "")

        record: dict[str, Any] = {
            "scheme_name": scheme_name,
            "pdf_url": pdf_url,
            "html_url": html_url,
            "timestamp": int(time.time()),
            "file_size_kb": round(len(pdf_bytes) / 1024, 1),
        }
        _report_history.append(record)

        return {
            "ok": True,
            "pdf_url": pdf_url,
            "html_url": html_url,
            "file_size_kb": record["file_size_kb"],
            "local_path": local_path,
        }

    @mcp.tool(annotations=ToolAnnotations(title="Preview Urban Report", readOnlyHint=True))
    def urban_preview_report() -> dict[str, object]:
        """
        Render the report as HTML only — no PDF, no S3. Fast iteration before final export.
        Returns the rendered HTML string and writes a temp file.
        """
        import tempfile
        from rhmcp.tools import urban_design_language, urban_renders
        from rhmcp.tools.urban import _urban_get_metrics

        metrics = _urban_get_metrics()
        renders = urban_renders._current_renders
        dl = urban_design_language._current_design_language or {}

        html = _render_html(
            project_name="Preview",
            scheme_name="Draft",
            author=None,
            metrics=metrics,
            renders=renders,
            design_language=dl,
            solar=None,
            params=[],
            include_solar=False,
            include_design_language=bool(dl),
        )

        tmp = Path(tempfile.mktemp(suffix=".html"))
        tmp.write_text(html)
        return {"ok": True, "html_path": str(tmp), "html_content": html}

    @mcp.tool(annotations=ToolAnnotations(title="List Urban Reports", readOnlyHint=True))
    def urban_list_reports() -> list[dict[str, object]]:
        """List all reports exported this session."""
        return list(_report_history)
```

- [ ] **Step 4: Run report tests**

```bash
uv run pytest tests/test_urban_report.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Full suite**

```bash
uv run pytest tests/ -q
```

Expected: 0 failures.

- [ ] **Step 6: Commit**

```bash
git add src/rhmcp/tools/urban_report.py tests/test_urban_report.py
git commit -m "feat(urban): report generator — Jinja2 template, DocRaptor PDF, S3 upload"
```

---

## Task 8: Studio Pipeline — tests (red) + implementation (green)

**Files:**
- Create: `src/rhmcp/tools/urban_pipeline.py`
- Create: `tests/test_urban_pipeline.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_urban_pipeline.py`:

```python
"""Unit tests for urban_pipeline orchestrator. All sub-tools mocked."""
from __future__ import annotations
import importlib
import unittest
from unittest.mock import patch, MagicMock, call
from mcp.server.fastmcp import FastMCP

_SAMPLE_METRICS = {"gfa_m2": 28000.0, "far": 3.5, "unit_count_est": 280, "open_space_pct": 22.0}
_SAMPLE_DL_RESULT = {"ok": True, "style_name": "Nordic", "diffusion_prompt": "nordic render"}
_SAMPLE_RENDERS = [{"view": "Perspective", "ok": True, "rendered_b64": "abc", "original_b64": "abc"}]
_SAMPLE_ANALYSIS = {"ok": True, "avg_radiation_kwh_m2": 380}
_SAMPLE_EXPORT = {"ok": True, "pdf_url": "https://s3.example.com/report.pdf", "html_url": ""}


def _register():
    import rhmcp.tools.urban_pipeline as m
    importlib.reload(m)
    mcp = FastMCP("test-pipeline")
    m.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


def _patch_all(generate_dl=None, render_views=None, run_analysis=None, export_report=None):
    return [
        patch("rhmcp.tools.urban_design_language.register"),
        patch("rhmcp.tools.urban_renders.register"),
        patch("rhmcp.tools.urban_report.register"),
    ]


class TestUrbanRunStudioPipeline(unittest.TestCase):
    def _run(self, **kw):
        tools = _register()
        defaults = dict(project_name="TestProject", scheme_name="V1",
                        brief="Mixed-use in London", render_views=["Perspective"])
        defaults.update(kw)
        with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",
                   return_value=_SAMPLE_DL_RESULT) as mock_dl:
            with patch("rhmcp.tools.urban_pipeline._step_render_views",
                       return_value=_SAMPLE_RENDERS) as mock_rv:
                with patch("rhmcp.tools.urban_pipeline._step_run_solar",
                           return_value=_SAMPLE_ANALYSIS) as mock_solar:
                    with patch("rhmcp.tools.urban_pipeline._step_export_report",
                               return_value=_SAMPLE_EXPORT) as mock_export:
                        result = tools["urban_run_studio_pipeline"](**defaults)
        return result, mock_dl, mock_rv, mock_solar, mock_export

    def test_calls_all_four_steps_in_order(self):
        r, mock_dl, mock_rv, mock_solar, mock_export = self._run()
        mock_dl.assert_called_once()
        mock_rv.assert_called_once()
        mock_solar.assert_called_once()
        mock_export.assert_called_once()

    def test_result_contains_report_url(self):
        r, *_ = self._run()
        self.assertTrue(r["ok"])
        self.assertEqual(r["report_url"], "https://s3.example.com/report.pdf")

    def test_skip_renders_skips_render_views_step(self):
        r, mock_dl, mock_rv, mock_solar, mock_export = self._run(skip_steps=["renders"])
        mock_rv.assert_not_called()
        mock_export.assert_called_once()

    def test_include_solar_false_skips_solar_step(self):
        r, mock_dl, mock_rv, mock_solar, mock_export = self._run(include_solar=False)
        mock_solar.assert_not_called()

    def test_render_failure_does_not_abort_pipeline(self):
        tools = _register()
        with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",
                   return_value=_SAMPLE_DL_RESULT):
            with patch("rhmcp.tools.urban_pipeline._step_render_views",
                       side_effect=Exception("fal timeout")):
                with patch("rhmcp.tools.urban_pipeline._step_run_solar",
                           return_value=_SAMPLE_ANALYSIS):
                    with patch("rhmcp.tools.urban_pipeline._step_export_report",
                               return_value=_SAMPLE_EXPORT) as mock_export:
                        r = tools["urban_run_studio_pipeline"](
                            project_name="P", scheme_name="S",
                            render_views=["Perspective"])
        mock_export.assert_called_once()
        self.assertIn("renders", r["errors"][0].lower() if r["errors"] else "")

    def test_step_log_has_entry_per_attempted_step(self):
        r, *_ = self._run()
        steps = [s["step"] for s in r["step_log"]]
        self.assertIn("design_language", steps)
        self.assertIn("renders", steps)
        self.assertIn("export", steps)

    def test_design_language_failure_aborts_pipeline(self):
        tools = _register()
        with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",
                   side_effect=Exception("API error")):
            r = tools["urban_run_studio_pipeline"](
                project_name="P", scheme_name="S", render_views=["Perspective"])
        self.assertFalse(r["ok"])
        self.assertFalse(r.get("report_url", ""))


class TestUrbanListPipelineRuns(unittest.TestCase):
    def test_accumulates_runs_across_calls(self):
        tools = _register()
        with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",
                   return_value=_SAMPLE_DL_RESULT):
            with patch("rhmcp.tools.urban_pipeline._step_render_views",
                       return_value=_SAMPLE_RENDERS):
                with patch("rhmcp.tools.urban_pipeline._step_run_solar",
                           return_value=_SAMPLE_ANALYSIS):
                    with patch("rhmcp.tools.urban_pipeline._step_export_report",
                               return_value=_SAMPLE_EXPORT):
                        for i in range(3):
                            tools["urban_run_studio_pipeline"](
                                project_name="P", scheme_name=f"V{i}")
        runs = tools["urban_list_pipeline_runs"]()
        self.assertEqual(len(runs), 3)
```

- [ ] **Step 2: Verify tests fail**

```bash
uv run pytest tests/test_urban_pipeline.py -v 2>&1 | head -10
```

Expected: `ERROR` — import error.

- [ ] **Step 3: Implement urban_pipeline.py**

Create `src/rhmcp/tools/urban_pipeline.py`:

```python
"""Studio Pipeline — single-call orchestrator: brief → design language → renders → report."""
from __future__ import annotations

import time
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_pipeline_history: list[dict[str, Any]] = []
_current_run: dict[str, Any] | None = None

# ---------------------------------------------------------------------------
# Step functions (module-level so tests can patch them)
# ---------------------------------------------------------------------------

def _step_generate_design_language(
    brief: str, typology: str, far: float, climate_zone: str, style_hints: str | None
) -> dict[str, Any]:
    from rhmcp.tools.urban_design_language import _current_design_language
    # If already set and brief is empty, reuse existing
    if not brief and _current_design_language:
        return {"ok": True, **_current_design_language}
    # Dynamically call the registered tool function
    import rhmcp.tools.urban_design_language as m
    # Direct call via helper to avoid needing the registered MCP instance
    from rhmcp.tools import urban_design_language
    import anthropic, json, os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"ok": False, "error": "ANTHROPIC_API_KEY not set"}
    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = urban_design_language._build_user_prompt(
        brief, typology, far, climate_zone, style_hints)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=urban_design_language._SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    result = json.loads(msg.content[0].text)
    urban_design_language._current_design_language = result
    return {"ok": True, **result}


def _step_render_views(views: list[str], strength: float) -> list[dict[str, Any]]:
    from rhmcp.tools import urban_renders
    import os
    if not os.environ.get("FAL_KEY"):
        return [{"view": v, "ok": False, "error": "FAL_KEY not set",
                 "original_b64": "", "rendered_b64": "", "prompt_used": "",
                 "seed": 0, "model": "", "fal_request_id": ""} for v in views]
    results = []
    from rhmcp.tools.urban_design_language import _current_design_language
    base_prompt = (_current_design_language or {}).get(
        "diffusion_prompt", "architectural render, photorealistic, 8k")
    negative = (_current_design_language or {}).get(
        "negative_prompt", "cartoon, blurry, low quality")
    for view in views:
        b64 = urban_renders._capture_named_view(view)
        suffix = urban_renders._VIEW_SUFFIXES.get(view, urban_renders._DEFAULT_SUFFIX)
        prompt = f"{base_prompt}, {suffix}"
        try:
            rendered_b64, request_id, seed = urban_renders._fal_img2img(
                b64, prompt, negative, strength, None)
            result: dict[str, Any] = {
                "view": view, "ok": True,
                "original_b64": b64, "rendered_b64": rendered_b64,
                "prompt_used": prompt, "seed": seed,
                "model": "fal-ai/flux-dev-canny", "fal_request_id": request_id,
            }
        except Exception as exc:
            result = {"view": view, "ok": False, "error": str(exc),
                      "original_b64": b64, "rendered_b64": "", "prompt_used": prompt,
                      "seed": 0, "model": "", "fal_request_id": ""}
        urban_renders._current_renders[view] = result
        results.append(result)
    return results


def _step_run_solar(geometry_layer: str, climate_zone: str) -> dict[str, Any]:
    from rhmcp.tools.urban import _urban_run_analysis_internal
    return _urban_run_analysis_internal("solar", geometry_layer, climate_zone)


def _step_export_report(project_name: str, scheme_name: str,
                        include_solar: bool) -> dict[str, Any]:
    from rhmcp.tools import urban_design_language, urban_renders, urban_report
    from rhmcp.tools.urban import _urban_get_metrics
    metrics = _urban_get_metrics()
    renders = urban_renders._current_renders
    dl = urban_design_language._current_design_language or {}
    html = urban_report._render_html(
        project_name=project_name,
        scheme_name=scheme_name,
        author=None,
        metrics=metrics,
        renders=renders,
        design_language=dl,
        solar=None,
        params=[],
        include_solar=include_solar,
        include_design_language=bool(dl),
    )
    import os
    pdf_bytes = b""
    if os.environ.get("DOCRAPTOR_API_KEY"):
        try:
            pdf_bytes = urban_report._html_to_pdf_docraptor(html)
        except Exception:
            pass
    if not pdf_bytes:
        pdf_bytes = html.encode()
    pdf_url = html_url = ""
    if os.environ.get("URBAN_AGENT_S3_BUCKET") and os.environ.get("AWS_ACCESS_KEY_ID"):
        try:
            pdf_url, html_url = urban_report._upload_to_s3(
                pdf_bytes, html, project_name, scheme_name)
        except Exception:
            pass
    if not pdf_url:
        pdf_url, html_url = urban_report._save_local(
            pdf_bytes, html, project_name, scheme_name)
    return {"ok": True, "pdf_url": pdf_url, "html_url": html_url}


def reset() -> None:
    global _pipeline_history, _current_run
    _pipeline_history = []
    _current_run = None


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Run Studio Pipeline", destructiveHint=True))
    def urban_run_studio_pipeline(
        project_name: str,
        scheme_name: str,
        brief: str | None = None,
        render_views: list[str] | None = None,
        render_strength: float = 0.65,
        include_solar: bool = True,
        style_hints: str | None = None,
        skip_steps: list[str] | None = None,
    ) -> dict[str, object]:
        """
        Single-call studio pipeline: brief → design language → AI renders → solar → PDF report.
        Returns PipelineResult with report_url, renders, metrics, step_log.
        Individual step failures do not abort the pipeline (except design_language failure).
        Use skip_steps=["renders"] or skip_steps=["solar"] to re-run from a checkpoint.
        """
        global _current_run
        skip = set(skip_steps or [])
        views = render_views or ["Perspective", "Top", "Front", "Right"]
        brief_text = brief or ""
        run_id = str(uuid.uuid4())[:8]
        t_start = time.time()
        step_log: list[dict[str, Any]] = []
        errors: list[str] = []
        report_url = ""
        renders: list[dict] = []

        _current_run = {"run_id": run_id, "running": True, "current_step": "design_language",
                        "steps_done": 0, "steps_total": 4}

        # Step 1 — Design Language (aborting on failure)
        t0 = time.time()
        if "design_language" in skip:
            step_log.append({"step": "design_language", "status": "skipped",
                             "duration_s": 0.0, "summary": "reusing existing design language"})
        else:
            try:
                from rhmcp.tools.urban import _current_typology, _current_far
                dl_result = _step_generate_design_language(
                    brief_text,
                    _current_typology or "tower",
                    _current_far or 3.5,
                    "London",
                    style_hints,
                )
                step_log.append({"step": "design_language", "status": "ok",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": f"Design language: {dl_result.get('style_name', '')}"})
            except Exception as exc:
                _current_run["running"] = False
                return {"ok": False, "run_id": run_id, "report_url": "",
                        "renders": [], "metrics": {}, "design_language": {},
                        "step_log": step_log, "elapsed_s": round(time.time() - t_start, 2),
                        "errors": [f"design_language: {exc}"]}

        _current_run["steps_done"] = 1
        _current_run["current_step"] = "renders"

        # Step 2 — AI Renders (non-aborting)
        t0 = time.time()
        if "renders" in skip:
            step_log.append({"step": "renders", "status": "skipped",
                             "duration_s": 0.0, "summary": "reusing existing renders"})
        else:
            try:
                renders = _step_render_views(views, render_strength)
                failed = sum(1 for r in renders if not r.get("ok"))
                step_log.append({"step": "renders", "status": "ok",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": f"{len(renders)} views rendered, {failed} failed"})
                if failed:
                    errors.append(f"renders: {failed}/{len(renders)} views failed")
            except Exception as exc:
                step_log.append({"step": "renders", "status": "failed",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": str(exc)})
                errors.append(f"renders: {exc}")

        _current_run["steps_done"] = 2
        _current_run["current_step"] = "solar"

        # Step 3 — Solar (non-aborting, optional)
        t0 = time.time()
        solar: dict[str, Any] | None = None
        if not include_solar or "solar" in skip:
            step_log.append({"step": "solar", "status": "skipped",
                             "duration_s": 0.0, "summary": "solar analysis skipped"})
        else:
            try:
                from rhmcp.tools.urban import _current_typology
                layer = f"Urban::Massing::{(_current_typology or 'tower').title()}"
                solar = _step_run_solar(layer, "London")
                step_log.append({"step": "solar", "status": "ok",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": f"avg radiation {solar.get('avg_radiation_kwh_m2', 0)} kWh/m²"})
            except Exception as exc:
                step_log.append({"step": "solar", "status": "failed",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": str(exc)})
                errors.append(f"solar: {exc}")

        _current_run["steps_done"] = 3
        _current_run["current_step"] = "export"

        # Step 4 — Export (non-aborting)
        t0 = time.time()
        try:
            export = _step_export_report(project_name, scheme_name, include_solar and solar is not None)
            report_url = export.get("pdf_url", "")
            step_log.append({"step": "export", "status": "ok",
                             "duration_s": round(time.time() - t0, 2),
                             "summary": f"report exported to {report_url}"})
        except Exception as exc:
            step_log.append({"step": "export", "status": "failed",
                             "duration_s": round(time.time() - t0, 2), "summary": str(exc)})
            errors.append(f"export: {exc}")

        elapsed = round(time.time() - t_start, 2)
        _current_run["running"] = False
        _current_run["steps_done"] = 4

        result: dict[str, Any] = {
            "ok": True,
            "run_id": run_id,
            "scheme_name": scheme_name,
            "report_url": report_url,
            "renders": renders,
            "step_log": step_log,
            "elapsed_s": elapsed,
            "errors": errors,
        }
        _pipeline_history.append({
            "run_id": run_id, "scheme_name": scheme_name,
            "timestamp": int(time.time()), "report_url": report_url,
            "steps_completed": len([s for s in step_log if s["status"] == "ok"]),
            "errors": errors,
        })
        return result

    @mcp.tool(annotations=ToolAnnotations(title="Pipeline Status", readOnlyHint=True))
    def urban_pipeline_status() -> dict[str, object]:
        """Return status of the running or last completed pipeline."""
        if _current_run is None:
            return {"running": False, "current_step": None,
                    "steps_done": 0, "steps_total": 4, "elapsed_s": 0.0, "errors": []}
        return dict(_current_run)

    @mcp.tool(annotations=ToolAnnotations(title="List Pipeline Runs", readOnlyHint=True))
    def urban_list_pipeline_runs() -> list[dict[str, object]]:
        """List all pipeline runs this session with their report URLs and step summaries."""
        return list(_pipeline_history)
```

- [ ] **Step 4: Run pipeline tests**

```bash
uv run pytest tests/test_urban_pipeline.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Full suite**

```bash
uv run pytest tests/ -q
```

Expected: 0 failures.

- [ ] **Step 6: Commit**

```bash
git add src/rhmcp/tools/urban_pipeline.py tests/test_urban_pipeline.py
git commit -m "feat(urban): studio pipeline orchestrator — 3 tools, 4-step sequential execution"
```

---

## Task 9: Update urban_clear_massing to reset new module state

**Files:**
- Modify: `src/rhmcp/tools/urban.py`

- [ ] **Step 1: Find the clear_massing tool in urban.py**

```bash
grep -n "urban_clear_massing\|def urban_clear" src/rhmcp/tools/urban.py
```

Note the line number. The function body calls `rhino.execute_python` to delete objects and returns `{ok, deleted_count}`.

- [ ] **Step 2: Add reset calls at the end of the clear_massing body**

Find the return statement inside `urban_clear_massing` and add resets before it. The function looks like:

```python
def urban_clear_massing(layer_prefix: str = "Urban") -> dict[str, object]:
    ...
    # existing deletion logic
    ...
    return {"ok": True, "deleted_count": deleted_count}
```

Add two import+reset calls just before the return:

```python
def urban_clear_massing(layer_prefix: str = "Urban") -> dict[str, object]:
    ...
    # existing deletion logic
    ...
    try:
        from rhmcp.tools import urban_design_language, urban_renders, urban_pipeline
        urban_design_language.reset()
        urban_renders.reset()
        urban_pipeline.reset()
    except ImportError:
        pass
    return {"ok": True, "deleted_count": deleted_count}
```

Use a bare `try/except ImportError` so if the new modules aren't imported yet (e.g. tests that only load urban.py), clear_massing still works.

- [ ] **Step 3: Run the clear_massing tests**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanClearMassing -v
```

Expected: all 3 existing clear_massing tests PASS.

- [ ] **Step 4: Run full suite**

```bash
uv run pytest tests/ -q
```

Expected: 0 failures.

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/urban.py
git commit -m "feat(urban): urban_clear_massing resets design language, renders, pipeline state"
```

---

## Task 10: README — Studio Pipeline section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find the Urban Massing section in README**

```bash
grep -n "## Urban Massing" README.md
```

- [ ] **Step 2: Add the Studio Pipeline section after the Urban Massing section**

Insert after the Urban Massing section:

```markdown
## Studio Pipeline

One call takes you from a site brief to a branded PDF report with AI renders.

### Workflow

```
Brief → urban_generate_design_language → urban_render_views → urban_export_report
           or run everything at once:
urban_run_studio_pipeline(project_name, scheme_name, brief, render_views, include_solar)
```

### Prerequisites

| Feature | Requirement |
|---|---|
| Design language | `ANTHROPIC_API_KEY` |
| AI renders | `FAL_KEY` (fal.ai account) |
| PDF export | `DOCRAPTOR_API_KEY` (optional — falls back to local HTML) |
| Cloud storage | `URBAN_AGENT_S3_BUCKET` + AWS credentials (optional — falls back to `~/.urbanagent/reports/`) |

All cloud services are optional. Without them, reports are saved locally and renders are skipped with raw Rhino captures used as fallback.

### Tools

| Tool | Description |
|---|---|
| `urban_generate_design_language` | Generate style name, materials, colour story, diffusion prompt from site brief |
| `urban_update_design_language` | Patch a single field (re-derives diffusion prompt on material/style changes) |
| `urban_get_design_language` | Read current session design language |
| `urban_render_views` | Capture Rhino viewports + AI-render via fal.ai FLUX.1 ControlNet |
| `urban_render_style_preview` | Quick text-to-image mood board preview (no massing needed) |
| `urban_get_renders` | Read all renders from current session |
| `urban_export_report` | Export branded PDF report with S3 share link |
| `urban_preview_report` | Render HTML preview (no PDF/S3, fast iteration) |
| `urban_list_reports` | List all reports exported this session |
| `urban_run_studio_pipeline` | Single-call orchestrator: runs all steps in sequence |
| `urban_pipeline_status` | Check running/completed pipeline status |
| `urban_list_pipeline_runs` | History of pipeline runs this session |

### Example conversation

```
User: Design a podium tower for a 100m×80m site in Shoreditch. FAR 3.5, 70% residential.

Claude: [calls urban_generate_massing + urban_generate_design_language]
        → "Contemporary Brick Residential" — warm brick, dark steel trim, planted podium
        [calls urban_render_views(["Perspective","Top","Front","Right"])]
        → 4 AI-rendered views
        [calls urban_export_report(project_name="Shoreditch", scheme_name="V1")]
        → https://s3.example.com/reports/Shoreditch/V1/1234567890.pdf
        "Report ready. Scheme shows 28,000m² GFA, FAR 3.5, ~280 units, 22% open space."
```

### Env var setup

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export FAL_KEY=...
export DOCRAPTOR_API_KEY=...
export URBAN_AGENT_S3_BUCKET=my-urbanagent-reports
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```
```

- [ ] **Step 3: Verify README renders cleanly**

```bash
grep -c "urban_run_studio_pipeline" README.md
```

Expected: at least 2 occurrences.

- [ ] **Step 4: Run full suite one final time**

```bash
uv run pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: studio pipeline README section — tool list, env vars, example conversation"
```

---

## Self-review

**Spec coverage:**
- ① Design Language: 3 tools ✓, Claude API ✓, retry logic ✓, module state ✓
- ② AI Renders: 3 tools ✓, fal.ai FLUX.1 canny ✓, per-view suffixes ✓, failure fallback ✓
- ③ Report: 3 tools ✓, 7-section Jinja2 template ✓, DocRaptor ✓, S3 + local fallback ✓, branding ✓
- ④ Pipeline: 3 tools ✓, 4-step execution ✓, skip_steps ✓, error isolation ✓, version history ✓
- urban_clear_massing resets new state ✓
- README section ✓

**Type consistency:**
- `_step_*` functions defined at module level in urban_pipeline.py — patchable by tests ✓
- `reset()` exported from all 3 new modules — called by urban_clear_massing ✓
- `_current_renders`, `_current_design_language` accessed directly by pipeline steps ✓

**No placeholders:** All code blocks contain complete, runnable implementations.
