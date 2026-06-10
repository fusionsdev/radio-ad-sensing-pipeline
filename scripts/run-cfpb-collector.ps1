# Run CFPB complaint trademark collector (host or Docker one-shot).
# Usage:
#   .\scripts\run-cfpb-collector.ps1           # host .venv
#   .\scripts\run-cfpb-collector.ps1 -Docker   # compose profile cfpb

param(
    [switch]$Docker,
    [string]$Config = "config/cfpb_collector.yaml"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

if ($Docker) {
    Write-Host "=== CFPB collector (Docker one-shot) ==="
    docker compose --profile cfpb run --rm cfpb-collector
    exit $LASTEXITCODE
}

Write-Host "=== CFPB collector (host .venv) ==="
& .\.venv\Scripts\python -m collectors.cfpb_complaints_collector --config $Config
exit $LASTEXITCODE
