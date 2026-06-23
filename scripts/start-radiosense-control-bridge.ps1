# Start the local RadioSense control bridge (allowlisted host actions).
# Usage:
#   .\scripts\start-radiosense-control-bridge.ps1
#   .\scripts\start-radiosense-control-bridge.ps1 -Background

param(
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$hostAddr = if ($env:RADIOSENSE_CONTROL_HOST) { $env:RADIOSENSE_CONTROL_HOST } else { "127.0.0.1" }
$port = if ($env:RADIOSENSE_CONTROL_PORT) { $env:RADIOSENSE_CONTROL_PORT } else { "8792" }
$healthUrl = "http://${hostAddr}:${port}/health"

try {
    $existing = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($existing.ok) {
        Write-Host "RadioSense control bridge already running at $healthUrl"
        exit 0
    }
} catch {
    # not running — start below
}

if ($Background) {
    Start-Process -FilePath "python" -ArgumentList "scripts\radiosense_control_bridge.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden
    Start-Sleep -Seconds 2
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
    if (-not $health.ok) {
        Write-Error "RadioSense control bridge failed to start."
    }
    Write-Host "RadioSense control bridge started in background at $healthUrl"
    exit 0
}

Write-Host "Starting RadioSense control bridge at $healthUrl ..."
python scripts\radiosense_control_bridge.py