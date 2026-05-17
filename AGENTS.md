# AGENTS.md — rhino-mcp Developer Guide for AI Agents

This file gives AI coding agents (Claude, Codex, Gemini, etc.) the context needed to work effectively in this codebase.

---

## What This Project Is

**rhino-mcp** is an MCP (Model Context Protocol) server that lets AI assistants control Rhino 3D. It has two components:

1. **Python MCP server** (`src/rhmcp/`) — FastMCP-based server exposing 347 tools to AI clients
2. **C# Rhino plugin** (`rhino_plugin/`) — TCP socket server inside Rhino (port 1999) that receives and executes commands

Current version: **0.11.0**

---

## Architecture

```
AI client (Claude Desktop / Claude Code / Cursor / Codex)
    ↓ MCP protocol
Python MCP server (src/rhmcp/)
    ↓ TCP JSON (port 1999)           ↓ rhinocode CLI (fallback)
C# plugin (rhino-mcp.rhp)         rhinocode subprocess
    ↓
Rhino 3D document
```

**Dual backend**: `plugin_client.py` tries the TCP socket first; if unavailable, `rhinocode.py` falls back to the `rhinocode` CLI. Controlled by `RHINO_MCP_BACKEND` env var (`auto` | `plugin` | `rhinocode`).

---

## Key Files

| Path | Purpose |
|---|---|
| `src/rhmcp/__init__.py` | MCP server entry point, HTTP/stdio transport setup, registers all tool modules |
| `src/rhmcp/tools/` | 50+ tool modules, each with a `register(mcp)` function |
| `src/rhmcp/tools_helpers/backend.py` | Backend router: `execute_python`, `run_plugin_or_python`, `run_command` |
| `src/rhmcp/tools_helpers/plugin_client.py` | TCP socket client with exponential backoff retry |
| `src/rhmcp/tools_helpers/rhinocode.py` | rhinocode CLI fallback, temp-file polling for results |
| `src/rhmcp/tools_helpers/validate.py` | Shared input validators returning error-dicts or None |
| `src/rhmcp/tools_helpers/security.py` | Security helpers: `sanitise_rhino_path`, `validate_download_url`, `safe_extractall`, `clamp` |
| `src/rhmcp/tools_helpers/slot_registry.py` | Multi-Rhino slot registry: `discover()`, `get()`, `wait_for_slot()` — reads `{pid}.json` files from system temp dir |
| `src/rhmcp/tools_helpers/rhino_launcher.py` | Auto-launch Rhino and wait for slot announcement: `find_rhino()`, `launch()` |
| `src/rhmcp/tools/gh2.py` | 11 GH2 tools — `rhino_id` aware, routes via `rhino.plugin_result()` |
| `src/rhmcp/tools/slots.py` | `get_rhino_instances` (slot discovery) and `launch_rhino` (auto-launch) |
| `src/rhmcp/tools_helpers/errors.py` | `normalize()` — ensures consistent `ok`/`error` shape |
| `rhino_plugin/RhinoMCPPlugin/` | C# Rhino plugin source |
| `rhino_plugin/package/manifest.yml` | Yak package manifest |
| `rhino_plugin/release/` | Built artifacts (.rhp, .yak) — gitignored |
| `tests/` | Unit, smoke, script-syntax, and integration tests |
| `scripts/package-plugin.sh` | Build .rhp and .yak from source |

---

## Tool Module Pattern

Every tool module follows this pattern:

```python
from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate

def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="...", readOnlyHint=True))
    def my_tool(object_id: str, ...) -> dict[str, object]:
        err = validate.guid(object_id, "object_id")
        if err: return err
        payload = {"op": "my_op", "object_id": object_id, ...}
        code = "__mcp_data = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

_SCRIPT = r'''
import rhinoscriptsyntax as rs
data = __mcp_data
# ... rhinoscript code ...
result = {"key": value}   # must assign result
'''
```

**Rules:**
- Always validate inputs with `validate.*` before building payloads
- Always assign `result` in `_SCRIPT` blocks — it's captured and returned via `__MCP_RESULT__:` sentinel
- Use `if err: return err` (E701 — intentional single-line pattern, not a bug)
- Tools that call `_run("op", locals())` must have `payload.pop("err", None)` in `_run()` to avoid locals() pollution

---

## Validators (`validate.py`)

| Function | What it checks |
|---|---|
| `validate.guid(v, field)` | UUID format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `validate.guid_list(v, field)` | Non-empty list of valid GUIDs |
| `validate.coordinate(v, field)` | `[x, y, z]` list of 3 numbers |
| `validate.color(v, field)` | `[r, g, b]` or `[r, g, b, a]` integers 0–255 |
| `validate.layer_name(v, field)` | Non-empty string |
| `validate.positive(v, field)` | Number > 0 |
| `validate.non_negative(v, field)` | Number >= 0 |

All return `{"ok": False, "error": "...", "error_code": "..."}` on failure, `None` on success.

---

## Running Tests

```bash
# Unit + smoke + script-syntax + security (no Rhino needed)
uv run pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_gh_integration.py --ignore=tests/test_studio_pipeline_integration.py -q

# Integration tests (requires Rhino running with plugin loaded)
uv run pytest tests/test_integration.py -v -m integration

# Lint
uvx ruff check src/rhmcp --select=E,W,F --ignore=E501,E701,E402,E741
```

**334 tests** (unit, smoke, script-syntax, and security) must pass before any commit. The CI workflow (`.github/workflows/ci.yml`) runs these on Python 3.10/3.11/3.12.

---

## Building Packages

```bash
# Build .rhp and .yak (requires Rhino 8 installed on macOS)
bash scripts/package-plugin.sh

# Build Python wheel and sdist
uv build
```

Artifacts land in `rhino_plugin/release/` (gitignored — upload to GitHub releases manually).

---

## Version Bumping Checklist

When bumping the version (e.g. `0.11.0` → `0.12.0`):

1. `pyproject.toml` — `version = "..."`
2. `rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj` — `<Version>...</Version>`
3. `rhino_plugin/package/manifest.yml` — `version: ...`
4. `rhino_plugin/release/manifest.yml` — `version: ...`
5. `README.md` — download links and yak filename
6. `CHANGELOG.md` — add new entry at top
7. `.env.example` — verify all new env vars are documented

Tool count: verify with `uv run python -c "..."` (see below) before updating docs.

```bash
uv run python -c "
from mcp.server.fastmcp import FastMCP
import rhmcp.tools as t, pkgutil, importlib
mcp = FastMCP('c')
for _, n, _ in pkgutil.iter_modules(t.__path__):
    m = importlib.import_module(f'rhmcp.tools.{n}')
    if hasattr(m, 'register'): m.register(mcp)
print(len(mcp._tool_manager._tools))
"
```

---

## Error Response Shape

All tools must return consistent shapes via `errors.normalize()`:

```python
# Success
{"ok": True, "result": {...}, "backend": "plugin"|"rhinocode"}

# Failure
{"ok": False, "error": "human-readable message", "error_code": "SNAKE_CASE_CODE"}
```

Common error codes: `INVALID_GUID`, `INVALID_COLOR`, `INVALID_COORDINATE`, `INVALID_VALUE`, `INVALID_GUID_LIST`, `SOCKET_UNAVAILABLE`, `RHINOCODE_DISPATCH_FAILED`, `COMPUTATION_FAILED`.

---

## CI / GitHub Actions

`.github/workflows/ci.yml` runs on every push/PR to `main`:
- **test** job: Python 3.10, 3.11, 3.12 — `uv sync --group dev` then pytest (no integration tests)
- **lint** job: ruff with `--select=E,W,F --ignore=E501,E701,E402,E741`

The `E701` ignore is intentional — `if err: return err` is the project's validation pattern.
