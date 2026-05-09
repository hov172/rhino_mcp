#!/usr/bin/env bash
# One-command installer for rhino-mcp (macOS / Linux)
# Usage: bash scripts/install.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== rhino-mcp installer ==="

# ── 1. Python package ────────────────────────────────────────────────────────
if command -v uv &>/dev/null; then
    echo "[1/2] Installing Python package with uv..."
    uv pip install "$REPO_ROOT"
elif command -v pip3 &>/dev/null; then
    echo "[1/2] Installing Python package with pip3..."
    pip3 install "$REPO_ROOT"
else
    echo "ERROR: Neither uv nor pip3 found. Install Python 3.10+ first." >&2
    exit 1
fi

# ── 2. Claude Desktop config ──────────────────────────────────────────────────
CONFIG_DIR="$HOME/Library/Application Support/Claude"
CONFIG="$CONFIG_DIR/claude_desktop_config.json"
PYTHON_PATH="$(command -v python3 || command -v python)"

if [ ! -d "$CONFIG_DIR" ]; then
    echo "[2/2] Claude Desktop not found — skipping MCP config."
    echo ""
    echo "Manual MCP config entry:"
    echo '  "rhino": { "command": "'"$PYTHON_PATH"'", "args": ["-m", "rhmcp"] }'
else
    mkdir -p "$CONFIG_DIR"
    if [ -f "$CONFIG" ]; then
        # Check if rhino key already present
        if python3 -c "import json,sys; d=json.load(open('$CONFIG')); sys.exit(0 if 'rhino' in d.get('mcpServers',{}) else 1)" 2>/dev/null; then
            echo "[2/2] Claude Desktop config already contains 'rhino' entry — skipping."
        else
            echo "[2/2] Adding rhino-mcp to Claude Desktop config..."
            python3 - <<PYEOF
import json, sys
path = "$CONFIG"
with open(path) as f:
    cfg = json.load(f)
cfg.setdefault("mcpServers", {})["rhino"] = {
    "command": "$PYTHON_PATH",
    "args": ["-m", "rhmcp"]
}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
print("  Written:", path)
PYEOF
        fi
    else
        echo "[2/2] Creating Claude Desktop config..."
        mkdir -p "$CONFIG_DIR"
        python3 - <<PYEOF
import json
cfg = {"mcpServers": {"rhino": {"command": "$PYTHON_PATH", "args": ["-m", "rhmcp"]}}}
with open("$CONFIG", "w") as f:
    json.dump(cfg, f, indent=2)
print("  Written: $CONFIG")
PYEOF
    fi
fi

echo ""
echo "Done! Restart Claude Desktop, then open Rhino and run MCPStart."
