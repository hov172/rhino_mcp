#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="$ROOT/rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj"

dotnet build "$PROJECT" -c Release
