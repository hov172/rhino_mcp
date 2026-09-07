# Upgrading to 0.17.0

> Historical release guide. For current macOS installation, use the [0.17.1 upgrade guide](upgrade-0.17.1.md), which fixes plugin discovery and cached registration.

0.17.0 updates the Python server, Rhino plugin, and Docker image. Upgrade both server and plugin to obtain the dispatch controls and document recovery changes. The public tool count remains 358.

## Build and artifact status

The 0.17.0 release includes these artifacts (paths below are build outputs):

| Component | Output |
|---|---|
| Rhino plugin | `rhino_plugin/release/rhino-mcp.rhp` |
| Yak package | `rhino_plugin/release/rhino-mcp-0.17.0-rh8_17-any.yak` |
| Python wheel | `dist/rhino_mcp-0.17.0-py3-none-any.whl` |
| Python source distribution | `dist/rhino_mcp-0.17.0.tar.gz` |
| macOS universal installer | `release/rhino-mcp-0.17.0-universal-signed.pkg` |
| macOS uninstaller | `release/rhino-mcp-0.17.0-universal-uninstaller-signed.pkg` |
| Docker image | `rhino-mcp:0.17.0` and `rhino-mcp:latest` |

Download the packages from the [v0.17.0 GitHub release](https://github.com/hov172/rhino_mcp/releases/tag/v0.17.0). Building locally does not install the plugin or recreate containers. GitHub publication is separate from PyPI, Yak, and Docker registry publication; those registries are not updated by this release workflow. Generated binaries and Python distributions are gitignored.

To reproduce from the repository root:

```bash
uv sync --group dev
bash scripts/package-plugin.sh
uv build
docker build -t rhino-mcp:0.17.0 -t rhino-mcp:latest .
```

Plugin packaging requires .NET 8 and Rhino 8 on macOS. See [publishing](../rhino_plugin/PUBLISHING.md) for the release checklist.

## Install and configure

1. Save your work and fully quit Rhino. Identify the existing plugin installation in Rhino's plugin manager; replace it using the same manual or Yak installation method. Avoid duplicate copies. See [plugin installation](../rhino_plugin/README.md#upgrading).
2. Install the rebuilt `.rhp` or Yak package and update the Python environment from the matching wheel, or run `uv sync` for a source checkout. Restart the MCP client/server after changing its environment.
3. For remote HTTP, configure a PEM certificate/private key, allowed hostname, and a trusted client CA. For remote plugin connections, configure Rhino's PFX certificate and shared secret, and enable verified TLS in Python. Follow the exact [transport settings](secure-operation.md#tls). Previous plaintext remote configurations fail startup or connection checks.
4. If using Docker, recreate the service from the new image with certificate mounts and environment settings from the [Docker instructions](../README.md#path-b--docker-setup-with-claude-desktop). Existing containers keep their original image until recreated. Set `RHINO_MCP_GH_DIR` to the definitions directory as seen by Rhino.
5. Restart Rhino and run `MCPStatus`; confirm the installed plugin version in Rhino's plugin manager. Check Python's version with the command below, then initialize MCP and perform a read-only document query before testing mutations on a scratch document.

```bash
uv run python -c 'from importlib.metadata import version; print(version("rhino-mcp"))'
docker image inspect rhino-mcp:0.17.0 --format '{{json .Config.Labels}}'
```

## Client-visible changes

- `EXECUTION_OUTCOME_UNKNOWN` means dispatch may have run. Inspect Rhino before retrying; automatic replay and backend fallback are suppressed after sending begins.
- All underlying tools accept `project_id` and `rhino_id`. Compact mode passes these inside `call_rhino_tool` tool arguments. HTTP identities can restrict tool, project, and instance access.
- Concurrent mutations on the same instance within one MCP process return `RHINO_BUSY`. Project workflow state is in memory and does not isolate the shared Rhino document.
- Execution gates apply at dispatch, including script-backed tools. Set them in both process environments; they are not a code sandbox.
- Report exports identify HTML fallback and leave `pdf_url` empty. Missing metrics and partial pipeline/migration results are explicit.

See [secure operation](secure-operation.md) for recovery limits, scope limits, authentication, and result semantics.

## Verification recorded for this build

The local non-integration suite passed **472 tests plus five subtests**. Ruff passed; the release .NET build completed with zero warnings and errors. Python and Yak versions were checked against 0.17.0. Docker TLS smoke checks covered health, authentication, MCP initialization, discovery, and packaged Grasshopper assets.

Live Rhino integration was not verified. Before operational use, validate TLS listener startup, instance routing, and failed mutation recovery on a scratch document. Document undo cannot reverse external file/network effects or all third-party state.

The macOS installer is built separately with `bash scripts/build-installer.sh` after the wheel. Its Apple Silicon and Intel runtimes are checked for version 0.17.0, MCP initialization metadata, and all 358 tools before signing. The package constrains the MCP SDK to 1.x because SDK 2.x removes the FastMCP import used by this server. See [installer signing and notarization](../rhino_plugin/PUBLISHING.md#macos-installer).

Installer payload verification also exercised MCP initialization and a read-only Rhino document query from each extracted runtime (Apple Silicon and Intel via Rosetta). Both passed and reported application version 0.17.0. This verifies the packaged runtime and plugin connection; it does not replace a clean-machine installation test.

On 2026-09-07, both macOS packages received Apple notarization acceptance. Their tickets were stapled and validated, and Gatekeeper accepted both as Notarized Developer ID. Final package hashes are in `release/SHA256SUMS-0.17.0`.
