# Run Claude Octopus orchestrate.sh on Windows with Git Bash prep fixes.
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Workflow,

    [switch]$DryRun,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Bash = "C:\Program Files\Git\bin\bash.exe"
$Orchestrate = "$env:USERPROFILE\.claude-octopus\plugin\scripts\orchestrate.sh"
$Prep = "$RepoRoot\scripts\octo-windows-prep.sh"

if (-not (Test-Path $Bash)) {
    throw "Git Bash not found at $Bash — install Git for Windows."
}
if (-not (Test-Path $Orchestrate)) {
    throw "Octo orchestrate.sh not found at $Orchestrate — install Claude Octopus plugin."
}

$prompt = ($Args -join " ").Trim()
if (-not $prompt -and $Workflow -notin @("doctor", "octopus-configure", "setup")) {
    throw "Usage: .\scripts\octo-run.ps1 define `"your prompt`""
}

$dryRunFlag = if ($DryRun) { "--dry-run" } else { "" }

$bashCmd = @"
set -euo pipefail
cd '$($RepoRoot -replace "\\", "/")'
source '$($Prep -replace "\\", "/")'
'$($Orchestrate -replace "\\", "/")' $dryRunFlag '$Workflow' $(if ($prompt) { "'$($prompt -replace "'", "'\\''")'" } else { "" })
"@

Write-Host "Running Octo workflow: $Workflow" -ForegroundColor Cyan
& $Bash -lc $bashCmd
exit $LASTEXITCODE
