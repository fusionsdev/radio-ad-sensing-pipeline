# One-time: enable Understand-Anything auto-update for this repo.
# - Sets autoUpdate in .understand-anything/config.json
# - Builds fingerprints baseline (required for incremental updates)
# - Installs git post-commit marker hook (fallback when Cursor agent is closed)
# - .cursor/hooks.json is already in repo for Cursor session/commit triggers

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$UaDir = Join-Path $ProjectRoot ".understand-anything"
$ConfigFile = Join-Path $UaDir "config.json"
$GraphFile = Join-Path $UaDir "knowledge-graph.json"
$ScanFile = Join-Path $UaDir "intermediate\scan-result.json"
$SkillDir = Join-Path $env:USERPROFILE ".agents\skills\understand"

if (-not (Test-Path $GraphFile)) {
    Write-Error "Run /understand first — missing $GraphFile"
}

# Enable autoUpdate (merge with existing config)
$config = @{ outputLanguage = "en"; autoUpdate = $true }
if (Test-Path $ConfigFile) {
    $existing = Get-Content $ConfigFile -Raw | ConvertFrom-Json
    if ($existing.outputLanguage) { $config.outputLanguage = $existing.outputLanguage }
}
[System.IO.File]::WriteAllText($ConfigFile, ($config | ConvertTo-Json), (New-Object System.Text.UTF8Encoding $false))
Write-Host "Enabled autoUpdate in $ConfigFile"

# Fingerprints baseline
if (-not (Test-Path $ScanFile)) {
    Write-Warning "Missing $ScanFile — re-run /understand to refresh scan inventory."
} else {
    $scan = Get-Content $ScanFile -Raw | ConvertFrom-Json
    $commit = git -C $ProjectRoot rev-parse HEAD
    $paths = @($scan.files | ForEach-Object { $_.path })
    $fpInput = @{
        projectRoot = $ProjectRoot
        sourceFilePaths = $paths
        gitCommitHash = $commit
    }
    $fpInputPath = Join-Path $UaDir "intermediate\fingerprint-input.json"
    [System.IO.File]::WriteAllText($fpInputPath, ($fpInput | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding $false))
    node "$SkillDir\build-fingerprints.mjs" $fpInputPath
    if ($LASTEXITCODE -ne 0) { throw "build-fingerprints failed" }
    Write-Host "Fingerprints baseline written"
}

# Normalize meta.json for auto-update hook
$commit = git -C $ProjectRoot rev-parse HEAD
$meta = @{
    lastAnalyzedAt = (Get-Date).ToUniversalTime().ToString("o")
    gitCommitHash = $commit
    version = "1.0.0"
    analyzedFiles = (Get-Content $ScanFile -Raw | ConvertFrom-Json).totalFiles
    nodeCount = 491
    edgeCount = 677
}
if (Test-Path $GraphFile) {
    $g = Get-Content $GraphFile -Raw | ConvertFrom-Json
    if ($g.nodes) { $meta.nodeCount = @($g.nodes).Count }
    if ($g.edges) { $meta.edgeCount = @($g.edges).Count }
}
[System.IO.File]::WriteAllText((Join-Path $UaDir "meta.json"), ($meta | ConvertTo-Json), (New-Object System.Text.UTF8Encoding $false))

# Git post-commit: mark graph stale (picked up on next Cursor session)
$HookDir = Join-Path $ProjectRoot ".githooks"
New-Item -ItemType Directory -Force -Path $HookDir | Out-Null
$hook = @'
#!/bin/sh
# Understand-Anything: mark graph stale after commit (Cursor sessionStart picks this up)
CFG=".understand-anything/config.json"
GRAPH=".understand-anything/knowledge-graph.json"
[ -f "$CFG" ] && grep -q '"autoUpdate".*true' "$CFG" 2>/dev/null || exit 0
[ -f "$GRAPH" ] || exit 0
META=".understand-anything/meta.json"
HEAD=$(git rev-parse HEAD 2>/dev/null) || exit 0
STORED=$(node -e "try{const m=require('./'+process.argv[1]);process.stdout.write(m.gitCommitHash||'')}catch(e){}" "$META" 2>/dev/null)
[ "$HEAD" = "$STORED" ] && exit 0
echo "$HEAD" > .understand-anything/.graph-stale 2>/dev/null || true
'@
$hook | Set-Content -NoNewline -Encoding utf8 (Join-Path $HookDir "post-commit")
git -C $ProjectRoot config core.hooksPath .githooks
Write-Host "Git hooksPath -> .githooks (post-commit marker)"

Write-Host ""
Write-Host "Auto-update enabled."
Write-Host "  Cursor: restart IDE to load .cursor/hooks.json"
Write-Host "  Agent will run auto-update on session start (stale graph) and after git commit"
