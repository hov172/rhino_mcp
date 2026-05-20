# Compact Mode (Schema-on-Demand) Design

> **Status:** Approved — ready for implementation

## Goal

Cut per-request token cost from ~52k (full) or ~28k (core) down to ~1.5k by deferring tool schemas until the AI explicitly requests them.

## Background

MCP sends the full tool list — name + description + JSON input schema — to the AI client on every request. With 360 tools, that is ~52k tokens before any actual work starts. The profiles feature (v0.13.0) reduces this to ~28k for `core`, but the fundamental problem remains: schemas for tools that will never be used in a session are still transmitted.

**Compact mode** registers only 3 meta-tools instead of 360 full tool schemas. The AI discovers tools lazily: list → describe → call.

---

## Architecture

### Files

| File | Change |
|------|--------|
| `src/rhmcp/tools_helpers/compact_registry.py` | New — captures tool registrations from a shadow FastMCP, implements list/describe/call logic |
| `src/rhmcp/__init__.py` | Add `--compact` flag, `RHMCP_COMPACT` env var, compact mode branch in startup |
| `tests/test_compact_mode.py` | New — unit tests for registry and flag wiring |

---

## CompactRegistry

`src/rhmcp/tools_helpers/compact_registry.py`

Loads all tool modules onto a **shadow FastMCP** instance (never exposed to clients), captures the resulting `Tool` objects (which carry `name`, `description`, `parameters` schema, and `fn`), and provides three operations:

```python
class CompactRegistry:
    def load_from_modules(self, active_modules: set[str] | None) -> None:
        # Creates shadow FastMCP, registers all modules, stores _tool_manager._tools

    def list_tools(self, category: str = "") -> list[dict]:
        # Returns [{name, description_first_line}], optionally filtered by substring

    def describe_tool(self, name: str) -> dict:
        # Returns {name, description, input_schema} or {error: "..."}

    async def call_tool(self, name: str, arguments: dict) -> Any:
        # Dispatches to tool.run(arguments) — the FastMCP async runner
        # Raises ValueError if tool not found
```

**Why shadow FastMCP?** `mod.register(shadow)` is the existing registration contract every module honours. Reusing it means zero changes to any tool module and guaranteed schema extraction via FastMCP's own Pydantic introspection.

**Why `tool.run()`?** `Tool.run(arguments, context=None)` is FastMCP's internal async dispatch path. It handles sync/async tools uniformly. rhino_mcp tools do not use the FastMCP `Context` object — they call `plugin_client` directly — so `context=None` is safe for all 360 tools.

---

## Three Meta-Tools (registered on real FastMCP in compact mode)

```python
@mcp.tool()
def list_rhino_tools(category: str = "") -> list[dict]:
    """List all available Rhino tools with one-line descriptions."""

@mcp.tool()
def describe_rhino_tool(name: str) -> dict:
    """Get the full description and input schema for a specific Rhino tool."""

@mcp.tool()
async def call_rhino_tool(name: str, arguments: dict = {}) -> Any:
    """Call any Rhino tool by name with a dict of arguments."""
```

Token cost: ~1.5k for these 3 tools vs ~52k for 360 full schemas.

**Typical AI session flow in compact mode:**
1. `list_rhino_tools()` — scans available tools (~360 names + 1-line descriptions)
2. `describe_rhino_tool("execute_rhino_python")` — fetches full schema for the tools it needs
3. `call_rhino_tool("execute_rhino_python", {"code": "...", "verified_functions": [...]})` — executes

For tools the AI already knows well from training (e.g. `execute_rhino_python`), step 2 can be skipped.

---

## CLI & Environment Variable

```bash
# Compact mode — 3 meta-tools, ~1.5k tokens
rhino-mcp --compact

# Compact mode within a profile — even narrower registry
rhino-mcp --compact --profile core

# Via environment variable
RHMCP_COMPACT=1 rhino-mcp
```

`RHMCP_COMPACT` is truthy for any non-empty string value (`"1"`, `"true"`, `"yes"`).

Startup stderr message when compact is active:
```
Rhino MCP: compact mode — 3 meta-tools loaded (360 tools available on demand)
```

---

## `__init__.py` Changes

1. Add `--compact` argument to argparse (after `--profile`).
2. After resolving profile, if `--compact`:
   - Instantiate `CompactRegistry`, call `load_from_modules(active_modules)`
   - Skip the normal module registration loop
   - Register `list_rhino_tools`, `describe_rhino_tool`, `call_rhino_tool` on the real FastMCP, closing over the registry instance
3. Normal (non-compact) path is unchanged.

---

## Tests (`tests/test_compact_mode.py`)

All unit tests — no live Rhino required.

| Test | What it checks |
|------|----------------|
| `test_load_captures_tools` | `load_from_modules(None)` stores > 0 tools |
| `test_load_respects_profile` | `load_from_modules({"geometry"})` stores only geometry tools |
| `test_list_tools_returns_names_and_descriptions` | every entry has `name` and `description` keys |
| `test_list_tools_filters_by_category` | `list_tools("geometry")` only returns geometry entries |
| `test_describe_tool_known` | returns `name`, `description`, `input_schema` for a real tool |
| `test_describe_tool_unknown` | returns `{"error": "..."}` for unknown name |
| `test_call_tool_dispatches` | mocks `tool.run`; verifies it is called with correct args |
| `test_call_tool_unknown_raises` | raises `ValueError` for unknown tool name |
| `test_compact_flag_in_argparse` | `parse_args(["--compact"])` sets `compact=True` |
| `test_rhmcp_compact_env_var` | `RHMCP_COMPACT=1` env sets compact default to `True` |

---

## Token Budget Comparison

| Mode | Tools registered | ~Tokens |
|------|-----------------|---------|
| `full` | 360 | ~52k |
| `--profile core` | 194 | ~28k |
| `--compact` | 3 meta-tools | ~1.5k |
| `--compact --profile core` | 3 meta-tools (194 behind the scenes) | ~1.5k |

Per-tool schema fetch via `describe_rhino_tool`: ~150 tokens. A session that describes 5 tools costs ~2.25k total — still 23× cheaper than full profile.

---

## Out of Scope

- Hot-swapping profiles at runtime
- Streaming partial tool lists
- Per-tool caching / TTL
- Changes to any tool module
