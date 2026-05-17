# Rhino MCP — Development Guide

MCP server that exposes 347 tools for controlling Rhino 3D from AI clients (Claude, Cursor, Codex, etc.).

## Project Structure

```
src/rhmcp/
├── __init__.py          # Server entry point, HTTP/stdio transport setup
├── __main__.py          # python -m rhmcp entrypoint
├── telemetry.py         # Optional usage telemetry
├── tools/               # One module per tool group (auto-loaded)
├── tools_helpers/       # Shared utilities (plugin client, rhinocode, backend)
└── data/                # prompts.yml, rhinoscript docs
rhino_plugin/            # Rhino-side C# plugin (MCPStart command)
tests/                   # pytest integration tests (require live Rhino)
```

## Architecture

The server has two sides:

- **MCP side** (`src/rhmcp/`) — Python, runs on developer's machine or Docker. Exposes tools over stdio or HTTP.
- **Rhino plugin side** (`rhino_plugin/`) — C# plugin installed into Rhino 8. Listens on TCP port 1999 and executes commands inside Rhino.

Communication between the two is via the plugin client (`tools_helpers/plugin_client.py`) over a TCP socket, or via the `rhinocode` CLI for script execution.

## Development Setup

```bash
# Install dependencies
uv sync

# Run against a local Rhino instance (stdio)
uv run python -m rhmcp

# Run as HTTP server
uv run python -m rhmcp --transport http --host 0.0.0.0 --port 8000

# Run tests (requires Rhino running with MCPStart)
uv run pytest tests/ -m integration
```

## Adding a Tool

1. Create or edit a module under `src/rhmcp/tools/`.
2. Define a `register(mcp: FastMCP)` function and decorate tools with `@mcp.tool()`.
3. The server auto-discovers and loads all modules in `tools/` at startup — no imports needed elsewhere.

## Environment Variables

See `.env.example` for the full list. Key ones for development:

- `RHINO_MCP_HOST` / `RHINO_MCP_PORT` — where the Rhino plugin is listening
- `RHINO_MCP_BACKEND` — `auto` (default), `rhinocode`, or `plugin`
- `ANTHROPIC_API_KEY` — required for urban design language and pipeline tools

## Deployment (MCPize)

```bash
mcpize deploy
```

The `mcpize.yaml` manifest configures the build and start commands. The server exposes a `/health` endpoint at `GET /health` used by Docker and Cloud Run health checks.

## Version & Release

Version is set in `pyproject.toml`, `rhino_plugin/`, and Docker image label — keep them in sync.
Releases are tagged `vX.Y.Z` and built via GitHub Actions.
