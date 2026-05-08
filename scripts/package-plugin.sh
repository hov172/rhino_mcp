#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_DIR="$ROOT/rhino_plugin/RhinoMCPPlugin"
PACKAGE_DIR="$ROOT/rhino_plugin/package"
BUILD_DIR="$PROJECT_DIR/bin/Release/net7.0"
YAK="${YAK:-/Applications/Rhino 8.app/Contents/Resources/bin/yak}"

"$ROOT/scripts/build-plugin.sh"

rm -rf "$PACKAGE_DIR/RhinoMCPPlugin"
rm -f "$PACKAGE_DIR"/RhinoMCPPlugin.* "$PACKAGE_DIR"/Microsoft.CodeAnalysis*.dll
cp "$BUILD_DIR/RhinoMCPPlugin.rhp" "$PACKAGE_DIR/"
cp "$BUILD_DIR/RhinoMCPPlugin.deps.json" "$PACKAGE_DIR/" 2>/dev/null || true
cp "$BUILD_DIR/RhinoMCPPlugin.runtimeconfig.json" "$PACKAGE_DIR/" 2>/dev/null || true
cp "$BUILD_DIR"/Microsoft.CodeAnalysis*.dll "$PACKAGE_DIR/" 2>/dev/null || true

cd "$PACKAGE_DIR"
"$YAK" build
