#!/usr/bin/env bash
set -euo pipefail

YAK="/Applications/Rhino 8.app/Contents/Resources/bin/yak"
PKG_DIR="$(cd "$(dirname "$0")/../rhino_plugin/package" && pwd)"

YAK_FILE=$(ls "$PKG_DIR"/rhino-mcp-*.yak 2>/dev/null | sort -V | tail -1)
if [ -z "$YAK_FILE" ]; then
    echo "No .yak file found in $PKG_DIR. Run ./scripts/package-plugin.sh first."
    exit 1
fi

echo "Installing $(basename "$YAK_FILE") ..."
"$YAK" install --source "$YAK_FILE"
echo "Done. Restart Rhino to load the updated plugin."
