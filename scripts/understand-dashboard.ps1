# Start the Understand-Anything knowledge-graph dashboard for this repo.
# Requires: Node.js 22+, pnpm (installed with Understand-Anything).
# Prereq graph: run `/understand` in Cursor once, or ensure
#   .understand-anything/knowledge-graph.json exists.

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$GraphFile = Join-Path $ProjectRoot ".understand-anything\knowledge-graph.json"

if (-not (Test-Path $GraphFile)) {
    Write-Error @"
No knowledge graph found at:
  $GraphFile

Run /understand in Cursor first, then retry:
  .\scripts\understand-dashboard.ps1
"@
}

$PluginRoot = Join-Path $env:USERPROFILE ".understand-anything\repo\understand-anything-plugin"
$DashboardDir = Join-Path $PluginRoot "packages\dashboard"

if (-not (Test-Path (Join-Path $DashboardDir "src\main.tsx"))) {
    Write-Error @"
Understand-Anything dashboard not found at:
  $DashboardDir

Install once (PowerShell):
  iwr -useb https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.ps1 | iex
  cd `$env:USERPROFILE\.understand-anything\repo; pnpm install
"@
}

$env:GRAPH_DIR = $ProjectRoot
Set-Location $DashboardDir

if (-not (Test-Path (Join-Path $PluginRoot "packages\core\dist\index.js"))) {
    Write-Host "Building @understand-anything/core..."
    Set-Location $PluginRoot
    pnpm --filter @understand-anything/core build | Out-Host
    Set-Location $DashboardDir
}

Write-Host "Project: $ProjectRoot"
Write-Host "Graph:   $GraphFile"
Write-Host ""
Write-Host "Starting dashboard (Ctrl+C to stop). Copy the URL with ?token= from output below."
Write-Host ""

npx vite --host 127.0.0.1
