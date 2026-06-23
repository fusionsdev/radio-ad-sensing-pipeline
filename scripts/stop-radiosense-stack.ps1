# Stop RadioSense host-side services (frontend + bridges). Docker pipeline stays up by default.
# Usage:
#   .\scripts\stop-radiosense-stack.ps1
#   .\scripts\stop-radiosense-stack.ps1 -StopDashboard

param(
    [switch]$StopDashboard
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$FrontendPort = if ($env:RADIOSENSE_FRONTEND_PORT) { $env:RADIOSENSE_FRONTEND_PORT } else { "5150" }
$HermesPort = if ($env:HERMES_BRIDGE_PORT) { $env:HERMES_BRIDGE_PORT } else { "8791" }
$ControlPort = if ($env:RADIOSENSE_CONTROL_PORT) { $env:RADIOSENSE_CONTROL_PORT } else { "8792" }

function Stop-PortListener {
    param([string]$Port, [string]$Label)
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "$Label not listening on port $Port"
        return
    }
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $pids) {
        try {
            $proc = Get-Process -Id $pid -ErrorAction Stop
            Write-Host "Stopping $Label (PID $pid, $($proc.ProcessName)) on port $Port"
            Stop-Process -Id $pid -Force -ErrorAction Stop
        } catch {
            Write-Warning "Could not stop PID $pid for $Label: $($_.Exception.Message)"
        }
    }
}

Write-Host "=== Stopping RadioSense host services ==="
Stop-PortListener -Port $ControlPort -Label "Control bridge"
Stop-PortListener -Port $HermesPort -Label "Hermes bridge"
Stop-PortListener -Port $FrontendPort -Label "Frontend dev server"

if ($StopDashboard) {
    Write-Host "Stopping radio-dashboard container..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.windows-dev.yml stop dashboard
} else {
    Write-Host "Docker pipeline left running (pass -StopDashboard to stop radio-dashboard)."
}

Write-Host "Done."