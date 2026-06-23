# Register a Windows Task Scheduler entry to start RadioSense after login/restart.
#
# Usage:
#   .\scripts\register-radiosense-startup-task.ps1
#   .\scripts\register-radiosense-startup-task.ps1 -WithFrontend
#   .\scripts\register-radiosense-startup-task.ps1 -Disable
#   .\scripts\register-radiosense-startup-task.ps1 -Unregister

param(
    [string]$TaskName = "RadioSense Stack Boot",
    [switch]$WithFrontend,
    [switch]$OpenBrowser,
    [switch]$Disable,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $RepoRoot "scripts\start-radiosense-stack.ps1"

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName"
    exit 0
}

if (-not (Test-Path $StartScript)) {
    Write-Error "Startup script not found: $StartScript"
}

$args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$StartScript`"")
if (-not $WithFrontend) {
    $args += "-NoFrontend"
}
if ($OpenBrowser) {
    $args += "-OpenBrowser"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ($args -join " ") `
    -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Start RadioSense stack after Windows login (Docker dashboard, Hermes bridge, control bridge)." `
    -Force | Out-Null

if ($Disable) {
    Disable-ScheduledTask -TaskName $TaskName | Out-Null
    Write-Host "Registered and DISABLED task: $TaskName"
} else {
    Enable-ScheduledTask -TaskName $TaskName | Out-Null
    Write-Host "Registered and ENABLED task: $TaskName"
}

Write-Host "Trigger: At logon for user $env:USERNAME"
Write-Host "Command: $StartScript $(if ($WithFrontend) { '' } else { '-NoFrontend ' })$(if ($OpenBrowser) { '-OpenBrowser' })"
Write-Host ""
Write-Host "After restart/login Windows will run the stack automatically."
Write-Host "Docker Desktop must be installed and allowed to start with Windows."
Write-Host ""
Write-Host "Manage:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Format-List"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  .\scripts\register-radiosense-startup-task.ps1 -Unregister"