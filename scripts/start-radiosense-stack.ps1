# One-click RadioSense stack launcher for post-reboot recovery.
# Usage:
#   .\scripts\start-radiosense-stack.ps1
#   .\scripts\start-radiosense-stack.ps1 -NoFrontend
#   .\scripts\start-radiosense-stack.ps1 -RestartDashboard
#   .\scripts\start-radiosense-stack.ps1 -OpenBrowser

param(
    [switch]$NoFrontend,
    [switch]$RestartDashboard,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$FrontendDir = if ($env:RADIOSENSE_FRONTEND_DIR) { $env:RADIOSENSE_FRONTEND_DIR } else { "H:\DEV\github_sandbox\radiosense-aistudio" }
$FrontendUrl = if ($env:RADIOSENSE_FRONTEND_URL) { $env:RADIOSENSE_FRONTEND_URL } else { "http://localhost:5150/" }
$BackendHealthUrl = if ($env:BACKEND_HEALTH_URL) { $env:BACKEND_HEALTH_URL } else { "http://127.0.0.1:8081/health" }
$StationsUrl = if ($env:BACKEND_STATIONS_URL) { $env:BACKEND_STATIONS_URL } else { "http://127.0.0.1:8081/api/stations?limit=1" }
$HermesHealthUrl = if ($env:HERMES_BRIDGE_URL) { "$($env:HERMES_BRIDGE_URL.TrimEnd('/'))/health" } else { "http://127.0.0.1:8791/health" }
$ControlHealthUrl = if ($env:RADIOSENSE_CONTROL_URL) { "$($env:RADIOSENSE_CONTROL_URL.TrimEnd('/'))/health" } else { "http://127.0.0.1:8792/health" }
$ComposeArgs = @(
    "compose",
    "-f", "docker-compose.yml",
    "-f", "docker-compose.prod.yml",
    "-f", "docker-compose.windows-dev.yml"
)

function Test-HttpOk {
    param([string]$Url, [int]$TimeoutSec = 5)
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSec -UseBasicParsing
        return [pscustomobject]@{
            Ok = ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
            StatusCode = $response.StatusCode
            Error = $null
        }
    } catch {
        $statusCode = $null
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        return [pscustomobject]@{
            Ok = $false
            StatusCode = $statusCode
            Error = $_.Exception.Message
        }
    }
}

function Wait-ForHttp {
    param(
        [string]$Label,
        [string]$Url,
        [int]$Attempts = 12,
        [int]$DelaySec = 5
    )
    for ($i = 1; $i -le $Attempts; $i++) {
        $probe = Test-HttpOk -Url $Url -TimeoutSec 4
        if ($probe.Ok) {
            Write-Host "  $Label ready ($Url)"
            return $probe
        }
        Write-Host "  Waiting for $Label ($i/$Attempts)..."
        Start-Sleep -Seconds $DelaySec
    }
    return Test-HttpOk -Url $Url -TimeoutSec 4
}

function Get-DockerDashboardStatus {
    try {
        $raw = docker inspect --format "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}" radio-dashboard 2>$null
        if (-not $raw) { return "down" }
        $parts = $raw -split "\|", 2
        $state = $parts[0]
        $health = if ($parts.Length -gt 1) { $parts[1] } else { "none" }
        if ($state -ne "running") { return "down" }
        if ($health -eq "healthy") { return "healthy" }
        if ($health -eq "unhealthy") { return "unhealthy" }
        return "running"
    } catch {
        return "unknown"
    }
}

function Ensure-DockerDesktop {
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) {
        Write-Warning "Docker CLI not found on PATH."
        return $false
    }
    try {
        docker info *> $null
        return $true
    } catch {
        Write-Host "Docker daemon not ready. Attempting to start Docker Desktop..."
        $desktop = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
        if (Test-Path $desktop) {
            Start-Process -FilePath $desktop | Out-Null
            for ($i = 1; $i -le 24; $i++) {
                Start-Sleep -Seconds 5
                try {
                    docker info *> $null
                    Write-Host "Docker Desktop is ready."
                    return $true
                } catch {
                    Write-Host "  Waiting for Docker Desktop ($i/24)..."
                }
            }
        }
        Write-Warning "Docker is not available. Dashboard container cannot be started."
        return $false
    }
}

function Test-FrontendRunning {
    return (Test-HttpOk -Url $FrontendUrl -TimeoutSec 3).Ok
}

function Start-FrontendDevServer {
    if (-not (Test-Path $FrontendDir)) {
        Write-Warning "Frontend directory not found: $FrontendDir"
        return $false
    }
    if (Test-FrontendRunning) {
        Write-Host "Frontend already running at $FrontendUrl"
        return $true
    }
    Write-Host "Starting RadioSense frontend dev server..."
    Start-Process -FilePath "powershell" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Set-Location '$FrontendDir'; npm run dev"
    ) -WorkingDirectory $FrontendDir -WindowStyle Minimized | Out-Null
    $probe = Wait-ForHttp -Label "Frontend" -Url $FrontendUrl -Attempts 10 -DelaySec 3
    return $probe.Ok
}

Write-Host "=== RadioSense stack startup ==="

$dockerReady = Ensure-DockerDesktop
$dashboardStatus = "unknown"

if ($dockerReady) {
    if ($RestartDashboard) {
        Write-Host "Restarting radio-dashboard container..."
        & docker @ComposeArgs restart dashboard | Out-Host
    } else {
        $current = Get-DockerDashboardStatus
        if ($current -eq "healthy" -or $current -eq "running") {
            Write-Host "radio-dashboard already $current"
        } else {
            Write-Host "Starting radio-dashboard container..."
            & docker @ComposeArgs up -d dashboard | Out-Host
        }
    }
    $dashboardStatus = Get-DockerDashboardStatus
} else {
    $dashboardStatus = "down"
}

Write-Host "Starting Hermes bridge..."
& "$RepoRoot\scripts\start-hermes-bridge.ps1" -Background

Write-Host "Starting RadioSense control bridge..."
& "$RepoRoot\scripts\start-radiosense-control-bridge.ps1" -Background

if (-not $NoFrontend) {
    [void](Start-FrontendDevServer)
} else {
    Write-Host "Skipping frontend startup (-NoFrontend)."
}

Write-Host ""
Write-Host "Verifying endpoints..."
$backendHealth = Wait-ForHttp -Label "Backend /health" -Url $BackendHealthUrl -Attempts 8 -DelaySec 4
$stationsProbe = Test-HttpOk -Url $StationsUrl -TimeoutSec 8
$hermesProbe = Wait-ForHttp -Label "Hermes bridge" -Url $HermesHealthUrl -Attempts 6 -DelaySec 3
$controlProbe = Wait-ForHttp -Label "Control bridge" -Url $ControlHealthUrl -Attempts 4 -DelaySec 2
$frontendProbe = if ($NoFrontend) { Test-HttpOk -Url $FrontendUrl -TimeoutSec 3 } else { Test-HttpOk -Url $FrontendUrl -TimeoutSec 5 }
$dashboardStatus = if ($dockerReady) { Get-DockerDashboardStatus } else { "down" }

function Format-Status {
    param($Probe, [string]$Fallback = "offline")
    if ($null -eq $Probe) { return $Fallback }
    if ($Probe.Ok) { return "online" }
    if ($Probe.StatusCode) { return "error ($($Probe.StatusCode))" }
    return $Fallback
}

$rows = @(
    [pscustomobject]@{ Component = "Docker Dashboard"; Status = $dashboardStatus; Endpoint = "radio-dashboard" },
    [pscustomobject]@{ Component = "Backend /health"; Status = (Format-Status $backendHealth); Endpoint = $BackendHealthUrl },
    [pscustomobject]@{ Component = "Backend /api/stations"; Status = (Format-Status $stationsProbe "error"); Endpoint = $StationsUrl },
    [pscustomobject]@{ Component = "Hermes Bridge"; Status = (Format-Status $hermesProbe); Endpoint = $HermesHealthUrl },
    [pscustomobject]@{ Component = "Control Bridge"; Status = (Format-Status $controlProbe); Endpoint = $ControlHealthUrl },
    [pscustomobject]@{ Component = "Frontend"; Status = $(if ($frontendProbe.Ok) { "running" } else { "offline" }); Endpoint = $FrontendUrl }
)

Write-Host ""
$rows | Format-Table -AutoSize

if ($OpenBrowser) {
    if ($frontendProbe.Ok) {
        Start-Process $FrontendUrl | Out-Null
        Write-Host "Opened $FrontendUrl"
    } else {
        Write-Warning "Frontend is not reachable; browser not opened."
    }
}

$allCoreOk = $backendHealth.Ok -and $hermesProbe.Ok -and $controlProbe.Ok
if ($allCoreOk) {
    Write-Host "RadioSense stack startup complete."
    exit 0
}

Write-Warning "RadioSense stack started with issues. Open http://localhost:5150/system-control for recovery actions."
exit 1