# Loan-only pipeline ops — live Docker DB + strict loan classifier.
# Usage: .\scripts\pipeline-loan-ops.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

function Get-DockerServiceStatus {
    param([string]$ContainerPrefix, [string]$ShortName)
    $line = docker compose `
        -f docker-compose.yml `
        -f docker-compose.prod.yml `
        -f docker-compose.windows-dev.yml `
        ps --format "{{.Name}}`t{{.Status}}" 2>$null |
        Where-Object { $_ -match "^$ContainerPrefix" } |
        Select-Object -First 1
    if (-not $line) {
        return @{ name = $ShortName; status = "missing"; note = "container not found" }
    }
    $parts = $line -split "`t", 2
    $status = if ($parts.Length -gt 1) { $parts[1] } else { "unknown" }
    $normalized = if ($status -match "Up") { "up" } else { "down" }
    return @{ name = $ShortName; status = $normalized; note = $status }
}

$services = @(
    (Get-DockerServiceStatus -ContainerPrefix "radio-ingestor" -ShortName "ingestor"),
    (Get-DockerServiceStatus -ContainerPrefix "radio-worker" -ShortName "worker"),
    (Get-DockerServiceStatus -ContainerPrefix "radio-alerter" -ShortName "alerter"),
    (Get-DockerServiceStatus -ContainerPrefix "radio-dashboard" -ShortName "dashboard")
)
$servicesJson = ($services | ConvertTo-Json -Compress)

$LoanClassifier = Join-Path $RepoRoot "scripts\loan_classifier.py"
$LoanOps = Join-Path $RepoRoot "scripts\pipeline_loan_ops.py"
$LoanOpsCore = Join-Path $RepoRoot "shared\pipeline_loan_ops.py"

# Worker image has /app/shared but no /app/scripts — copy fresh ops modules to container.
docker cp $LoanOpsCore radio-worker:/app/shared/pipeline_loan_ops.py | Out-Null
docker cp $LoanClassifier radio-worker:/tmp/loan_classifier.py | Out-Null
docker cp $LoanOps radio-worker:/tmp/pipeline_loan_ops.py | Out-Null

$servicesJson = ($services | ConvertTo-Json -Compress)
$servicesB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($servicesJson))

docker exec radio-worker python /tmp/pipeline_loan_ops.py --services-b64 "$servicesB64"
