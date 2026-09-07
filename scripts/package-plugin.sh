#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_DIR="$ROOT/rhino_plugin/RhinoMCPPlugin"
PACKAGE_DIR="$ROOT/rhino_plugin/package"
RELEASE_DIR="$ROOT/rhino_plugin/release"
BUILD_DIR="$PROJECT_DIR/bin/Release/net8.0"
YAK="${YAK:-/Applications/Rhino 8.app/Contents/Resources/bin/yak}"
VERSION="$(sed -n 's/^version: *//p' "$PACKAGE_DIR/manifest.yml")"

"$ROOT/scripts/build-plugin.sh"

rm -rf "$PACKAGE_DIR/RhinoMCPPlugin"
rm -f "$PACKAGE_DIR"/RhinoMCPPlugin.* "$PACKAGE_DIR"/Microsoft.CodeAnalysis*.dll
cp "$BUILD_DIR/rhino-mcp.rhp" "$PACKAGE_DIR/"
cp "$BUILD_DIR/rhino-mcp.deps.json" "$PACKAGE_DIR/" 2>/dev/null || true
cp "$BUILD_DIR/rhino-mcp.runtimeconfig.json" "$PACKAGE_DIR/" 2>/dev/null || true
cp "$BUILD_DIR"/Microsoft.CodeAnalysis*.dll "$PACKAGE_DIR/" 2>/dev/null || true

cd "$PACKAGE_DIR"
"$YAK" build

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
cp "$PACKAGE_DIR"/rhino-mcp.rhp "$RELEASE_DIR"/
cp "$PACKAGE_DIR"/rhino-mcp-"$VERSION"-*.yak "$RELEASE_DIR"/
cp "$PACKAGE_DIR"/manifest.yml "$RELEASE_DIR"/
cp "$PACKAGE_DIR"/rhino-mcp.deps.json "$RELEASE_DIR"/ 2>/dev/null || true
cp "$PACKAGE_DIR"/rhino-mcp.runtimeconfig.json "$RELEASE_DIR"/ 2>/dev/null || true
cp "$PACKAGE_DIR"/Microsoft.CodeAnalysis*.dll "$RELEASE_DIR"/ 2>/dev/null || true
