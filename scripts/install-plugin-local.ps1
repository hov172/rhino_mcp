$YakExe = "C:\Program Files\Rhino 8\System\yak.exe"
$PkgDir = Join-Path $PSScriptRoot "..\rhino_plugin\package"

if (-not (Test-Path $YakExe)) {
    Write-Error "yak.exe not found at $YakExe. Is Rhino 8 installed?"
    exit 1
}

$YakFile = Get-ChildItem "$PkgDir\rhino-mcp-*.yak" | Sort-Object LastWriteTime | Select-Object -Last 1

if (-not $YakFile) {
    Write-Error "No .yak file found. Build the plugin first (use scripts/build-plugin.sh in WSL or Git Bash, then scripts/package-plugin.sh)."
    exit 1
}

Write-Host "Installing $($YakFile.Name) ..."
& $YakExe install --source $YakFile.FullName
Write-Host "Done. Restart Rhino to load the updated plugin."
