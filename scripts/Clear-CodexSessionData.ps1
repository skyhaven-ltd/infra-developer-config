[CmdletBinding(SupportsShouldProcess = $true)]
param (
    [string]$CodexDirectory = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }),
    [string]$TemporaryDirectory = [IO.Path]::GetTempPath(),
    [string]$EditorLogDirectory = (Join-Path $env:APPDATA "Code\logs"),
    [switch]$InstallScheduledTask
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Get-Item -LiteralPath $CodexDirectory -Force
if (-not $root.PSIsContainer -or $root.PSProvider.Name -ne "FileSystem") {
    throw "CodexDirectory must be a filesystem directory."
}
$rootPath = $root.FullName.TrimEnd('\')
$ancestor = $root
while ($null -ne $ancestor) {
    if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing a Codex directory with a linked ancestor: $($ancestor.FullName)"
    }
    $ancestor = $ancestor.Parent
}
if (-not (Test-Path -LiteralPath (Join-Path $rootPath "config.toml") -PathType Leaf)) {
    throw "Expected config.toml in the Codex directory."
}

if ($InstallScheduledTask) {
    $taskName = "Codex Session Cleanup"
    $executable = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
    $arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -CodexDirectory "{1}" -TemporaryDirectory "{2}" -EditorLogDirectory "{3}"' -f $PSCommandPath, $rootPath, ([IO.Path]::GetFullPath($TemporaryDirectory).TrimEnd('\')), ([IO.Path]::GetFullPath($EditorLogDirectory).TrimEnd('\'))
    $action = New-ScheduledTaskAction -Execute $executable -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -Daily -At "17:00"
    $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -RestartCount 16 -RestartInterval (New-TimeSpan -Minutes 15)
    if ($PSCmdlet.ShouldProcess($taskName, "Register daily 17:00 session cleanup")) {
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Delete local Codex session data when Codex is closed; preserve authentication and configuration." -Force | Out-Null
        Write-Output "Registered $taskName for 17:00 local time. No session data was deleted."
    }
    return
}

if (-not $WhatIfPreference -and @(Get-Process -Name "codex*" -ErrorAction SilentlyContinue).Count -gt 0) {
    throw "Codex is running. Close the app and CLI sessions before cleanup. Scheduled runs retry in 15 minutes."
}

$directoryNames = @(
    "sessions", "archived_sessions", "log", "logs", "memories", "cache",
    "tmp", ".tmp", "generated_images", "shell_snapshots", "thread-writer-locks"
)
$fileNames = @("history.jsonl", "session_index.jsonl", "sandbox.log", ".codex-global-state.json", ".codex-global-state.json.bak")
$targets = @(Get-ChildItem -LiteralPath $rootPath -Force | Where-Object {
    ($_.PSIsContainer -and $_.Name -in $directoryNames) -or
    (-not $_.PSIsContainer -and ($_.Name -in $fileNames -or $_.Name -match '^(state|logs|memories|goals|queue|thread_history)_\d+\.sqlite(-wal|-shm|-journal)?$'))
})

function Assert-CleanupTree {
    param ([System.IO.FileSystemInfo]$Item, [string]$Boundary = $rootPath)

    if (-not $Item.FullName.StartsWith($Boundary + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Cleanup path is outside its allowed directory: $($Item.FullName)"
    }
    if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing to delete a linked cleanup path: $($Item.FullName)"
    }
    if ($Item.PSIsContainer) {
        foreach ($child in Get-ChildItem -LiteralPath $Item.FullName -Force) {
            Assert-CleanupTree -Item $child -Boundary $Boundary
        }
    }
}

function Get-NotifierLogs {
    param ([string]$Directory)

    foreach ($item in Get-ChildItem -LiteralPath $Directory -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing a linked editor log path: $($item.FullName)"
        }
        if ($item.PSIsContainer) {
            Get-NotifierLogs -Directory $item.FullName
        } elseif ($item.Name -match '^\d+-Codex Finish Notifier\.log$') {
            $item
        }
    }
}

$cleanupTargets = @($targets | ForEach-Object { [pscustomobject]@{ Item = $_; Boundary = $rootPath } })
$sandboxPath = Join-Path $rootPath ".sandbox"
if (Test-Path -LiteralPath $sandboxPath) {
    Assert-CleanupTree -Item (Get-Item -LiteralPath $sandboxPath -Force)
    $sandboxLog = Join-Path $sandboxPath "sandbox.log"
    if (Test-Path -LiteralPath $sandboxLog -PathType Leaf) {
        $cleanupTargets += [pscustomobject]@{ Item = Get-Item -LiteralPath $sandboxLog -Force; Boundary = $rootPath }
    }
}
foreach ($location in @($TemporaryDirectory, $EditorLogDirectory)) {
    if (-not (Test-Path -LiteralPath $location)) { continue }
    $locationItem = Get-Item -LiteralPath $location -Force
    if (-not $locationItem.PSIsContainer -or $locationItem.PSProvider.Name -ne "FileSystem") {
        throw "Expected a filesystem cleanup directory: $location"
    }
    $ancestor = $locationItem
    while ($null -ne $ancestor) {
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing a cleanup directory with a linked ancestor: $($ancestor.FullName)"
        }
        $ancestor = $ancestor.Parent
    }
    $boundary = $locationItem.FullName.TrimEnd('\')
    if ($location -eq $TemporaryDirectory) {
        $extraTargets = @(Get-ChildItem -LiteralPath $boundary -Force | Where-Object {
            -not $_.PSIsContainer -and $_.Name -match '^codex-clipboard-[a-zA-Z0-9_-]+\.png$'
        })
    } else {
        $extraTargets = @(Get-NotifierLogs -Directory $boundary)
    }
    $cleanupTargets += @($extraTargets | ForEach-Object { [pscustomobject]@{ Item = $_; Boundary = $boundary } })
}
foreach ($target in $cleanupTargets) {
    Assert-CleanupTree -Item $target.Item -Boundary $target.Boundary
}
$failedTargets = 0
foreach ($target in $cleanupTargets) {
    if ($PSCmdlet.ShouldProcess($target.Item.FullName, "Permanently delete local session data (not secure erasure)")) {
        Assert-CleanupTree -Item (Get-Item -LiteralPath $target.Item.FullName -Force) -Boundary $target.Boundary
        try {
            Remove-Item -LiteralPath $target.Item.FullName -Recurse -Force
        } catch [System.IO.IOException], [System.UnauthorizedAccessException] {
            $failedTargets++
            Write-Warning "Could not fully remove '$($target.Item.FullName)': $($_.Exception.Message) Close the app using the file or check permissions, then rerun cleanup."
            continue
        }
        if (Test-Path -LiteralPath $target.Item.FullName) {
            $failedTargets++
            Write-Warning "Cleanup target still exists: $($target.Item.FullName)"
        }
    }
}
if ($failedTargets -gt 0) {
    Write-Warning "Session cleanup incomplete: $failedTargets target(s) could not be fully removed. Other eligible targets were processed. Rerun cleanup after resolving the warnings."
} else {
    Write-Output "Session cleanup finished. Unknown files and preserved configuration are not removed."
}
