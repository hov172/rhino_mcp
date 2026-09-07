# macOS installer 0.17.0 validation — 2026-09-07

- Installer and uninstaller: Apple notarization accepted; tickets stapled and validated; Gatekeeper accepted as Notarized Developer ID.
- Installer submission: 4c3d931c-7caa-49e9-8961-735e046a942f.
- Uninstaller submission: a35d566a-162b-42bf-b610-eadc4ced2c95.
- Both extracted runtimes: rhino-mcp 0.17.0, MCP SDK 1.29.1, all 358 tools registered.
- Apple Silicon and Intel (via Rosetta): MCP initialization and read-only live Rhino document query passed.
- Venv links/configuration target /Users/Shared/rhino_mcp; bundled plugin and dependencies match the release artifacts.
- GitHub CI passed on Python 3.10, 3.11, and 3.12, including project timestamp compatibility.
- All packaged Python source files match the release source.
- 472 tests plus five subtests passed; lint, installer shell syntax, and whitespace checks passed.
- Installer was built and verified without replacing the live shared installation. A clean-machine installation test was not performed.

See SHA256SUMS-0.17.0 for final stapled package hashes.
