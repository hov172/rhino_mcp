#!/usr/bin/env bash
set -euo pipefail

YAK="/Applications/Rhino 8.app/Contents/Resources/bin/yak"
PKG_DIR="$(cd "$(dirname "$0")/../rhino_plugin/package" && pwd)"

if [ ! -x "$YAK" ]; then
    echo "yak not found at $YAK. Is Rhino 8 installed?"
    exit 1
fi

YAK_FILE=$(find "$PKG_DIR" -maxdepth 1 -name "rhino-mcp-*.yak" | sort -V | tail -1)
if [ -z "$YAK_FILE" ]; then
    echo "No .yak file found in $PKG_DIR. Run ./scripts/package-plugin.sh first."
    exit 1
fi

echo "Installing $(basename "$YAK_FILE") ..."
"$YAK" install --source "$YAK_FILE"
echo "Done. Restart Rhino to load the updated plugin."
