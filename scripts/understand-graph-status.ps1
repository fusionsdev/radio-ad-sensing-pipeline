# Show Understand-Anything graph status for this repo.

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$GraphFile = Join-Path $ProjectRoot ".understand-anything\knowledge-graph.json"
$MetaFile = Join-Path $ProjectRoot ".understand-anything\meta.json"

if (-not (Test-Path $GraphFile)) {
    Write-Host "Status: no graph"
    Write-Host "Run /understand in Cursor, then check again."
    exit 1
}

$sizeKb = [math]::Round((Get-Item $GraphFile).Length / 1KB)
Write-Host "Status: graph present ($sizeKb KB)"
Write-Host "Path:   $GraphFile"

if (Test-Path $MetaFile) {
    $meta = Get-Content $MetaFile -Raw | ConvertFrom-Json
    if ($meta.gitCommitHash) { Write-Host "Commit: $($meta.gitCommitHash.Substring(0, 12))" }
    if ($meta.analyzedAt) { Write-Host "Built:  $($meta.analyzedAt)" }
    if ($meta.nodeCount) { Write-Host "Nodes:  $($meta.nodeCount)  Edges: $($meta.edgeCount)" }
}

Write-Host ""
Write-Host "Open dashboard: .\scripts\understand-dashboard.ps1"
