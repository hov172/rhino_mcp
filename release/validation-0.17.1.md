# macOS installer 0.17.1 validation — 2026-09-07

- Installer and uninstaller: Apple notarization accepted; tickets stapled and validated; Gatekeeper accepted as Notarized Developer ID.
- Installer submission: c7ab549b-6044-4edf-a995-5634bf131871.
- Uninstaller submission: e0ebf0e3-5d26-4bf9-b399-45e3da28ef64.
- Both extracted runtimes: rhino-mcp 0.17.1, MCP SDK 1.29.1, all 358 tools registered.
- Apple Silicon and Intel (via Rosetta): MCP protocol initialization reports 0.17.1; unavailable-backend error handling passed with Rhino closed.
- Packaged installer helper, using the packaged Apple Silicon runtime and real plugin payload: correct bundle installation, cached-path repair, and legacy backup passed in a temporary user directory.
- Venv links/configuration target /Users/Shared/rhino_mcp; bundled plugin and dependencies match the release artifacts.
- C# plugin assembly reports 0.17.1 (assembly version 0.17.1.0); Yak and Python metadata match.
- Rebuilt Docker image application runtime and MCP initialization metadata report 0.17.1.
- GitHub CI passed on Python 3.10, 3.11, and 3.12.
- All packaged Python source files and the installer helper match the release source.
- 476 tests plus five subtests passed; lint, installer shell syntax, and whitespace checks passed.
- Installer build and initial payload checks did not replace the live installation; Rhino was closed during those checks. Subsequent installed-system verification is recorded below. A clean-machine installation test was not performed.

## Installed-system verification — 2026-09-07

- `/Users/Shared/rhino_mcp/VERSION`, installed Python package metadata, and MCP initialization all report 0.17.1.
- The shared plugin payload and all seven files in the installed Rhino 8 `MacPlugIns/rhino-mcp.rhp` bundle match the released plugin and dependencies by SHA-256.
- Rhino’s cached assembly path points to `8.0/MacPlugIns/rhino-mcp.rhp/rhino-mcp.rhp`.
- Live TCP `ping` at `127.0.0.1:1999` returned `status: ok`, plugin version `0.17.1`, and Rhino version `8.34.26223.11002`.
- The installed Apple Silicon Python runtime initialized an MCP stdio session as 0.17.1 and successfully called `get_document_summary` through `call_rhino_tool`, returning `ok: true` and `backend: plugin`.
- These checks establish local installation, listener availability, and a read-only end-to-end request. They do not establish mutation recovery, every tool’s behavior, remote TLS, or a running Docker deployment.

See SHA256SUMS-0.17.1 for final stapled package hashes.
