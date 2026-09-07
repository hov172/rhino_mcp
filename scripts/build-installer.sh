#!/usr/bin/env bash
set -euo pipefail

# ── Cleanup trap ──────────────────────────────────────────────────────────────
cleanup() {
    rm -rf "${BUILDTMP:-/tmp/rhino-mcp-build}" 2>/dev/null || true
    [ -n "${DIST_XML:-}" ]    && rm -f "$DIST_XML"    2>/dev/null || true
    [ -n "${UNSIGNED_PKG:-}" ] && rm -f "$UNSIGNED_PKG" 2>/dev/null || true
    [ -n "${SIGNED_PKG:-}" ]  && rm -f "$SIGNED_PKG"  2>/dev/null || true
}
trap cleanup EXIT

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BUILDTMP=$(mktemp -d "${TMPDIR%/}/rhino-mcp-build.XXXXXX")
PAYLOAD="$BUILDTMP/pkg1/Users/Shared/rhino_mcp"

# ── Load .env if present ──────────────────────────────────────────────────────
if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$ROOT/.env"
    set +a
fi

# ── Pre-flight checks ─────────────────────────────────────────────────────────
# Auto-detect Developer ID Installer cert if not set in .env
if [ -z "${INSTALLER_SIGNING_ID:-}" ]; then
    INSTALLER_SIGNING_ID=$(security find-identity -v | \
        grep '"Developer ID Installer:' | head -1 | \
        sed 's/.*"\(Developer ID Installer:[^"]*\)".*/\1/')
    [ -n "$INSTALLER_SIGNING_ID" ] || {
        echo "ERROR: No 'Developer ID Installer' certificate found in Keychain." >&2
        echo "       Set INSTALLER_SIGNING_ID in .env or install the certificate." >&2
        exit 1
    }
    echo "       Installer signing identity: $INSTALLER_SIGNING_ID"
fi

# Auto-detect Developer ID Application cert (needed to sign bundled binaries)
if [ -z "${APP_SIGNING_ID:-}" ]; then
    APP_SIGNING_ID=$(security find-identity -v | \
        grep '"Developer ID Application:' | head -1 | \
        sed 's/.*"\(Developer ID Application:[^"]*\)".*/\1/')
    [ -n "$APP_SIGNING_ID" ] || {
        echo "ERROR: No 'Developer ID Application' certificate found in Keychain." >&2
        echo "       Set APP_SIGNING_ID in .env or install the certificate." >&2
        exit 1
    }
    echo "       Application signing identity: $APP_SIGNING_ID"
fi
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


# ── 1. Read VERSION ───────────────────────────────────────────────────────────
VERSION=$(uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
echo "=== Building rhino-mcp installer v$VERSION ==="

# ── 2. Build Rhino plugin ─────────────────────────────────────────────────────
echo "[1/14] Building Rhino plugin..."
"$ROOT/scripts/build-plugin.sh"

# ── 3. Package plugin ─────────────────────────────────────────────────────────
echo "[2/14] Packaging plugin (.rhp + .yak)..."
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
echo "[3/14] Setting script permissions..."
chmod +x \
    "$ROOT/scripts/installer/preinstall" \
    "$ROOT/scripts/installer/postinstall" \
    "$ROOT/scripts/installer/rhino-mcp-configure.sh" \
    "$ROOT/scripts/installer/uninstaller/postinstall"

# ── 6. Clean stale /tmp artifacts + ensure shared dirs ───────────────────────
echo "[4/14] Cleaning stale build artifacts..."
rm -rf "$BUILDTMP"
mkdir -p "$BUILDTMP"

# All build files stay in temporary staging; do not change the live installation.
mkdir -p "${PAYLOAD}/plugin"

# ── 7. Bundle Python runtimes (arm64 + x86_64) ────────────────────────────────
echo "[5/14] Bundling Python 3.13 runtimes (arm64 + x86_64)..."
UV_PYTHON_DIR=$(uv python dir)

PYTHON_ARM64=$(find "$UV_PYTHON_DIR" -maxdepth 1 -type d -name "cpython-3.13*-macos-aarch64-none" 2>/dev/null | sort -V | tail -1)
[ -n "$PYTHON_ARM64" ] || {
    echo "ERROR: No uv-managed cpython-3.13 arm64 install found." >&2
    echo "       Run: uv python install 3.13" >&2
    exit 1
}
echo "       arm64:  $PYTHON_ARM64"

PYTHON_X86=$(find "$UV_PYTHON_DIR" -maxdepth 1 -type d -name "cpython-3.13*-macos-x86_64-none" 2>/dev/null | sort -V | tail -1)
if [ -z "$PYTHON_X86" ]; then
    echo "       x86_64 Python not found — installing via uv..."
    uv python install "cpython-3.13-macos-x86_64"
    PYTHON_X86=$(find "$UV_PYTHON_DIR" -maxdepth 1 -type d -name "cpython-3.13*-macos-x86_64-none" 2>/dev/null | sort -V | tail -1)
fi
[ -n "$PYTHON_X86" ] || {
    echo "ERROR: Failed to find/install cpython-3.13 x86_64." >&2
    exit 1
}
echo "       x86_64: $PYTHON_X86"

rm -rf "${PAYLOAD}/python-arm64" "${PAYLOAD}/python-x86_64"
cp -R "$PYTHON_ARM64" "${PAYLOAD}/python-arm64"
cp -R "$PYTHON_X86"   "${PAYLOAD}/python-x86_64"

# ── 8. Create portable venvs for both architectures ───────────────────────────
echo "[6/14] Creating portable venvs..."
rm -rf "${PAYLOAD}/.venv-arm64" "${PAYLOAD}/.venv-x86_64"
"${PAYLOAD}/python-arm64/bin/python3.13" -m venv "${PAYLOAD}/.venv-arm64"
"${PAYLOAD}/python-x86_64/bin/python3.13" -m venv "${PAYLOAD}/.venv-x86_64"

# The matching wheel must be built and verified before installer packaging.
[ -f "$ROOT/dist/rhino_mcp-${VERSION}-py3-none-any.whl" ] || {
    echo "ERROR: Build the matching Python wheel first (uv build)." >&2; exit 1;
}

# ── 9. Install rhino-mcp into both venvs ──────────────────────────────────────
echo "[7/14] Installing rhino-mcp into venvs..."
"${PAYLOAD}/.venv-arm64/bin/pip" install --quiet "$ROOT/dist/rhino_mcp-${VERSION}-py3-none-any.whl"
# cryptography >= 49 ships no macOS x86_64/universal2 wheels — without the pin
# pip falls back to a source build that needs a Rust x86_64 cross target.
"${PAYLOAD}/.venv-x86_64/bin/pip" install --quiet "$ROOT/dist/rhino_mcp-${VERSION}-py3-none-any.whl" "cryptography<49"

# Validate both installed runtimes before relocation, signing, or submission.
for ARCH in arm64 x86_64; do
    "${PAYLOAD}/.venv-${ARCH}/bin/python" -c '
from importlib.metadata import version
from rhmcp.tools_helpers.tool_runtime import RuntimeMCP
from rhmcp.tools_helpers.compact_registry import CompactRegistry
v = version("rhino-mcp")
assert v == __import__("sys").argv[1]
assert RuntimeMCP("rhino-mcp")._mcp_server.create_initialization_options().server_version == v
registry = CompactRegistry()
registry.load_from_modules(None)
assert len(registry._tools) == 358
print("Verified bundled runtime:", v, "MCP SDK:", version("mcp"), "tools:", len(registry._tools))
' "$VERSION"
done

# ── 10. Write VERSION file ────────────────────────────────────────────────────
echo "[8/14] Writing VERSION..."
printf "%s" "$VERSION" > "${PAYLOAD}/VERSION"

# ── 11. Stage Rhino plugin ────────────────────────────────────────────────────
echo "[9/14] Staging Rhino plugin..."
cp "$ROOT/rhino_plugin/release/rhino-mcp.rhp" "${PAYLOAD}/plugin/"
cp "$ROOT/rhino_plugin/release/"rhino-mcp.*json "${PAYLOAD}/plugin/"
cp "$ROOT/rhino_plugin/release/"Microsoft.CodeAnalysis*.dll "${PAYLOAD}/plugin/"

# ── 12. Stage component payloads ──────────────────────────────────────────────
echo "[10/14] Staging package payloads..."

cp "$ROOT/scripts/installer/install-plugin.py" "$PAYLOAD/install-plugin.py"

# Component 1: payload is already staged under its final installation path.
mkdir -p "$BUILDTMP/pkg1/usr/local/bin"
cp "$ROOT/scripts/installer/rhino-mcp-configure.sh" \
   "$BUILDTMP/pkg1/usr/local/bin/rhino-mcp-configure"
chmod +x "$BUILDTMP/pkg1/usr/local/bin/rhino-mcp-configure"

# Rewrite venv links/config/scripts to the final install prefix before signing.
uv run python "$ROOT/scripts/relocate-installer-venvs.py" "$PAYLOAD"

# Component 2: LaunchAgent plist only
mkdir -p "$BUILDTMP/pkg2"
cp "$ROOT/scripts/installer/com.ayala.rhino-mcp.configure.plist" "$BUILDTMP/pkg2/"

# ── 11. Deep-sign all native binaries in payload ──────────────────────────────
# Apple notarization requires every .dylib, .so, and Mach-O executable to be
# signed with a Developer ID Application cert, with --timestamp and --options runtime.
echo "[11/14] Deep-signing native binaries..."
SIGN_ARGS=(--sign "$APP_SIGNING_ID" --timestamp --options runtime --force)

# Sign all dylibs and shared objects
find "$BUILDTMP/pkg1" \( -name "*.dylib" -o -name "*.so" \) -print0 \
    | xargs -0 -P4 codesign "${SIGN_ARGS[@]}"

# Sign Mach-O executables (skip shell scripts and text files)
while IFS= read -r -d '' f; do
    file "$f" 2>/dev/null | grep -q "Mach-O" || continue
    codesign "${SIGN_ARGS[@]}" "$f"
done < <(find "$BUILDTMP/pkg1" -type f -perm +0111 -print0)

echo "       Signed $(find "$BUILDTMP/pkg1" \( -name "*.dylib" -o -name "*.so" \) | wc -l | tr -d ' ') dylibs/SOs"

# ── 13. Build component packages ─────────────────────────────────────────────
echo "[12/14] Building component packages..."

pkgbuild \
    --root "$BUILDTMP/pkg1" \
    --install-location / \
    --scripts "$ROOT/scripts/installer" \
    --identifier com.ayala.rhino-mcp.server \
    --version "$VERSION" \
    "$BUILDTMP/rhino-mcp-server.pkg"

pkgbuild \
    --root "$BUILDTMP/pkg2" \
    --install-location /Library/LaunchAgents \
    --identifier com.ayala.rhino-mcp.launchagent \
    --version "$VERSION" \
    "$BUILDTMP/rhino-mcp-launchagent.pkg"

# ── 14. Generate distribution.xml ────────────────────────────────────────────
DIST_XML="$ROOT/rhino-mcp-distribution.xml"
cat > "$DIST_XML" <<DISTEOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Rhino MCP v${VERSION}</title>
    <options customize="allow" require-scripts="false" />
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

# ── 15. Product archive ───────────────────────────────────────────────────────
echo "[13/14] Building product archive..."
mkdir -p "$ROOT/release"
FINAL_PKG="$ROOT/release/rhino-mcp-${VERSION}-universal-installer.pkg"
productbuild \
    --distribution "$DIST_XML" \
    --resources "$ROOT/scripts/installer/resources" \
    --package-path "$BUILDTMP" \
    "$FINAL_PKG"
rm -f "$DIST_XML"

# ── 16. Build uninstaller package ────────────────────────────────────────────
echo "[14/14] Building uninstaller package..."
UNINSTALLER_PKG="$ROOT/release/rhino-mcp-${VERSION}-universal-uninstaller.pkg"
pkgbuild \
    --nopayload \
    --scripts "$ROOT/scripts/installer/uninstaller" \
    --identifier com.ayala.rhino-mcp.uninstaller \
    --version "$VERSION" \
    "$UNINSTALLER_PKG"

# ── 17. Cleanup ───────────────────────────────────────────────────────────────
rm -rf "$BUILDTMP"

echo ""
echo "=== Build done ==="
echo "    Installer:   $FINAL_PKG"
echo "    Uninstaller: $UNINSTALLER_PKG"
echo "    Installer size: $(du -sh "$FINAL_PKG" | cut -f1)"

# ── 18. Sign, notarize, staple ───────────────────────────────────────────────
# Signs with the Developer ID Installer cert detected above. Notarization runs
# when NOTARY_PROFILE is set (a notarytool keychain profile, e.g. created with
# `xcrun notarytool store-credentials`); set it in .env to fully automate.
SIGNED_FINAL="$ROOT/release/rhino-mcp-${VERSION}-universal-signed.pkg"
SIGNED_UNINSTALL="$ROOT/release/rhino-mcp-${VERSION}-universal-uninstaller-signed.pkg"

echo ""
echo "[15] Signing packages with: $INSTALLER_SIGNING_ID"
productsign --sign "$INSTALLER_SIGNING_ID" "$FINAL_PKG" "$SIGNED_FINAL"
productsign --sign "$INSTALLER_SIGNING_ID" "$UNINSTALLER_PKG" "$SIGNED_UNINSTALL"

if [ -n "${NOTARY_PROFILE:-}" ]; then
    echo "[16] Notarizing with keychain profile '$NOTARY_PROFILE' (this can take a few minutes)..."
    # Submit both before waiting so Apple can process them concurrently.
    mkdir -p "$BUILDTMP"
    xcrun notarytool submit "$SIGNED_FINAL" --keychain-profile "$NOTARY_PROFILE" --output-format json > "$BUILDTMP/installer-notary.json"
    xcrun notarytool submit "$SIGNED_UNINSTALL" --keychain-profile "$NOTARY_PROFILE" --output-format json > "$BUILDTMP/uninstaller-notary.json"
    for SUBMISSION in "$BUILDTMP/installer-notary.json" "$BUILDTMP/uninstaller-notary.json"; do
        SUBMISSION_ID=$(uv run python -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$SUBMISSION")
        xcrun notarytool wait "$SUBMISSION_ID" --keychain-profile "$NOTARY_PROFILE"
    done
    echo "[17] Stapling notarization tickets..."
    xcrun stapler staple "$SIGNED_FINAL"
    xcrun stapler staple "$SIGNED_UNINSTALL"
    echo "[18] Gatekeeper check:"
    spctl -a -vv -t install "$SIGNED_FINAL"
else
    echo "    NOTARY_PROFILE not set — skipping notarization. To notarize:"
    echo "      xcrun notarytool submit $SIGNED_FINAL --keychain-profile <profile> --wait"
    echo "      xcrun stapler staple $SIGNED_FINAL"
fi

echo ""
echo "=== Done! ==="
echo "    Signed installer:   $SIGNED_FINAL"
echo "    Signed uninstaller: $SIGNED_UNINSTALL"
