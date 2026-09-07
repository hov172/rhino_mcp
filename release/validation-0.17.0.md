# macOS installer 0.17.0 validation — 2026-09-07

- Installer and uninstaller: Apple notarization accepted; tickets stapled and validated; Gatekeeper accepted as Notarized Developer ID.
- Installer submission: 2e6589a2-6216-4173-a1ce-03e17584c228.
- Uninstaller submission: 24dd6f46-9ef8-4055-a0d5-e069598197f8 (also submitted by the build script).
- Both extracted runtimes: rhino-mcp 0.17.0, MCP SDK 1.29.1, all 358 tools registered.
- Apple Silicon and Intel (via Rosetta): MCP initialization and read-only live Rhino document query passed.
- Venv links/configuration target /Users/Shared/rhino_mcp; bundled plugin and dependencies match the release artifacts.
- 472 tests plus five subtests passed; lint, installer shell syntax, and whitespace checks passed.
- Installer was built and verified without replacing the live shared installation. A clean-machine installation test was not performed.

See SHA256SUMS-0.17.0 for final stapled package hashes.
