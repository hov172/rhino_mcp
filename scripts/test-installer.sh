#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Must run as root (installer requires it)
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Run as root: sudo bash scripts/test-installer.sh" >&2
    exit 1
fi

VERSION=$(uv run python -c "import tomllib; print(tomllib.load(open('$ROOT/pyproject.toml','rb'))['project']['version'])")
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
