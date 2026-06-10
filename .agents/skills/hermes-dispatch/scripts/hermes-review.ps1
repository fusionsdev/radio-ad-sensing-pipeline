# Dispatch a review bundle to Hermes agent CLI.
# Usage:
#   .\hermes-review.ps1 -Scope wp13 -PlanPath plan/codexplan.md
#   .\hermes-review.ps1 -Scope wp13-gemini -PromptFile ..\.agents\skills\hermes-dispatch\PROMPTS.md

param(
    [Parameter(Mandatory = $true)]
    [string]$Scope,

    [string]$PlanPath = "plan/codexplan.md",
    [string]$ReportPath = "",
    [string]$PromptFile = "",
    [string]$RepoRoot = "",
    [int]$DiffCommits = 5
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = (Get-Location).Path
}

Set-Location $RepoRoot

$hermes = Get-Command hermes -ErrorAction SilentlyContinue
if (-not $hermes) {
    Write-Error "hermes CLI not found on PATH. Install Hermes agent first."
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmm"
$bundle = Join-Path $RepoRoot "plan\_hermes-bundle-$Scope-$timestamp.md"
$out = Join-Path $RepoRoot "plan\hermes-review-$Scope-$timestamp.md"

$lines = [System.Collections.Generic.List[string]]::new()
[void]$lines.Add("# Hermes Review Bundle — $Scope")
[void]$lines.Add("Generated: $(Get-Date -Format o)")
[void]$lines.Add("")
[void]$lines.Add("## Git changed files (last $DiffCommits commits)")
[void]$lines.Add('```')

try {
    $revRange = "HEAD~${DiffCommits}..HEAD"
    $diff = git diff --name-only $revRange 2>$null
    if ($diff) {
        foreach ($f in $diff) { [void]$lines.Add($f) }
    } else {
        [void]$lines.Add("(no diff or shallow history)")
    }
} catch {
    [void]$lines.Add("(git diff unavailable)")
}

[void]$lines.Add('```')
[void]$lines.Add("")
[void]$lines.Add("## Plan")
[void]$lines.Add("Path: $PlanPath")

if (Test-Path (Join-Path $RepoRoot $PlanPath)) {
    [void]$lines.Add("")
    [void]$lines.Add((Get-Content (Join-Path $RepoRoot $PlanPath) -Raw))
} else {
    [void]$lines.Add("")
    [void]$lines.Add("(plan file not found)")
}

if ($ReportPath -and (Test-Path (Join-Path $RepoRoot $ReportPath))) {
    [void]$lines.Add("")
    [void]$lines.Add("## Implementer report")
    [void]$lines.Add("Path: $ReportPath")
    [void]$lines.Add("")
    [void]$lines.Add((Get-Content (Join-Path $RepoRoot $ReportPath) -Raw))
}

[void]$lines.Add("")
[void]$lines.Add("## Pytest summary")
[void]$lines.Add('```')

$pytestCmd = Join-Path $RepoRoot '.venv\Scripts\pytest.exe'
if (Test-Path $pytestCmd) {
    try {
        $pyOut = & $pytestCmd -q 2>&1 | Select-Object -Last 8
        foreach ($line in $pyOut) { [void]$lines.Add([string]$line) }
    } catch {
        [void]$lines.Add("pytest failed to run")
    }
} else {
    try {
        $pyOut = pytest -q 2>&1 | Select-Object -Last 8
        foreach ($line in $pyOut) { [void]$lines.Add([string]$line) }
    } catch {
        [void]$lines.Add("pytest not available")
    }
}

[void]$lines.Add('```')

$lines -join "`n" | Set-Content $bundle -Encoding utf8

$defaultPrompt = @"
Act as independent review gate for scope: $Scope.
Read the bundled markdown. Review Spec + Standards per project PLAN.md.
List findings by severity (critical / major / minor) with file:line where possible.
End with exactly one line: VERDICT: ship | fix-then-ship | rework
"@

if ($PromptFile -and (Test-Path (Join-Path $RepoRoot $PromptFile))) {
    $prompt = Get-Content (Join-Path $RepoRoot $PromptFile) -Raw
} elseif ($PromptFile -and (Test-Path $PromptFile)) {
    $prompt = Get-Content $PromptFile -Raw
} else {
    $prompt = $defaultPrompt
}

Write-Host "Dispatching Hermes"
Write-Host "  scope:  $Scope"
Write-Host "  input:  $bundle"
Write-Host "  output: $out"

$bundleContent = Get-Content $bundle -Raw
$fullPrompt = @"
$prompt

---
Review bundle:

$bundleContent
"@

# Hermes Agent CLI: use -z/--oneshot (not `hermes run` from older docs).
& hermes -z $fullPrompt --yolo --accept-hooks 2>&1 | Set-Content $out -Encoding utf8

if ($LASTEXITCODE -ne 0) {
    Write-Error "hermes oneshot failed with exit code $LASTEXITCODE"
}

Write-Host "Review saved: $out"
