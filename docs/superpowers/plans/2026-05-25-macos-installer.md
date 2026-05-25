# macOS Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a signed, notarized macOS `.pkg` installer that deploys the rhino-mcp server to `/Users/Shared/rhino_mcp/`, installs the Rhino plugin per-user, and auto-configures Claude Desktop, Claude Code CLI, ChatGPT Desktop, and Codex Desktop.

**Architecture:** Two component packages (`pkgbuild`) assembled into a product archive (`productbuild`), signed with Developer ID Installer, and notarized via `xcrun notarytool`. A LaunchAgent in `/Library/LaunchAgents/` runs `rhino-mcp-configure` at each user's first GUI login. The MCP server runs from a portable Python venv built at its final install path (`/Users/Shared/rhino_mcp/.venv/`) using a bundled full Python runtime (`/Users/Shared/rhino_mcp/python/`) so no Python installation is required on target machines.

**Tech Stack:** bash, macOS `pkgbuild`/`productbuild`/`productsign`/`xcrun notarytool`, `uv` (build-time only), Python 3.13 (bundled), `python3 -m venv`, LaunchAgent plist

**Spec:** `docs/superpowers/specs/2026-05-25-macos-installer-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `.gitignore` | Modify | Add `release/*.pkg`, `release/*-unsigned.pkg`, `.env` |
| `.env.example` | Modify | Add `APPLE_ID`, `APPLE_APP_PASSWORD`, `APPLE_TEAM_ID`, `INSTALLER_SIGNING_ID` |
| `scripts/installer/preinstall` | Create | macOS version guard (blocks install on < 13) |
| `scripts/installer/postinstall` | Create | Set permissions + trigger configure for console user |
| `scripts/installer/rhino-mcp-configure.sh` | Create | Per-user: Rhino plugin copy + AI client JSON config |
| `scripts/installer/com.ayala.rhino-mcp.configure.plist` | Create | LaunchAgent — runs configure at each GUI login |
| `scripts/installer/resources/welcome.html` | Create | Installer welcome screen |
| `scripts/installer/resources/license.txt` | Create | MIT license displayed during install |
| `scripts/build-installer.sh` | Create | Master build/sign/notarize script (18-step pipeline) |
| `scripts/test-installer.sh` | Create | Post-install verification (run as root after install) |

---

## Task 1: Update `.gitignore` and `.env.example`

**Files:**
- Modify: `.gitignore`
- Modify: `.env.example`

- [ ] **Step 1: Add pkg patterns to .gitignore**

The existing `.gitignore` covers `rhino_plugin/release/` and `.venv/` but not `release/*.pkg` at the repo root, and doesn't exclude `.env`. Add these lines at the bottom of `.gitignore`:

```
# macOS installer build artifacts
release/*.pkg
release/*-unsigned.pkg
.env
```

- [ ] **Step 2: Add notarization env vars to .env.example**

Append to `.env.example` (after all existing content):

```bash

# macOS installer signing and notarization
# Required to run scripts/build-installer.sh
INSTALLER_SIGNING_ID=Developer ID Installer: Jesus Ayala (N859JA9UCJ)
APPLE_ID=ayala.solutions@gmail.com
APPLE_APP_PASSWORD=      # App-specific password from appleid.apple.com
APPLE_TEAM_ID=N859JA9UCJ # Found in App Store Connect > Membership
```

- [ ] **Step 3: Verify .gitignore works**

```bash
cd /Users/helpdesk/Developer/GitHub/rhino_mcp
git check-ignore -v release/rhino-mcp-0.15.1-arm64-installer.pkg
```

Expected output contains `release/*.pkg`.

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.example
git commit -m "chore: add pkg gitignore patterns and notarization env vars"
```

---

## Task 2: `preinstall` — System Guard

**Files:**
- Create: `scripts/installer/preinstall`

- [ ] **Step 1: Create the preinstall script**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Block install on macOS < 13 (Ventura)
OS_VERSION=$(sw_vers -productVersion)
OS_MAJOR=$(echo "$OS_VERSION" | cut -d. -f1)
if [ "$OS_MAJOR" -lt 13 ]; then
    echo "ERROR: rhino-mcp requires macOS 13 Ventura or later (found $OS_VERSION)." >&2
    exit 1
fi

# Warn (do not block) if Rhino 8 is absent
if [ ! -d "/Applications/Rhino 8.app" ]; then
    echo "WARNING: Rhino 8 not found at /Applications/Rhino 8.app." >&2
    echo "         The MCP server will install but the Rhino plugin cannot load." >&2
fi

exit 0
```

Save to `scripts/installer/preinstall` (no `.sh` extension — pkgbuild requires this exact name).

- [ ] **Step 2: Mark executable**

```bash
chmod +x scripts/installer/preinstall
```

- [ ] **Step 3: Smoke-test the guard logic**

```bash
bash scripts/installer/preinstall
echo "Exit: $?"
```

Expected: exits 0 (macOS 15 is ≥ 13). If Rhino 8 is not installed you'll see the warning on stderr; exit is still 0.

- [ ] **Step 4: Commit**

```bash
git add scripts/installer/preinstall
git commit -m "feat(installer): add preinstall macOS version guard"
```

---

## Task 3: `postinstall` — Permissions + Configure Trigger

**Files:**
- Create: `scripts/installer/postinstall`

- [ ] **Step 1: Create the postinstall script**

```bash
#!/usr/bin/env bash
set -euo pipefail

# World-readable/executable BEFORE configure calls the venv Python
chmod -R a+rX /Users/Shared/rhino_mcp/

# Detect the GUI user at the console (postinstall always runs as root)
CONSOLE_USER=$(stat -f "%Su" /dev/console)

# Skip on headless installs or if no user session exists
if [ -z "$CONSOLE_USER" ] || [ "$CONSOLE_USER" = "root" ]; then
    echo "No GUI session detected — run /usr/local/bin/rhino-mcp-configure" \
         "manually to configure AI clients and install the Rhino plugin." >&2
    exit 0
fi

# Run configure as the installing user; failure is non-fatal (LaunchAgent handles it)
sudo -u "$CONSOLE_USER" -H /usr/local/bin/rhino-mcp-configure || true

exit 0
```

Save to `scripts/installer/postinstall` (no `.sh` extension).

- [ ] **Step 2: Mark executable**

```bash
chmod +x scripts/installer/postinstall
```

- [ ] **Step 3: Verify the stat command works on this machine**

```bash
stat -f "%Su" /dev/console
```

Expected: your username (e.g. `helpdesk`).

- [ ] **Step 4: Commit**

```bash
git add scripts/installer/postinstall
git commit -m "feat(installer): add postinstall permissions + configure trigger"
```

---

## Task 4: `rhino-mcp-configure.sh` — Per-User Configurator

This is the largest script. It runs as the target user (from postinstall or LaunchAgent), installs the Rhino plugin to the user's Rhinoceros folder, and merges the MCP server entry into each detected AI client's config file.

**Files:**
- Create: `scripts/installer/rhino-mcp-configure.sh`

- [ ] **Step 1: Create the configure script**

```bash
#!/usr/bin/env bash
set -euo pipefail

SHARED_DIR="/Users/Shared/rhino_mcp"
PYTHON="$SHARED_DIR/.venv/bin/python"
SENTINEL="$HOME/.rhino-mcp-configured"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/rhino-mcp-configure.log"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# Read installed version — missing means corrupted install, re-run unconditionally
if [ -f "$SHARED_DIR/VERSION" ]; then
    INSTALLED_VERSION=$(cat "$SHARED_DIR/VERSION")
else
    log "WARNING: $SHARED_DIR/VERSION not found — running configure unconditionally"
    INSTALLED_VERSION="unknown"
fi

# Idempotency: skip if already configured for this version
if [ -f "$SENTINEL" ] && [ "$INSTALLED_VERSION" != "unknown" ]; then
    if [ "$(cat "$SENTINEL")" = "$INSTALLED_VERSION" ]; then
        log "Already configured for v$INSTALLED_VERSION — skipping"
        exit 0
    fi
fi

log "=== rhino-mcp configure v${INSTALLED_VERSION} for ${USER:-$(id -un)} ==="

# ── 1. Rhino plugin ──────────────────────────────────────────────────────────
PLUGIN_SRC="$SHARED_DIR/plugin/rhino-mcp.rhp"
PLUGIN_DST="$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/rhino-mcp.rhp"

if [ -f "$PLUGIN_SRC" ]; then
    mkdir -p "$(dirname "$PLUGIN_DST")"
    cp "$PLUGIN_SRC" "$PLUGIN_DST"
    log "Rhino plugin installed: $PLUGIN_DST"
else
    log "ERROR: Plugin source not found: $PLUGIN_SRC"
fi

# ── Helper: merge mcpServers.rhino into a JSON config (creates if absent) ────
# Usage: merge_mcp_json <config_path>
merge_mcp_json() {
    local config_path="$1"
    mkdir -p "$(dirname "$config_path")"
    "$PYTHON" - "$config_path" <<'PYEOF'
import json, sys, os, shutil

config_path = sys.argv[1]
entry = {
    "command": "/Users/Shared/rhino_mcp/.venv/bin/python",
    "args": ["-m", "rhmcp"]
}

if os.path.exists(config_path):
    try:
        with open(config_path) as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, ValueError):
        shutil.copy(config_path, config_path + ".bak")
        print(f"  Backed up broken JSON to {config_path}.bak", flush=True)
        cfg = {}
else:
    cfg = {}

cfg.setdefault("mcpServers", {})["rhino"] = entry
with open(config_path, "w") as f:
    json.dump(cfg, f, indent=2)
print(f"  Written: {config_path}", flush=True)
PYEOF
}

# ── 2. Claude Desktop ────────────────────────────────────────────────────────
if [ -d "/Applications/Claude.app" ]; then
    (
        CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
        merge_mcp_json "$CONFIG"
        log "Claude Desktop configured"
    ) || log "WARNING: Claude Desktop configuration failed"
fi

# ── 3. Claude Code CLI ───────────────────────────────────────────────────────
if [ -d "$HOME/.claude" ]; then
    (
        MCP_JSON="$HOME/.claude/mcp.json"
        SETTINGS_JSON="$HOME/.claude/settings.json"

        merge_mcp_json "$MCP_JSON"

        # Append "rhino" to enabledMcpjsonServers in settings.json
        "$PYTHON" - "$SETTINGS_JSON" <<'PYEOF'
import json, sys, os, shutil

settings_path = sys.argv[1]
if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, ValueError):
        shutil.copy(settings_path, settings_path + ".bak")
        cfg = {}
else:
    cfg = {}

servers = cfg.setdefault("enabledMcpjsonServers", [])
if "rhino" not in servers:
    servers.append("rhino")
with open(settings_path, "w") as f:
    json.dump(cfg, f, indent=2)
print(f"  Written: {settings_path}", flush=True)
PYEOF
        log "Claude Code CLI configured"
    ) || log "WARNING: Claude Code CLI configuration failed"
fi

# ── 4. ChatGPT Desktop (config path unverified — only update if file exists) ─
if [ -d "/Applications/ChatGPT.app" ]; then
    (
        CONFIG="$HOME/Library/Application Support/ChatGPT/model_settings.json"
        if [ -f "$CONFIG" ]; then
            merge_mcp_json "$CONFIG"
            log "ChatGPT Desktop configured"
        else
            log "WARNING: ChatGPT Desktop config not found at expected path — skipping (path unverified)"
        fi
    ) || log "WARNING: ChatGPT Desktop configuration failed"
fi

# ── 5. Codex CLI (skip — MCP support unconfirmed) ───────────────────────────
if [ -d "$HOME/.codex" ]; then
    log "Codex CLI detected but MCP support unconfirmed — skipping (see open item #3 in spec)"
fi

# ── 6. Codex Desktop (config path unverified — only update if file exists) ───
if [ -d "/Applications/Codex.app" ]; then
    (
        CONFIG="$HOME/Library/Application Support/Codex/model_settings.json"
        if [ -f "$CONFIG" ]; then
            merge_mcp_json "$CONFIG"
            log "Codex Desktop configured"
        else
            log "WARNING: Codex Desktop config not found at expected path — skipping (path unverified)"
        fi
    ) || log "WARNING: Codex Desktop configuration failed"
fi

# ── Write sentinel ────────────────────────────────────────────────────────────
printf "%s" "$INSTALLED_VERSION" > "$SENTINEL"
log "Sentinel written: $SENTINEL = $INSTALLED_VERSION"
log "=== configure complete ==="
```

Save to `scripts/installer/rhino-mcp-configure.sh`.

- [ ] **Step 2: Mark executable**

```bash
chmod +x scripts/installer/rhino-mcp-configure.sh
```

- [ ] **Step 3: Smoke-test the script (requires `/Users/Shared/rhino_mcp/` from a prior build or local install)**

If you have rhino-mcp installed locally (from `scripts/install.sh` or a prior build), test:

```bash
# Check syntax first (no actual run)
bash -n scripts/installer/rhino-mcp-configure.sh
echo "Syntax OK"
```

If you have the shared dir set up:
```bash
# Dry run as yourself
bash scripts/installer/rhino-mcp-configure.sh
cat ~/Library/Logs/rhino-mcp-configure.log | tail -20
```

Expected log: `=== rhino-mcp configure v0.15.1 for helpdesk ===` and one line per configured client.

- [ ] **Step 4: Commit**

```bash
git add scripts/installer/rhino-mcp-configure.sh
git commit -m "feat(installer): add per-user configure script (Rhino plugin + AI clients)"
```

---

## Task 5: LaunchAgent Plist

**Files:**
- Create: `scripts/installer/com.ayala.rhino-mcp.configure.plist`

- [ ] **Step 1: Create the plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ayala.rhino-mcp.configure</string>
    <key>Program</key>
    <string>/usr/local/bin/rhino-mcp-configure</string>
    <key>RunAtLoad</key>
    <true/>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
</dict>
</plist>
```

Save to `scripts/installer/com.ayala.rhino-mcp.configure.plist`.

> **Why no StandardOutPath/StandardErrorPath:** Tilde (`~`) is not expanded in LaunchAgent plists — paths would be literal. The configure script handles all logging to `~/Library/Logs/rhino-mcp-configure.log` itself via `$HOME`.

- [ ] **Step 2: Validate the plist**

```bash
plutil -lint scripts/installer/com.ayala.rhino-mcp.configure.plist
```

Expected: `scripts/installer/com.ayala.rhino-mcp.configure.plist: OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/installer/com.ayala.rhino-mcp.configure.plist
git commit -m "feat(installer): add LaunchAgent plist for per-user configure on login"
```

---

## Task 6: Installer Resources

**Files:**
- Create: `scripts/installer/resources/welcome.html`
- Create: `scripts/installer/resources/license.txt`

- [ ] **Step 1: Create welcome.html**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Rhino MCP</title>
</head>
<body style="font-family: -apple-system, sans-serif; padding: 20px; line-height: 1.5;">
  <h2>Rhino MCP</h2>
  <p>This installer will:</p>
  <ul>
    <li>Install the Rhino MCP server to <code>/Users/Shared/rhino_mcp/</code> (accessible by all users)</li>
    <li>Install the Rhino 8 plug-in to each user&rsquo;s Rhinoceros folder on first login</li>
    <li>Configure Claude Desktop, Claude Code, ChatGPT Desktop, and Codex (if installed)</li>
  </ul>
  <p><strong>Requirements:</strong> macOS 13 Ventura or later &middot; Apple Silicon (arm64) &middot; Admin password</p>
  <p>After installation, open Rhino 8 and run the <strong>MCPStart</strong> command, then restart your AI client.</p>
  <p style="color: #666; font-size: 0.9em;">Additional users on this machine will be configured automatically on their next login.</p>
</body>
</html>
```

Save to `scripts/installer/resources/welcome.html`.

- [ ] **Step 2: Create license.txt**

```
MIT License

Copyright (c) 2024 Jesus Ayala

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Save to `scripts/installer/resources/license.txt`.

- [ ] **Step 3: Commit**

```bash
git add scripts/installer/resources/
git commit -m "feat(installer): add welcome.html and license.txt installer resources"
```

---

## Task 7: `build-installer.sh` — Master Build Script

This script orchestrates the full 18-step pipeline: build plugin → bundle Python → create venv → stage payloads → pkgbuild × 2 → productbuild → productsign → notarize → staple → copy to release/.

**Files:**
- Create: `scripts/build-installer.sh`

- [ ] **Step 1: Create the build script**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ── Load .env if present ──────────────────────────────────────────────────────
if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$ROOT/.env"
    set +a
fi

# ── Pre-flight checks ─────────────────────────────────────────────────────────
INSTALLER_SIGNING_ID="${INSTALLER_SIGNING_ID:-Developer ID Installer: Jesus Ayala (N859JA9UCJ)}"
YAK="${YAK:-/Applications/Rhino 8.app/Contents/Resources/bin/yak}"

check_tool() {
    command -v "$1" &>/dev/null || {
        echo "ERROR: '$1' not found. $2" >&2; exit 1
    }
}
check_env() {
    [ -n "${!1:-}" ] || {
        echo "ERROR: $1 env var is required. $2" >&2; exit 1
    }
}

check_tool dotnet      "Install .NET SDK from https://dot.net"
check_tool uv          "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
check_tool pkgbuild    "Run: xcode-select --install"
check_tool productbuild "Run: xcode-select --install"
check_tool productsign  "Run: xcode-select --install"
check_tool xcrun       "Run: xcode-select --install"

[ -x "$YAK" ] || {
    echo "ERROR: yak not found at '$YAK'. Is Rhino 8 installed?" >&2; exit 1
}

check_env APPLE_ID          "Create an app-specific password at appleid.apple.com"
check_env APPLE_APP_PASSWORD "Create an app-specific password at appleid.apple.com"
check_env APPLE_TEAM_ID     "Find your team ID in App Store Connect > Membership"

# ── 1. Read VERSION ───────────────────────────────────────────────────────────
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
echo "=== Building rhino-mcp installer v$VERSION ==="

# ── 2. Build Rhino plugin ─────────────────────────────────────────────────────
echo "[1/12] Building Rhino plugin..."
"$ROOT/scripts/build-plugin.sh"

# ── 3. Package plugin ─────────────────────────────────────────────────────────
echo "[2/12] Packaging plugin (.rhp + .yak)..."
"$ROOT/scripts/package-plugin.sh"

# ── 4. Assert version in yak filename ────────────────────────────────────────
YAK_FILE=$(find "$ROOT/rhino_plugin/package" -maxdepth 1 -name "rhino-mcp-*.yak" | sort -V | tail -1)
[ -n "$YAK_FILE" ] || {
    echo "ERROR: No .yak file found after package-plugin.sh" >&2; exit 1
}
[[ "$YAK_FILE" == *"$VERSION"* ]] || {
    echo "ERROR: yak filename '$(basename "$YAK_FILE")' does not contain version '$VERSION'." >&2
    echo "       Ensure rhino_plugin manifest.yml version matches pyproject.toml." >&2
    exit 1
}
echo "       Plugin verified: $(basename "$YAK_FILE") ✓"

# ── 5. Mark installer scripts executable ─────────────────────────────────────
echo "[3/12] Setting script permissions..."
chmod +x \
    "$ROOT/scripts/installer/preinstall" \
    "$ROOT/scripts/installer/postinstall" \
    "$ROOT/scripts/installer/rhino-mcp-configure.sh"

# ── 6. Clean stale /tmp artifacts + ensure shared dirs ───────────────────────
echo "[4/12] Cleaning stale build artifacts..."
rm -rf \
    /tmp/rhino-mcp-pkg1 \
    /tmp/rhino-mcp-pkg2 \
    /tmp/rhino-mcp-server.pkg \
    /tmp/rhino-mcp-launchagent.pkg

# /Users/Shared is world-writable (mode 1777) — no sudo needed
mkdir -p /Users/Shared/rhino_mcp/plugin

# ── 7. Bundle full Python runtime ─────────────────────────────────────────────
echo "[5/12] Bundling Python 3.13 runtime..."
UV_PYTHON_DIR=$(uv python dir)
PYTHON_INSTALL=$(ls -d "$UV_PYTHON_DIR"/cpython-3.13*-macos-aarch64-none 2>/dev/null | sort -V | tail -1)
[ -n "$PYTHON_INSTALL" ] || {
    echo "ERROR: No uv-managed cpython-3.13 arm64 install found." >&2
    echo "       Run: uv python install 3.13" >&2
    exit 1
}
echo "       Source: $PYTHON_INSTALL"

rm -rf /Users/Shared/rhino_mcp/python
cp -R "$PYTHON_INSTALL" /Users/Shared/rhino_mcp/python

# ── 8. Create portable venv from bundled Python ───────────────────────────────
echo "[6/12] Creating portable venv..."
rm -rf /Users/Shared/rhino_mcp/.venv
/Users/Shared/rhino_mcp/python/bin/python3.13 -m venv /Users/Shared/rhino_mcp/.venv

# ── 9. Install rhino-mcp into venv ────────────────────────────────────────────
echo "[7/12] Installing rhino-mcp into venv..."
/Users/Shared/rhino_mcp/.venv/bin/pip install --quiet "$ROOT"

# ── 10. Write VERSION file ────────────────────────────────────────────────────
echo "[8/12] Writing VERSION..."
printf "%s" "$VERSION" > /Users/Shared/rhino_mcp/VERSION

# ── 11. Stage Rhino plugin ────────────────────────────────────────────────────
echo "[9/12] Staging Rhino plugin..."
cp "$ROOT/rhino_plugin/release/rhino-mcp.rhp" /Users/Shared/rhino_mcp/plugin/rhino-mcp.rhp

# ── 12. Stage component payloads ──────────────────────────────────────────────
echo "[10/12] Staging package payloads..."

# Component 1: full filesystem tree (installs to / )
mkdir -p /tmp/rhino-mcp-pkg1/Users/Shared/rhino_mcp
cp -R /Users/Shared/rhino_mcp/python  /tmp/rhino-mcp-pkg1/Users/Shared/rhino_mcp/
cp -R /Users/Shared/rhino_mcp/.venv   /tmp/rhino-mcp-pkg1/Users/Shared/rhino_mcp/
cp -R /Users/Shared/rhino_mcp/plugin  /tmp/rhino-mcp-pkg1/Users/Shared/rhino_mcp/
cp    /Users/Shared/rhino_mcp/VERSION  /tmp/rhino-mcp-pkg1/Users/Shared/rhino_mcp/
mkdir -p /tmp/rhino-mcp-pkg1/usr/local/bin
cp "$ROOT/scripts/installer/rhino-mcp-configure.sh" \
   /tmp/rhino-mcp-pkg1/usr/local/bin/rhino-mcp-configure
chmod +x /tmp/rhino-mcp-pkg1/usr/local/bin/rhino-mcp-configure

# Component 2: LaunchAgent plist only
mkdir -p /tmp/rhino-mcp-pkg2
cp "$ROOT/scripts/installer/com.ayala.rhino-mcp.configure.plist" /tmp/rhino-mcp-pkg2/

# ── 13. Build component packages ─────────────────────────────────────────────
echo "[11/12] Building component packages..."

pkgbuild \
    --root /tmp/rhino-mcp-pkg1 \
    --install-location / \
    --scripts "$ROOT/scripts/installer" \
    --identifier com.ayala.rhino-mcp.server \
    --version "$VERSION" \
    /tmp/rhino-mcp-server.pkg

pkgbuild \
    --root /tmp/rhino-mcp-pkg2 \
    --install-location /Library/LaunchAgents \
    --identifier com.ayala.rhino-mcp.launchagent \
    --version "$VERSION" \
    /tmp/rhino-mcp-launchagent.pkg

# ── 14. Generate distribution.xml ────────────────────────────────────────────
DIST_XML="$ROOT/rhino-mcp-distribution.xml"
cat > "$DIST_XML" <<DISTEOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Rhino MCP v${VERSION}</title>
    <options hostArchitectures="arm64" customize="allow" require-scripts="false" />
    <volume-check>
        <allowed-os-versions>
            <os-version min="13.0" />
        </allowed-os-versions>
    </volume-check>
    <welcome file="welcome.html" mime-type="text/html" />
    <license file="license.txt" mime-type="text/plain" />
    <pkg-ref id="com.ayala.rhino-mcp.server">rhino-mcp-server.pkg</pkg-ref>
    <pkg-ref id="com.ayala.rhino-mcp.launchagent">rhino-mcp-launchagent.pkg</pkg-ref>
    <choices-outline>
        <line choice="default">
            <line choice="com.ayala.rhino-mcp.server"/>
            <line choice="com.ayala.rhino-mcp.launchagent"/>
        </line>
    </choices-outline>
    <choice id="default" title="Rhino MCP"/>
    <choice id="com.ayala.rhino-mcp.server" visible="false">
        <pkg-ref id="com.ayala.rhino-mcp.server"/>
    </choice>
    <choice id="com.ayala.rhino-mcp.launchagent" visible="false">
        <pkg-ref id="com.ayala.rhino-mcp.launchagent"/>
    </choice>
</installer-gui-script>
DISTEOF

# ── 15. Product archive (unsigned) ────────────────────────────────────────────
UNSIGNED_PKG="$ROOT/rhino-mcp-${VERSION}-arm64-unsigned.pkg"
productbuild \
    --distribution "$DIST_XML" \
    --resources "$ROOT/scripts/installer/resources" \
    --package-path /tmp \
    "$UNSIGNED_PKG"
rm -f "$DIST_XML"

# ── 16. Sign ─────────────────────────────────────────────────────────────────
echo "[12/12] Signing, notarizing, stapling..."
SIGNED_PKG="$ROOT/rhino-mcp-${VERSION}-arm64.pkg"
productsign \
    --sign "$INSTALLER_SIGNING_ID" \
    "$UNSIGNED_PKG" \
    "$SIGNED_PKG"
rm -f "$UNSIGNED_PKG"

# ── 17. Notarize ─────────────────────────────────────────────────────────────
echo "       Submitting to Apple notary service (this takes 1-3 minutes)..."
xcrun notarytool submit "$SIGNED_PKG" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait

# ── 18. Staple ───────────────────────────────────────────────────────────────
xcrun stapler staple "$SIGNED_PKG"

# ── 19. Move to release/ + cleanup ───────────────────────────────────────────
mkdir -p "$ROOT/release"
FINAL_PKG="$ROOT/release/rhino-mcp-${VERSION}-arm64-installer.pkg"
cp "$SIGNED_PKG" "$FINAL_PKG"
rm -f "$SIGNED_PKG"

rm -rf \
    /tmp/rhino-mcp-pkg1 \
    /tmp/rhino-mcp-pkg2 \
    /tmp/rhino-mcp-server.pkg \
    /tmp/rhino-mcp-launchagent.pkg

echo ""
echo "=== Done! ==="
echo "    Installer: $FINAL_PKG"
echo "    Size: $(du -sh "$FINAL_PKG" | cut -f1)"
```

Save to `scripts/build-installer.sh`.

- [ ] **Step 2: Mark executable**

```bash
chmod +x scripts/build-installer.sh
```

- [ ] **Step 3: Validate syntax**

```bash
bash -n scripts/build-installer.sh
echo "Syntax OK"
```

- [ ] **Step 4: Run pre-flight check only (no build)**

Temporarily test that tool detection works by checking each tool directly:

```bash
command -v dotnet && echo "dotnet ok"
command -v uv && echo "uv ok"
command -v pkgbuild && echo "pkgbuild ok"
command -v productbuild && echo "productbuild ok"
command -v productsign && echo "productsign ok"
command -v xcrun && echo "xcrun ok"
test -x "/Applications/Rhino 8.app/Contents/Resources/bin/yak" && echo "yak ok"
```

All lines should print `ok`. If `pkgbuild` / `productbuild` / `productsign` are missing, run `xcode-select --install`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build-installer.sh
git commit -m "feat(installer): add build-installer.sh master build script"
```

---

## Task 8: `test-installer.sh` — Post-Install Verification

**Files:**
- Create: `scripts/test-installer.sh`

- [ ] **Step 1: Create the test script**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Must run as root (installer requires it)
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Run as root: sudo bash scripts/test-installer.sh" >&2
    exit 1
fi

VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('$ROOT/pyproject.toml','rb'))['project']['version'])")
PKG="$ROOT/release/rhino-mcp-${VERSION}-arm64-installer.pkg"

if [ ! -f "$PKG" ]; then
    echo "ERROR: Installer not found: $PKG" >&2
    echo "       Run scripts/build-installer.sh first." >&2
    exit 1
fi

echo "=== Installing $PKG ==="
installer -pkg "$PKG" -target /

echo ""
echo "=== Verifying installation ==="
PASS=0
FAIL=0

check_file() {
    local desc="$1"
    local path="$2"
    if [ -e "$path" ]; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — not found: $path"
        FAIL=$((FAIL + 1))
    fi
}

check_exec() {
    local desc="$1"
    local path="$2"
    if [ -x "$path" ]; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — not executable: $path"
        FAIL=$((FAIL + 1))
    fi
}

check_file "Python runtime dir"       "/Users/Shared/rhino_mcp/python"
check_exec "Python 3.13 binary"       "/Users/Shared/rhino_mcp/python/bin/python3.13"
check_file "libpython3.13.dylib"      "/Users/Shared/rhino_mcp/python/lib/libpython3.13.dylib"
check_exec "Venv Python binary"       "/Users/Shared/rhino_mcp/.venv/bin/python"
check_file "Rhino plugin staged"      "/Users/Shared/rhino_mcp/plugin/rhino-mcp.rhp"
check_file "VERSION file"             "/Users/Shared/rhino_mcp/VERSION"
check_exec "Configure script"         "/usr/local/bin/rhino-mcp-configure"
check_file "LaunchAgent plist"        "/Library/LaunchAgents/com.ayala.rhino-mcp.configure.plist"

# VERSION content
INSTALLED_VERSION=$(cat /Users/Shared/rhino_mcp/VERSION 2>/dev/null || echo "")
if [ "$INSTALLED_VERSION" = "$VERSION" ]; then
    echo "  PASS: VERSION matches ($VERSION)"
    PASS=$((PASS + 1))
else
    echo "  FAIL: VERSION mismatch — expected '$VERSION', got '$INSTALLED_VERSION'"
    FAIL=$((FAIL + 1))
fi

# rhmcp importable from venv
if /Users/Shared/rhino_mcp/.venv/bin/python -c "import rhmcp" 2>/dev/null; then
    echo "  PASS: rhmcp importable from venv"
    PASS=$((PASS + 1))
else
    echo "  FAIL: rhmcp not importable from venv"
    FAIL=$((FAIL + 1))
fi

# pyvenv.cfg home points to bundled Python
VENV_HOME=$(grep '^home' /Users/Shared/rhino_mcp/.venv/pyvenv.cfg 2>/dev/null | cut -d= -f2 | tr -d ' ')
if [ "$VENV_HOME" = "/Users/Shared/rhino_mcp/python/bin" ]; then
    echo "  PASS: pyvenv.cfg home = /Users/Shared/rhino_mcp/python/bin"
    PASS=$((PASS + 1))
else
    echo "  FAIL: pyvenv.cfg home = '$VENV_HOME' (expected /Users/Shared/rhino_mcp/python/bin)"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    echo "=== All checks passed ==="
else
    echo "=== $FAIL check(s) FAILED ==="
    exit 1
fi
```

Save to `scripts/test-installer.sh`.

- [ ] **Step 2: Mark executable**

```bash
chmod +x scripts/test-installer.sh
```

- [ ] **Step 3: Validate syntax**

```bash
bash -n scripts/test-installer.sh
echo "Syntax OK"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/test-installer.sh
git commit -m "feat(installer): add test-installer.sh post-install verification script"
```

---

## Task 9: Full Build Run

This task runs the complete build pipeline end-to-end and verifies the output. **Requires a `.env` file with `APPLE_ID`, `APPLE_APP_PASSWORD`, and `APPLE_TEAM_ID` set.**

- [ ] **Step 1: Create `.env` from template (first time only)**

```bash
cp .env.example .env
# Edit .env to set APPLE_APP_PASSWORD and verify other values
```

- [ ] **Step 2: Run the build**

```bash
bash scripts/build-installer.sh
```

Expected final output:
```
=== Done! ===
    Installer: /Users/helpdesk/Developer/GitHub/rhino_mcp/release/rhino-mcp-0.15.1-arm64-installer.pkg
    Size: ~70M
```

The build writes a side-effect on the build machine: `/Users/Shared/rhino_mcp/` is populated. This is expected and serves as a local install.

- [ ] **Step 3: Verify the signed package**

```bash
pkgutil --check-signature release/rhino-mcp-0.15.1-arm64-installer.pkg
```

Expected output includes `Developer ID Installer: Jesus Ayala (N859JA9UCJ)` and `Status: signed by a certificate trusted by macOS`.

- [ ] **Step 4: Run post-install verification**

```bash
sudo bash scripts/test-installer.sh
```

Expected: all checks pass.

- [ ] **Step 5: Check configure log**

```bash
cat ~/Library/Logs/rhino-mcp-configure.log
```

Expected: lines for each detected AI client showing configuration success.

- [ ] **Step 6: Commit any final fixups**

If the build run revealed any issues (path typos, permission problems), fix and commit them before this step.

```bash
git add -p   # stage only intentional changes
git commit -m "fix(installer): <describe issue>"
```

---

## Self-Review Checklist

After writing tasks, checked against spec:

- [x] `.gitignore` missing entries documented and implemented (Task 1)
- [x] `preinstall` blocks macOS < 13, warns on missing Rhino 8 (Task 2)
- [x] `postinstall` runs `chmod -R a+rX` BEFORE calling configure (Task 3)
- [x] `rhino-mcp-configure.sh` reads VERSION, handles missing-VERSION edge case (Task 4)
- [x] Configure script: idempotent sentinel logic (Task 4)
- [x] Configure script: Rhino plugin copy with `mkdir -p` (Task 4)
- [x] Configure script: Claude Desktop JSON merge — create if missing (Task 4)
- [x] Configure script: Claude Code CLI — updates both `mcp.json` and `settings.json` (Task 4)
- [x] Configure script: ChatGPT Desktop — only updates if file EXISTS (path unverified) (Task 4)
- [x] Configure script: Codex CLI — skip with log message (Task 4)
- [x] Configure script: Codex Desktop — only updates if file EXISTS (path unverified) (Task 4)
- [x] Configure script: each client block isolated with `(subshell) || log "WARNING"` (Task 4)
- [x] Configure script: logging to `~/Library/Logs/rhino-mcp-configure.log` via `$HOME` (Task 4)
- [x] LaunchAgent: `LimitLoadToSessionType = Aqua`, no tilde in plist (Task 5)
- [x] `build-installer.sh`: pre-flight checks for all tools + env vars (Task 7)
- [x] `build-installer.sh`: VERSION from `tomllib` (Task 7)
- [x] `build-installer.sh`: version assertion on yak filename (Task 7)
- [x] `build-installer.sh`: `/tmp` cleanup at START of step 6 (Task 7)
- [x] `build-installer.sh`: `mkdir -p /Users/Shared/rhino_mcp/plugin` before staging (Task 7)
- [x] `build-installer.sh`: full Python runtime copied with `cp -R` (Task 7)
- [x] `build-installer.sh`: venv created from bundled Python at final install path (Task 7)
- [x] `build-installer.sh`: `printf "%s"` for VERSION (no trailing newline) (Task 7)
- [x] `build-installer.sh`: Component 1 uses `--install-location /` with full fs tree (Task 7)
- [x] `build-installer.sh`: `distribution.xml` has `hostArchitectures="arm64"` (Task 7)
- [x] `build-installer.sh`: `productbuild --package-path /tmp` (Task 7)
- [x] `test-installer.sh`: checks `pyvenv.cfg home` for bundled Python path (Task 8)
- [x] `test-installer.sh`: checks `libpython3.13.dylib` exists (Task 8)
- [x] `test-installer.sh`: checks `rhmcp` importable (Task 8)
- [x] `.env.example` updated with signing/notarization vars (Task 1)
