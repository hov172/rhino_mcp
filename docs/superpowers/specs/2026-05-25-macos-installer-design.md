# macOS Installer Package — Design Spec
**Project:** rhino-mcp  
**Date:** 2026-05-25  
**Status:** Approved

---

## Goal

Produce a signed, notarized macOS `.pkg` installer that any studio can double-click to deploy rhino-mcp across one or many machines with multiple user accounts. A single build script (`scripts/build-installer.sh`) re-generates the package on each release from one source-of-truth version in `pyproject.toml`.

---

## Architecture Overview

```
scripts/
├── build-installer.sh                         ← master build + sign + notarize script
└── installer/
    ├── preinstall                              ← system guard checks
    ├── postinstall                             ← configures current console user
    ├── rhino-mcp-configure.sh                  ← per-user AI client configurator
    ├── com.ayala.rhino-mcp.configure.plist     ← LaunchAgent template
    └── resources/
        ├── welcome.html
        ├── license.txt
        └── background.png

Output: release/rhino-mcp-<version>-installer.pkg
```

The installer is a **notarized product archive** (`productbuild`) wrapping two component packages built with `pkgbuild`. Signed with the `Jay_Signaro` installer signing identity and notarized via `xcrun notarytool`.

---

## Component Packages

### Component 1: `rhino-mcp-server.pkg`
Identifier: `com.ayala.rhino-mcp.server`

| Source (build-time) | Destination on target machine | Permissions |
|---|---|---|
| `src/rhmcp/` + pre-baked `.venv/` | `/Users/Shared/rhino_mcp/` | `755`, `root:wheel`, world-readable |
| `rhino_plugin/release/rhino-mcp.rhp` | `/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/rhino-mcp/rhino-mcp.rhp` | `644` |
| `scripts/installer/rhino-mcp-configure.sh` | `/usr/local/bin/rhino-mcp-configure` | `755` |

Includes `preinstall` and `postinstall` scripts.

### Component 2: `rhino-mcp-launchagent.pkg`
Identifier: `com.ayala.rhino-mcp.launchagent`

| Source | Destination |
|---|---|
| `com.ayala.rhino-mcp.configure.plist` | `/Library/LaunchAgents/com.ayala.rhino-mcp.configure.plist` |

---

## Installation Paths & Rationale

- **`/Users/Shared/rhino_mcp/`** — world-readable, survives user account changes, single copy of the Python venv for all accounts.
- **`/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/`** — Rhino scans this system-wide path in addition to `~/Library/…`, so all user accounts pick up the plugin without per-user registration.
- **`/Library/LaunchAgents/`** — LaunchAgents here load for every user at GUI login (Aqua session), triggering per-user AI client configuration automatically.
- **`/usr/local/bin/rhino-mcp-configure`** — manually runnable by any user to re-run or repair their AI client config.

---

## MCP Server Command (written to all AI client configs)

```json
{
  "command": "/Users/Shared/rhino_mcp/.venv/bin/python",
  "args": ["-m", "rhmcp"]
}
```

No `uv`, no PATH dependency. The venv is pre-built at package-build time and ships inside the installer.

---

## Per-User AI Client Configuration

### `rhino-mcp-configure.sh` — runs as the target user

Idempotent. Uses version sentinel at `~/.rhino-mcp-configured` to skip on repeat runs and re-run on version upgrades.

All output appended to `~/Library/Logs/rhino-mcp-configure.log`.

| Client | Detection | Config file | Format |
|---|---|---|---|
| Claude Desktop | `/Applications/Claude.app` exists | `~/Library/Application Support/Claude/claude_desktop_config.json` | JSON `mcpServers` |
| Claude Code (CLI) | `~/.claude/` dir exists | `~/.claude/claude_desktop_config.json` | JSON `mcpServers` |
| ChatGPT Desktop | `/Applications/ChatGPT.app` exists | `~/Library/Application Support/ChatGPT/model_settings.json` | JSON `mcpServers` |
| Codex CLI | `~/.codex/` dir exists | `~/.codex/config.yaml` | YAML `mcpServers` |
| Codex Desktop | `/Applications/Codex.app` exists | `~/Library/Application Support/Codex/model_settings.json` | JSON `mcpServers` (path to be verified against actual app at implementation time) |

**JSON merging:** Python (from the bundled venv) reads → merges `mcpServers.rhino` key → writes. Preserves all existing keys. On JSON parse error, backs up broken file as `config.json.bak` before writing fresh.

**YAML merging (Codex CLI):** `pyyaml` (included in venv) for the same read-merge-write pattern.

### LaunchAgent (`com.ayala.rhino-mcp.configure.plist`)

- `RunAtLoad = true`
- `LimitLoadToSessionType = Aqua` (GUI login only, not SSH)
- Program: `/usr/local/bin/rhino-mcp-configure`
- `StandardOutPath` / `StandardErrorPath`: `~/Library/Logs/rhino-mcp-configure.log`
- Exits immediately if sentinel `~/.rhino-mcp-configured` contains current version

### `postinstall` script

Detects console user via `stat /dev/console`, then runs configure under that user's identity immediately via `launchctl asuser <uid> /usr/local/bin/rhino-mcp-configure`. Installing admin is configured without needing to log out.

---

## Build Script (`scripts/build-installer.sh`)

### Inputs

| Source | Value |
|---|---|
| Version | Parsed from `pyproject.toml` |
| Signing identity | `INSTALLER_SIGNING_ID` env var (default: `"Jay_Signaro"`) |
| Apple ID | `APPLE_ID` env var |
| App-specific password | `APPLE_APP_PASSWORD` env var |
| Team ID | `APPLE_TEAM_ID` env var |

Env vars loaded from `.env` if present (never committed to git).

### Build Sequence

```
1.  Read VERSION from pyproject.toml
2.  scripts/build-plugin.sh          → dotnet build Release
3.  scripts/package-plugin.sh        → release/rhino-mcp.rhp
4.  Clean /tmp/rhino-mcp-build/
5.  Stage payload tree under /tmp/rhino-mcp-build/
6.  uv venv + uv pip install → pre-baked .venv in payload
7.  pkgbuild → rhino-mcp-server.pkg
8.  pkgbuild → rhino-mcp-launchagent.pkg
9.  Generate distribution.xml from version + component refs
10. productbuild → rhino-mcp-$VERSION-unsigned.pkg
11. productsign --sign "Jay_Signaro" → rhino-mcp-$VERSION.pkg
12. xcrun notarytool submit --wait → prints UUID, waits for Apple
13. xcrun stapler staple → ticket embedded
14. cp → release/rhino-mcp-$VERSION-installer.pkg
```

### `distribution.xml` (auto-generated)

- Title: `Rhino MCP v<VERSION>`
- Minimum macOS: 13 (Ventura)
- Soft check: warns if `/Applications/Rhino 8.app` not found (does not block install)
- Both component packages listed; "Customize" option exposed in installer UI

---

## Error Handling

### `preinstall`
- macOS < 13 → exits 1, blocks install with message
- Rhino 8 not found → warning logged, install proceeds (MCP server still usable)

### `postinstall`
- Plugin directory creation failure → exits 1 (critical)
- AI client config failure → logged, skipped, does not block install
- No console user detected (headless) → logs "Run rhino-mcp-configure manually"

### `rhino-mcp-configure.sh`
- Each client block isolated — one failure does not skip others
- JSON parse error → backup + fresh write
- All errors → `~/Library/Logs/rhino-mcp-configure.log`

### `build-installer.sh`
- `set -euo pipefail` — fails fast on any step
- Pre-flight checks: `dotnet`, `yak`, `uv`, `pkgbuild`, `productbuild`, `xcrun` present
- `APPLE_ID` / `APPLE_APP_PASSWORD` / `APPLE_TEAM_ID` must be set before notarization step
- Prints notarytool UUID for manual lookup on timeout

---

## Testing

`scripts/test-installer.sh` (optional helper):
- Runs `installer -pkg release/rhino-mcp-$VERSION-installer.pkg -target /` in a VM or test user
- Verifies `/Users/Shared/rhino_mcp/.venv/bin/python -m rhmcp --help` exits 0
- Verifies `/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/rhino-mcp/rhino-mcp.rhp` exists
- Verifies Claude Desktop config contains `rhino` key (if Claude.app present)

---

## Version Matching

Version is read from a single source: `pyproject.toml`. The build script propagates it to:
- `distribution.xml` title and `version` attribute
- `pkgbuild --version` for both component packages
- Output filename `rhino-mcp-<version>-installer.pkg`
- Sentinel file written to `~/.rhino-mcp-configured`

The Rhino plugin version (in `manifest.yml`) must match `pyproject.toml` — the build will fail if `package-plugin.sh` produces a `.yak` with a mismatched version (the yak filename embeds the version and the build script asserts it matches).

---

## Files Added to Repo

```
scripts/build-installer.sh
scripts/installer/preinstall
scripts/installer/postinstall
scripts/installer/rhino-mcp-configure.sh
scripts/installer/com.ayala.rhino-mcp.configure.plist
scripts/installer/resources/welcome.html
scripts/installer/resources/license.txt
scripts/test-installer.sh
.env.example                    (adds APPLE_ID, APPLE_APP_PASSWORD, APPLE_TEAM_ID)
```

`release/*.pkg` and `.env` remain in `.gitignore`.
