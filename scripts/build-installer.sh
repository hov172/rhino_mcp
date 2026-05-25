#!/usr/bin/env bash
set -euo pipefail

# ── Cleanup trap ──────────────────────────────────────────────────────────────
cleanup() {
    rm -rf /tmp/rhino-mcp-pkg1 /tmp/rhino-mcp-pkg2 \
           /tmp/rhino-mcp-server.pkg /tmp/rhino-mcp-launchagent.pkg 2>/dev/null || true
    [ -n "${DIST_XML:-}" ]    && rm -f "$DIST_XML"    2>/dev/null || true
    [ -n "${UNSIGNED_PKG:-}" ] && rm -f "$UNSIGNED_PKG" 2>/dev/null || true
    [ -n "${SIGNED_PKG:-}" ]  && rm -f "$SIGNED_PKG"  2>/dev/null || true
}
trap cleanup EXIT

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
VERSION=$(uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
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
    --wait \
    --timeout 600

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
