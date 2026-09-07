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
- Installer was built and verified without replacing the live shared installation. A clean-machine installation test and live 0.17.1 Rhino plugin query were not performed; Rhino was closed during final package verification.

See SHA256SUMS-0.17.1 for final stapled package hashes.
