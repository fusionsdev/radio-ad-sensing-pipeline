# Live pipeline status via Docker (avoids stale Windows bind-mount DB reads).
# Usage: .\scripts\pipeline-status.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$QueryScript = Join-Path $RepoRoot "scripts\pipeline_status_query.py"
Get-Content -Raw $QueryScript | docker exec -i radio-worker python -

Write-Host ""
Write-Host "=== Docker services ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}"
