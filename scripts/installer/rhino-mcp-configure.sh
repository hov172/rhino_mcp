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
