# Start the local Hermes HTTP bridge for RadioSense / radio-dashboard Docker.
# Usage:
#   .\scripts\start-hermes-bridge.ps1
#   .\scripts\start-hermes-bridge.ps1 -Background

param(
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    Write-Error "hermes CLI not found on PATH. Install Hermes Agent first."
}

$healthUrl = "http://127.0.0.1:8791/health"
try {
    $existing = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($existing.ok) {
        Write-Host "Hermes bridge already running at $healthUrl"
        exit 0
    }
} catch {
    # not running — start below
}

$env:HERMES_BRIDGE_HOST = if ($env:HERMES_BRIDGE_HOST) { $env:HERMES_BRIDGE_HOST } else { "127.0.0.1" }
$env:HERMES_BRIDGE_PORT = if ($env:HERMES_BRIDGE_PORT) { $env:HERMES_BRIDGE_PORT } else { "8791" }
$env:HERMES_COMMAND = if ($env:HERMES_COMMAND) { $env:HERMES_COMMAND } else { "hermes -p radio-runner" }
$env:HERMES_PROFILE = if ($env:HERMES_PROFILE) { $env:HERMES_PROFILE } else { "radio-runner" }
$env:HERMES_CWD = if ($env:HERMES_CWD) { $env:HERMES_CWD } else { $RepoRoot }

if ($Background) {
    Start-Process -FilePath "python" -ArgumentList "scripts\hermes_bridge.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden
    Start-Sleep -Seconds 2
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
    if (-not $health.ok) {
        Write-Error "Hermes bridge failed to start."
    }
    Write-Host "Hermes bridge started in background at $healthUrl"
    exit 0
}

Write-Host "Starting Hermes bridge at http://$($env:HERMES_BRIDGE_HOST):$($env:HERMES_BRIDGE_PORT) ..."
python scripts\hermes_bridge.py