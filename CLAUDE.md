# Rhino MCP — Development Guide

Version **0.20.0** exposes 358 tools for controlling Rhino 3D. See [AGENTS.md](AGENTS.md) for tool patterns, validation, error shapes, and version synchronization.

## Architecture

The Python server in `src/rhmcp/` exposes stdio or HTTP MCP. The C# plugin in `rhino_plugin/` executes commands inside Rhino over newline-delimited TCP JSON on port 1999. Non-loopback HTTP and plugin connections require TLS.

`tools_helpers/backend.py` routes between the plugin and `rhinocode`. Once dispatch starts, ambiguous outcomes return `EXECUTION_OUTCOME_UNKNOWN` without replay. `http_transport.py` handles identities and HTTP policy; `tool_runtime.py` handles tool grants, scopes, worker execution, concurrency, and telemetry. Keep workflow state in `workflow_state.py`, not module globals.

## Development setup

Run from the repository root:

```bash
uv sync --group dev

# Local stdio
uv run python -m rhmcp

# Local HTTP; use the bearer token printed at startup
uv run python -m rhmcp --transport http --host 127.0.0.1 --port 8000

# Non-integration tests; no Rhino required
uv run pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_gh_integration.py --ignore=tests/test_studio_pipeline_integration.py --ignore=tests/test_gh_intelligence_integration.py -q
uvx ruff check src/rhmcp --select=E,W,F --ignore=E501,E701,E402,E741

# Live integration; requires Rhino with the plugin loaded
uv run pytest tests/test_integration.py -v -m integration
```

## Adding a tool

Create a module under `src/rhmcp/tools/` with `register(mcp)` and `@mcp.tool()` annotations. Modules are discovered at startup subject to the selected profile. Validate inputs before dispatch, declare read-only behavior accurately, and assign `result` in embedded Python scripts. The runtime adds project/instance scope parameters to underlying tools.

## Configuration and deployment

See [.env.example](.env.example) and [secure operation](docs/secure-operation.md). Execution gates must be set in both Rhino and MCP environments. For containers, configure both HTTP and plugin TLS and the definitions directory as seen by Rhino.

`mcpize.yaml` contains deployment configuration, but it does not provision certificates. Hosted deployment requires adapting its environment/startup settings for non-loopback TLS and validating connectivity to Rhino. `/health` reports HTTP liveness, not Rhino readiness.

## Builds and releases

Follow the [0.20.0 upgrade guide](docs/upgrade-0.20.0.md) and [publishing checklist](rhino_plugin/PUBLISHING.md). Builds do not automatically install the plugin. The GitHub plugin release workflow is manually dispatched on a self-hosted macOS runner with Rhino; it is not an automatic release-on-tag pipeline.

## Latest installed verification

On 2026-10-04, the released **0.19.0** plugin bundle and server were installed locally (Rhino 8 `MacPlugIns` bundle and `/Users/Shared/rhino_mcp/plugin` match the release by content). No live Rhino session was started afterwards, so environment maps, script component port reshaping, and Grasshopper 2 placement remain compile-verified only. The last live ping and read-only round trip were on 2026-09-07 with 0.17.1 on Rhino **8.34.26223.11002**; see the [validation record](release/validation-0.19.0.md) for the 0.19.0 artifact checks. Recheck runtime status when needed; this is a dated observation.
