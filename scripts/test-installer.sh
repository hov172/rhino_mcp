#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Must run as root (installer requires it)
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Run as root: sudo bash scripts/test-installer.sh" >&2
    exit 1
fi

VERSION=$(uv run python -c "import tomllib; print(tomllib.load(open('$ROOT/pyproject.toml','rb'))['project']['version'])")
PKG="$ROOT/release/rhino-mcp-${VERSION}-universal-signed.pkg"

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

# pyvenv.cfg home points to the architecture-specific bundled Python
EXPECTED_PYTHON_HOME="/Users/Shared/rhino_mcp/python-$(uname -m)/bin"
VENV_HOME=$(grep '^home' /Users/Shared/rhino_mcp/.venv/pyvenv.cfg 2>/dev/null | cut -d= -f2 | tr -d ' ')
if [ "$VENV_HOME" = "$EXPECTED_PYTHON_HOME" ]; then
    echo "  PASS: pyvenv.cfg home = $EXPECTED_PYTHON_HOME"
    PASS=$((PASS + 1))
else
    echo "  FAIL: pyvenv.cfg home = '$VENV_HOME' (expected $EXPECTED_PYTHON_HOME)"
    FAIL=$((FAIL + 1))
fi

# Per-user checks (resolve the current console user's home)
CONSOLE_USER=$(stat -f "%Su" /dev/console 2>/dev/null || echo "")
if [ -n "$CONSOLE_USER" ] && [ "$CONSOLE_USER" != "root" ]; then
    USER_HOME=$(dscl . -read "/Users/$CONSOLE_USER" NFSHomeDirectory 2>/dev/null | awk '{print $2}')
    if [ -n "$USER_HOME" ]; then
        PLUGIN_PATH="$USER_HOME/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp/rhino-mcp.rhp"
        if [ -f "$PLUGIN_PATH" ]; then
            echo "  PASS: Rhino plugin installed for $CONSOLE_USER"
            PASS=$((PASS + 1))
        else
            echo "  FAIL: Rhino plugin not found for $CONSOLE_USER: $PLUGIN_PATH"
            FAIL=$((FAIL + 1))
        fi

        if [ -d "$USER_HOME/.claude" ]; then
            MCP_JSON="$USER_HOME/.claude/mcp.json"
            if [ -f "$MCP_JSON" ] && grep -q '"rhino"' "$MCP_JSON" 2>/dev/null; then
                echo "  PASS: Claude Code mcp.json contains rhino entry"
                PASS=$((PASS + 1))
            else
                echo "  FAIL: Claude Code mcp.json missing or has no rhino entry"
                FAIL=$((FAIL + 1))
            fi
        fi

        if [ -d "/Applications/Claude.app" ]; then
            CLAUDE_CFG="$USER_HOME/Library/Application Support/Claude/claude_desktop_config.json"
            if [ -f "$CLAUDE_CFG" ] && grep -q '"rhino"' "$CLAUDE_CFG" 2>/dev/null; then
                echo "  PASS: Claude Desktop config contains rhino entry"
                PASS=$((PASS + 1))
            else
                echo "  FAIL: Claude Desktop config missing or has no rhino entry"
                FAIL=$((FAIL + 1))
            fi
        fi
    fi
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
    echo "=== All checks passed ==="
else
    echo "=== $FAIL check(s) FAILED ==="
    exit 1
fi
