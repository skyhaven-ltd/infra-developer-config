$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "..\Clear-CodexSessionData.ps1"
$fixture = Join-Path ([IO.Path]::GetTempPath()) ("codex-cleanup-test-" + [guid]::NewGuid())
$codexFixture = Join-Path $fixture ".codex"
$outside = Join-Path $fixture "outside"
$temporaryFixture = Join-Path $fixture "temp"
$editorFixture = Join-Path $fixture "editor-logs"
$cleanupArguments = @{ CodexDirectory = $codexFixture; TemporaryDirectory = $temporaryFixture; EditorLogDirectory = $editorFixture }
New-Item -ItemType Directory -Path $codexFixture, $outside, $temporaryFixture, (Join-Path $editorFixture "window1") | Out-Null

function Assert-True {
    param ([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Get-Process {
    param ($Name, $ErrorAction)
    if ($simulateRunning) { [pscustomobject]@{ ProcessName = "codex" } }
}

try {
    New-Item -ItemType Directory -Path (Join-Path $codexFixture ".sandbox"), (Join-Path $codexFixture ".sandbox-bin") | Out-Null
    Set-Content -LiteralPath (Join-Path $codexFixture ".sandbox\sandbox.log") -Value "sandbox activity"
    Set-Content -LiteralPath (Join-Path $codexFixture ".sandbox\setup.json") -Value "preserve setup"
    Set-Content -LiteralPath (Join-Path $codexFixture ".sandbox-bin\codex.exe") -Value "preserve tooling"
    Set-Content -LiteralPath (Join-Path $temporaryFixture "codex-clipboard-abc123.png") -Value "test image"
    Set-Content -LiteralPath (Join-Path $temporaryFixture "unrelated.png") -Value "preserve image"
    Set-Content -LiteralPath (Join-Path $temporaryFixture "codex-project-work.md") -Value "preserve work"
    Set-Content -LiteralPath (Join-Path $editorFixture "window1\10-Codex Finish Notifier.log") -Value "test notification"
    Set-Content -LiteralPath (Join-Path $editorFixture "window1\other.log") -Value "preserve log"
    foreach ($name in @("config.toml", "auth.json", "AGENTS.md", "unknown.txt")) {
        Set-Content -LiteralPath (Join-Path $codexFixture $name) -Value "preserve-$name"
    }
    New-Item -ItemType Directory -Path (Join-Path $codexFixture "sessions"), (Join-Path $codexFixture "skills") | Out-Null
    Set-Content -LiteralPath (Join-Path $codexFixture "sessions\sample.jsonl") -Value "test session"
    Set-Content -LiteralPath (Join-Path $codexFixture "skills\test.md") -Value "test skill"
    foreach ($name in @("history.jsonl", "state_5.sqlite", "state_5.sqlite-wal", "state_5.sqlite-shm", "queue_1.sqlite", "thread_history_1.sqlite")) {
        Set-Content -LiteralPath (Join-Path $codexFixture $name) -Value "test data"
    }
    $script:simulateRunning = $true
    $blocked = $false
    try { & $scriptPath @cleanupArguments } catch {
        if ($_.Exception.Message -notlike "Codex is running.*") { throw }
        $blocked = $true
    }
    Assert-True $blocked "Active Codex must block deletion."
    Assert-True (Test-Path -LiteralPath (Join-Path $codexFixture "history.jsonl")) "Active-process check deleted history."
    & $scriptPath @cleanupArguments -WhatIf
    Assert-True (Test-Path -LiteralPath (Join-Path $codexFixture "sessions\sample.jsonl")) "WhatIf deleted a session."
    Assert-True (Test-Path -LiteralPath (Join-Path $temporaryFixture "codex-clipboard-abc123.png")) "WhatIf deleted a clipboard image."
    Assert-True (Test-Path -LiteralPath (Join-Path $editorFixture "window1\10-Codex Finish Notifier.log")) "WhatIf deleted a notifier log."
    $script:simulateRunning = $false
    Set-Content -LiteralPath (Join-Path $outside "keep.txt") -Value "outside data"
    $linkPath = Join-Path $codexFixture "sessions\linked"
    New-Item -ItemType Junction -Path $linkPath -Target $outside | Out-Null
    $blocked = $false
    try { & $scriptPath @cleanupArguments } catch {
        if ($_.Exception.Message -notlike "Refusing to delete a linked cleanup path:*") { throw }
        $blocked = $true
    }
    Assert-True $blocked "Linked session tree must block deletion."
    Assert-True (Test-Path -LiteralPath (Join-Path $outside "keep.txt")) "External file was deleted."
    Assert-True (Test-Path -LiteralPath (Join-Path $codexFixture "history.jsonl")) "Preflight failure caused partial deletion."
    [IO.Directory]::Delete($linkPath)
    $externalLink = Join-Path $editorFixture "linked"
    New-Item -ItemType Junction -Path $externalLink -Target $outside | Out-Null
    $blocked = $false
    try { & $scriptPath @cleanupArguments } catch {
        if ($_.Exception.Message -notlike "Refusing a linked editor log path:*") { throw }
        $blocked = $true
    }
    Assert-True $blocked "Linked editor tree must block deletion."
    Assert-True (Test-Path -LiteralPath (Join-Path $temporaryFixture "codex-clipboard-abc123.png")) "Editor preflight failure deleted an image."
    [IO.Directory]::Delete($externalLink)
    & $scriptPath @cleanupArguments
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $temporaryFixture "codex-clipboard-abc123.png"))) "Cleanup left a clipboard image."
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $editorFixture "window1\10-Codex Finish Notifier.log"))) "Cleanup left a notifier log."
    Assert-True (Test-Path -LiteralPath (Join-Path $temporaryFixture "unrelated.png")) "Cleanup deleted an unrelated image."
    Assert-True (Test-Path -LiteralPath (Join-Path $temporaryFixture "codex-project-work.md")) "Cleanup deleted task output."
    Assert-True (Test-Path -LiteralPath (Join-Path $editorFixture "window1\other.log")) "Cleanup deleted an unrelated log."
    foreach ($name in @("sessions", "history.jsonl", "state_5.sqlite", "state_5.sqlite-wal", "state_5.sqlite-shm", "queue_1.sqlite", "thread_history_1.sqlite")) {
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $codexFixture $name))) "Cleanup left $name."
    }
    foreach ($name in @("config.toml", "auth.json", "AGENTS.md", "unknown.txt")) {
        Assert-True ((Get-Content -LiteralPath (Join-Path $codexFixture $name) -Raw).Trim() -eq "preserve-$name") "Cleanup changed $name."
    }
    Assert-True (Test-Path -LiteralPath (Join-Path $codexFixture "skills\test.md")) "Cleanup deleted a skill."
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $codexFixture ".sandbox\sandbox.log"))) "Cleanup left the sandbox log."
    Assert-True (Test-Path -LiteralPath (Join-Path $codexFixture ".sandbox\setup.json")) "Cleanup deleted sandbox setup."
    Assert-True (Test-Path -LiteralPath (Join-Path $codexFixture ".sandbox-bin\codex.exe")) "Cleanup deleted sandbox tooling."
    & $scriptPath @cleanupArguments
    $lockedLog = Join-Path $editorFixture "window1\10-Codex Finish Notifier.log"
    $laterLog = Join-Path $editorFixture "window1\11-Codex Finish Notifier.log"
    Set-Content -LiteralPath $lockedLog -Value "active log"
    Set-Content -LiteralPath $laterLog -Value "old log"
    $handle = [IO.File]::Open($lockedLog, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    try {
        $cleanupOutput = & $scriptPath @cleanupArguments -WarningVariable cleanupWarnings -WarningAction SilentlyContinue
        Assert-True (Test-Path -LiteralPath $lockedLog) "Cleanup removed a locked log."
        Assert-True (-not (Test-Path -LiteralPath $laterLog)) "Locked log prevented remaining cleanup."
        Assert-True (@($cleanupWarnings | Where-Object { $_.Message -like "*10-Codex Finish Notifier.log*" }).Count -gt 0) "Locked log was not flagged."
        Assert-True (@($cleanupWarnings | Where-Object { $_.Message -like "Session cleanup incomplete:*" }).Count -eq 1) "Incomplete cleanup was not reported."
        Assert-True (@($cleanupOutput | Where-Object { $_ -like "Session cleanup finished.*" }).Count -eq 0) "Incomplete cleanup reported success."
    }
    finally {
        $handle.Dispose()
    }
    & $scriptPath @cleanupArguments
    Assert-True (-not (Test-Path -LiteralPath $lockedLog)) "Cleanup did not remove the released log."
    Write-Output "PASS: running-process guard, preview, link guard, deletion, preservation, repeated cleanup, locked-log warning and recovery."
}
finally {
    $fixturePath = [IO.Path]::GetFullPath($fixture)
    $tempPath = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $fixturePath.StartsWith($tempPath, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path $fixturePath -Leaf) -notlike "codex-cleanup-test-*") {
        throw "Unexpected fixture path: $fixturePath"
    }
    $remainingLink = Join-Path $codexFixture "sessions\linked"
    if (Test-Path -LiteralPath $remainingLink) { [IO.Directory]::Delete($remainingLink) }
    $remainingEditorLink = Join-Path $editorFixture "linked"
    if (Test-Path -LiteralPath $remainingEditorLink) { [IO.Directory]::Delete($remainingEditorLink) }
    Remove-Item -LiteralPath $fixturePath -Recurse -Force
}
