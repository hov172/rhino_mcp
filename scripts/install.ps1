# One-command installer for rhino-mcp (Windows)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install.ps1
#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== rhino-mcp installer ===" -ForegroundColor Cyan

# ── 1. Python package ─────────────────────────────────────────────────────────
$uvPath = Get-Command uv -ErrorAction SilentlyContinue
$pipPath = Get-Command pip -ErrorAction SilentlyContinue

if ($uvPath) {
    Write-Host "[1/2] Installing Python package with uv..."
    uv pip install $RepoRoot
} elseif ($pipPath) {
    Write-Host "[1/2] Installing Python package with pip..."
    pip install $RepoRoot
} else {
    Write-Error "Neither uv nor pip found. Install Python 3.10+ first."
    exit 1
}

# ── 2. Claude Desktop config ──────────────────────────────────────────────────
$ConfigDir = Join-Path $env:APPDATA "Claude"
$ConfigFile = Join-Path $ConfigDir "claude_desktop_config.json"
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue)?.Source ?? "python"

if (-not (Test-Path $ConfigDir)) {
    Write-Host "[2/2] Claude Desktop not found — skipping MCP config."
    Write-Host ""
    Write-Host "Manual MCP config entry:"
    Write-Host "  `"rhino`": { `"command`": `"$PythonPath`", `"args`": [`"-m`", `"rhmcp`"] }"
} else {
    if (Test-Path $ConfigFile) {
        $cfg = Get-Content $ConfigFile -Raw | ConvertFrom-Json
        if ($cfg.mcpServers -and $cfg.mcpServers.PSObject.Properties["rhino"]) {
            Write-Host "[2/2] Claude Desktop config already contains 'rhino' entry — skipping."
        } else {
            Write-Host "[2/2] Adding rhino-mcp to Claude Desktop config..."
            if (-not $cfg.mcpServers) {
                $cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([PSCustomObject]@{})
            }
            $entry = [PSCustomObject]@{ command = $PythonPath; args = @("-m", "rhmcp") }
            $cfg.mcpServers | Add-Member -NotePropertyName rhino -NotePropertyValue $entry
            $cfg | ConvertTo-Json -Depth 10 | Set-Content $ConfigFile -Encoding UTF8
            Write-Host "  Written: $ConfigFile"
        }
    } else {
        Write-Host "[2/2] Creating Claude Desktop config..."
        $cfg = [PSCustomObject]@{
            mcpServers = [PSCustomObject]@{
                rhino = [PSCustomObject]@{ command = $PythonPath; args = @("-m", "rhmcp") }
            }
        }
        New-Item -ItemType Directory -Force $ConfigDir | Out-Null
        $cfg | ConvertTo-Json -Depth 10 | Set-Content $ConfigFile -Encoding UTF8
        Write-Host "  Written: $ConfigFile"
    }
}

Write-Host ""
Write-Host "Done! Restart Claude Desktop, then open Rhino and run MCPStart." -ForegroundColor Green
