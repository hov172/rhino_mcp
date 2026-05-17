$YakExe = "C:\Program Files\Rhino 8\System\yak.exe"
$PkgDir = Join-Path $PSScriptRoot "..\rhino_plugin\package"
$YakFile = Get-ChildItem "$PkgDir\rhino-mcp-*.yak" | Sort-Object Name | Select-Object -Last 1

if (-not $YakFile) {
    Write-Error "No .yak file found. Run .\scripts\package-plugin.ps1 first."
    exit 1
}

Write-Host "Installing $($YakFile.Name) ..."
& $YakExe install --source $YakFile.FullName
Write-Host "Done. Restart Rhino to load the updated plugin."
