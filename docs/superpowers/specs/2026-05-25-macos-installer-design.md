# macOS Installer Package — Design Spec
**Project:** rhino-mcp  
**Date:** 2026-05-25  
**Status:** Approved (corrected after senior dev review 2026-05-25)

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
    ├── rhino-mcp-configure.sh                  ← per-user configurator (AI clients + Rhino plugin)
    ├── com.ayala.rhino-mcp.configure.plist     ← LaunchAgent template
    └── resources/
        ├── welcome.html
        ├── license.txt
        └── background.png

Output: release/rhino-mcp-<version>-arm64-installer.pkg
```

The installer is a **notarized product archive** (`productbuild`) wrapping two component packages built with `pkgbuild`. Signed with `"Developer ID Installer: Jesus Ayala (N859JA9UCJ)"` and notarized via `xcrun notarytool`.

> **Architecture note:** The bundled `.venv` is compiled for the build machine's architecture (arm64). For Intel or mixed fleets, a separate build is required. The output filename includes `-arm64` to make this explicit.

---

## Component Packages

### Component 1: `rhino-mcp-server.pkg`
Identifier: `com.ayala.rhino-mcp.server`

| Source (build-time) | Destination on target machine | Permissions |
|---|---|---|
| `src/rhmcp/` + pre-baked `.venv/` | `/Users/Shared/rhino_mcp/` | `755`, `root:wheel`, world-readable |
| `rhino_plugin/release/rhino-mcp.rhp` | `/Users/Shared/rhino_mcp/plugin/rhino-mcp.rhp` | `644` |
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
- **`/Users/Shared/rhino_mcp/plugin/rhino-mcp.rhp`** — staging location for the Rhino plugin. Rhino does not reliably auto-scan `/Library/Application Support/McNeel/` (that system-wide path does not exist by default on macOS). Instead, `rhino-mcp-configure.sh` copies the `.rhp` to each user's own `~/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/` on first login — matching the path that `install-plugin-local.sh` already uses successfully.
- **`/Library/LaunchAgents/`** — LaunchAgents here load for every user at GUI login (Aqua session), triggering per-user Rhino plugin copy and AI client configuration automatically.
- **`/usr/local/bin/rhino-mcp-configure`** — manually runnable by any user to re-run or repair their configuration.

---

## MCP Server Command (written to all AI client configs)

```json
{
  "command": "/Users/Shared/rhino_mcp/.venv/bin/python",
  "args": ["-m", "rhmcp"]
}
```

No `uv`, no PATH dependency. The venv is pre-built at package-build time at the exact final install path and ships inside the installer.

---

## Per-User Configuration

### `rhino-mcp-configure.sh` — runs as the target user

Idempotent. Uses version sentinel at `~/.rhino-mcp-configured` to skip on repeat runs and re-run on version upgrades.

All output appended to `~/Library/Logs/rhino-mcp-configure.log`.

**Handles two responsibilities per user:**
1. Copy Rhino plugin to user's Plug-ins directory
2. Configure all detected AI clients

#### Rhino Plugin Copy

```
/Users/Shared/rhino_mcp/plugin/rhino-mcp.rhp
  → ~/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/rhino-mcp.rhp
```

Creates the destination directory if it doesn't exist. Overwrites on version upgrade (sentinel mismatch).

#### AI Client Configuration

| Client | Detection | Config file(s) | Format |
|---|---|---|---|
| Claude Desktop | `/Applications/Claude.app` exists | `~/Library/Application Support/Claude/claude_desktop_config.json` | JSON — merge `mcpServers.rhino` |
| Claude Code (CLI) | `~/.claude/` dir exists | `~/.claude/mcp.json` (server def) + `~/.claude/settings.json` (`enabledMcpjsonServers` array) | JSON — merge both files |
| ChatGPT Desktop | `/Applications/ChatGPT.app` exists | `~/Library/Application Support/ChatGPT/model_settings.json` *(path unverified — app not installed on build machine; log warning if parse fails rather than hard-fail)* | JSON — merge `mcpServers.rhino` |
| Codex CLI | `~/.codex/` dir exists | `~/.codex/config.toml` *(MCP server key unconfirmed in Codex CLI — detect and skip gracefully if key absent; verify at implementation time)* | TOML — use Python `tomllib` (read) + `tomli_w` (write) |
| Codex Desktop | `/Applications/Codex.app` exists | `~/Library/Application Support/Codex/model_settings.json` *(path unverified — verify at implementation time)* | JSON — merge `mcpServers.rhino` |

**JSON merging:** Python (from the bundled venv) reads → merges key → writes. Preserves all existing keys. On JSON parse error, backs up broken file as `<name>.bak` before writing fresh.

**TOML merging (Codex CLI):** `tomllib` (stdlib, Python 3.11+) for reading; `tomli_w` (add as venv dependency) for writing. Skip if the MCP server key is not part of the Codex CLI schema.

**Claude Code specifics:** Two files must be updated together:
- `~/.claude/mcp.json` — add/update `mcpServers.rhino` entry
- `~/.claude/settings.json` — ensure `"rhino"` is present in the `enabledMcpjsonServers` array

### LaunchAgent (`com.ayala.rhino-mcp.configure.plist`)

- `RunAtLoad = true`
- `LimitLoadToSessionType = Aqua` (GUI login only, not SSH)
- Program: `/usr/local/bin/rhino-mcp-configure`
- `StandardOutPath` / `StandardErrorPath`: `~/Library/Logs/rhino-mcp-configure.log`
- Exits immediately if sentinel `~/.rhino-mcp-configured` contains current version

### `postinstall` script

Detects console user via `stat -f "%Su" /dev/console`, resolves their UID via `id -u`, then runs the configure script under that user's identity via:

```bash
launchctl asuser "$CONSOLE_UID" sudo -u "$CONSOLE_USER" /usr/local/bin/rhino-mcp-configure
```

Installing admin is fully configured without needing to log out. If no console user is detected (headless install), logs: "Run `rhino-mcp-configure` manually to configure AI clients and install the Rhino plugin."

---

## Build Script (`scripts/build-installer.sh`)

### Inputs

| Source | Value |
|---|---|
| Version | Parsed from `pyproject.toml` |
| Signing identity | `INSTALLER_SIGNING_ID` env var (default: `"Developer ID Installer: Jesus Ayala (N859JA9UCJ)"`) |
| Apple ID | `APPLE_ID` env var |
| App-specific password | `APPLE_APP_PASSWORD` env var |
| Team ID | `APPLE_TEAM_ID` env var |

Env vars loaded from `.env` if present (never committed to git).

### Build Sequence

```
1.  Read VERSION from pyproject.toml
2.  scripts/build-plugin.sh              → dotnet build Release
3.  scripts/package-plugin.sh            → release/rhino-mcp.rhp
4.  Assert yak-output version == VERSION (fail if mismatch)
5.  Create /Users/Shared/rhino_mcp/ on build machine (world-writable, safe)
6.  uv venv /Users/Shared/rhino_mcp/.venv
7.  uv pip install <repo-root> → venv at exact final install path (no shebang mismatch)
8.  Copy src/rhmcp/ → /Users/Shared/rhino_mcp/src/
9.  Copy release/rhino-mcp.rhp → /Users/Shared/rhino_mcp/plugin/
10. Clean /tmp/rhino-mcp-build/ and stage payload from /Users/Shared/rhino_mcp/
11. pkgbuild → rhino-mcp-server.pkg      (with preinstall/postinstall scripts)
12. pkgbuild → rhino-mcp-launchagent.pkg
13. Generate distribution.xml from VERSION + component refs
14. productbuild → rhino-mcp-$VERSION-arm64-unsigned.pkg
15. productsign --sign "Developer ID Installer: Jesus Ayala (N859JA9UCJ)"
         → rhino-mcp-$VERSION-arm64.pkg
16. xcrun notarytool submit --wait       → prints UUID, waits for Apple ticket
17. xcrun stapler staple                 → ticket embedded in .pkg
18. cp → release/rhino-mcp-$VERSION-arm64-installer.pkg
```

> **Step 5–9 rationale:** Building the venv directly at `/Users/Shared/rhino_mcp/.venv` (the exact final install path) avoids absolute-path shebang mismatches in venv scripts. `/Users/Shared/` is world-writable on macOS by default, so no `sudo` is needed. The build machine's own `/Users/Shared/rhino_mcp/` can remain after the build — it is a valid local install for the developer.

### `distribution.xml` (auto-generated)

- Title: `Rhino MCP v<VERSION>`
- Minimum macOS: 13 (Ventura)
- Soft check: warns if `/Applications/Rhino 8.app` not found (does not block install)
- Both component packages listed; "Customize" option exposed in installer UI

---

## Error Handling

### `preinstall`
- macOS < 13 → exits 1, blocks install with message
- Rhino 8 not found → warning logged, install proceeds (MCP server still usable without Rhino locally)

### `postinstall`
- Rhino plugin staging copy failure → exits 1 (critical — plugin source must be in place)
- AI client config failure → logged, skipped, does not block install
- No console user detected (headless) → logs manual instruction, exits 0

### `rhino-mcp-configure.sh`
- Each client block isolated — one failure does not skip others
- JSON parse error → backup + fresh write
- TOML parse error (Codex CLI) → log warning, skip Codex CLI config
- Unrecognised ChatGPT/Codex Desktop config format → log "path unverified", skip
- All errors → `~/Library/Logs/rhino-mcp-configure.log`

### `build-installer.sh`
- `set -euo pipefail` — fails fast on any step
- Pre-flight checks: `dotnet`, `yak`, `uv`, `pkgbuild`, `productbuild`, `xcrun` present
- Version assertion: yak output filename must contain `$VERSION` (step 4)
- `APPLE_ID` / `APPLE_APP_PASSWORD` / `APPLE_TEAM_ID` must be set before notarization step
- Prints notarytool UUID for manual lookup on timeout

---

## Testing

`scripts/test-installer.sh` (optional helper):
- Runs `installer -pkg release/rhino-mcp-$VERSION-arm64-installer.pkg -target /` in a VM or test user
- Verifies `/Users/Shared/rhino_mcp/.venv/bin/python -m rhmcp --help` exits 0
- Verifies `/Users/Shared/rhino_mcp/plugin/rhino-mcp.rhp` exists
- Verifies `~/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/rhino-mcp.rhp` exists for current user
- Verifies `~/.claude/mcp.json` contains `rhino` key (if `~/.claude/` present)
- Verifies Claude Desktop config contains `rhino` key (if `Claude.app` present)

---

## Version Matching

Version is read from a single source: `pyproject.toml`. The build script propagates it to:
- `distribution.xml` title and `version` attribute
- `pkgbuild --version` for both component packages
- Output filename `rhino-mcp-<version>-arm64-installer.pkg`
- Sentinel file written to `~/.rhino-mcp-configured`

The Rhino plugin version (in `manifest.yml`) must match `pyproject.toml` — the build asserts the yak output filename contains `$VERSION` and fails if not.

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

---

## Open Items (resolve at implementation time)

| # | Item |
|---|---|
| 1 | Verify ChatGPT Desktop MCP config path (`model_settings.json` assumed) |
| 2 | Verify Codex Desktop MCP config path and format |
| 3 | Confirm whether Codex CLI `config.toml` supports an MCP server key at all; if not, skip that block entirely |
| 4 | Add `tomli_w` to `pyproject.toml` dependencies (needed for Codex CLI TOML writing) |
