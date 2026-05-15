<#
.SYNOPSIS
    Wires up all tool config symlinks/junctions from ops-developer-config.

.DESCRIPTION
    Creates junctions (directories) and symlinks (files) from each tool's
    expected config location into this repository. Run once on each new machine.
    Requires Developer Mode enabled (Settings -> For Developers -> Developer Mode)
    or an Administrator shell for file symlinks.

    On machines where symlinks are blocked (e.g. by Group Policy), the script
    falls back to copying files and prints a reminder to re-run this script after
    each git pull.

    Skills are sourced from this repository's skills/ directory. The repo may
    group skills by purpose, but any descendant directory containing SKILL.md is
    installed flat into ~/.claude/skills and ~/.codex/skills. Per-skill
    junctions are preferred; if junction creation fails, the skill directory is
    copied and marked as managed. Codex-managed system skills under
    ~/.codex/skills/.system are preserved. The legacy ~/.agents/skills junction
    is removed only when it points at this repo's skills directory.

.PARAMETER Repo
    Absolute path to the ops-developer-config repository root.
    Defaults to the parent directory of this script.

.PARAMETER InstallScheduledTask
    Register or update a per-user scheduled task that runs this script at user
    logon. This does not require local administrator privileges.

.PARAMETER TaskName
    Name of the per-user scheduled task created by -InstallScheduledTask.

.EXAMPLE
    .\Install-DeveloperConfig.ps1
    .\Install-DeveloperConfig.ps1 -Repo "C:\Local Files\Repositories\ops-developer-config"
    .\Install-DeveloperConfig.ps1 -InstallScheduledTask
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param (
    [string]$Repo = (Resolve-Path "$PSScriptRoot\..").Path,
    [switch]$InstallScheduledTask,
    [string]$TaskName = "Install Developer Config"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:copyFallback = 0

# -- Helpers ----------------------------------------------------------------

function Remove-IfReal {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $item) { return }
    $isReparse = $item.Attributes -band [System.IO.FileAttributes]::ReparsePoint
    if ($isReparse) { return }  # already a junction/symlink, let callers decide
    Write-Host "  [remove] $Path (real item - repo is source of truth)" -ForegroundColor Yellow
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function New-Junction {
    param([string]$Link, [string]$Target)
    $item = Get-Item -LiteralPath $Link -ErrorAction SilentlyContinue
    if ($item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        Write-Host "  [skip] $Link already linked" -ForegroundColor DarkGray
        return
    }
    Remove-IfReal $Link
    New-Item -ItemType Directory -Path (Split-Path $Link) -Force | Out-Null
    cmd /c mklink /J `"$Link`" `"$Target`" | Out-Null
    Write-Host "  [junction] $Link -> $Target" -ForegroundColor Green
}

function New-Symlink {
    param([string]$Link, [string]$Target)
    $item = Get-Item -LiteralPath $Link -ErrorAction SilentlyContinue
    if ($item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        Write-Host "  [skip] $Link already linked" -ForegroundColor DarkGray
        return
    }
    Remove-IfReal $Link
    New-Item -ItemType Directory -Path (Split-Path $Link) -Force | Out-Null

    if ($canSymlink) {
        try {
            New-Item -ItemType SymbolicLink -Path $Link -Value $Target -ErrorAction Stop | Out-Null
            Write-Host "  [symlink] $Link -> $Target" -ForegroundColor Green
            return
        } catch {
            Write-Host "  [warn] Symlink failed ($($_.Exception.Message)), falling back to copy" -ForegroundColor Yellow
        }
    }

    # Copy fallback
    Copy-Item -LiteralPath $Target -Destination $Link -Force
    Write-Host "  [copy]    $Link <- $Target" -ForegroundColor Cyan
    $script:copyFallback++
}

function ConvertTo-ComparablePath {
    param([string]$Path)
    try {
        return ([System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path)).TrimEnd("\")
    } catch {
        return ([System.IO.Path]::GetFullPath($Path)).TrimEnd("\")
    }
}

function Test-ReparseTarget {
    param([string]$Link, [string]$ExpectedTarget)
    $item = Get-Item -LiteralPath $Link -ErrorAction SilentlyContinue
    if (-not $item) { return $false }
    if (-not ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { return $false }

    $expected = ConvertTo-ComparablePath $ExpectedTarget
    foreach ($target in @($item.Target)) {
        if (-not $target) { continue }
        if ((ConvertTo-ComparablePath $target) -ieq $expected) {
            return $true
        }
    }
    return $false
}

function Remove-DirectoryReparsePoint {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $item) { return }
    if (-not ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "Refusing to remove non-reparse directory: $Path"
    }
    [System.IO.Directory]::Delete($Path)
}

function Initialize-SkillsDirectory {
    param([string]$Path, [string]$RepoSkills, [string]$ToolName)
    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    if ($item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        if (Test-ReparseTarget $Path $RepoSkills) {
            Remove-DirectoryReparsePoint $Path
            Write-Host "  [remove] $Path legacy whole-directory junction" -ForegroundColor Yellow
        } else {
            Write-Host "  [warn] $Path is linked elsewhere; leaving $ToolName skills unchanged" -ForegroundColor Yellow
            return $false
        }
    }

    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    return $true
}

function Get-RepoSkills {
    param([string]$RepoSkills)

    $skills = Get-ChildItem -LiteralPath $RepoSkills -Recurse -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") } |
        Sort-Object -Property Name

    $duplicates = $skills |
        Group-Object -Property Name |
        Where-Object { $_.Count -gt 1 }

    if ($duplicates) {
        $names = ($duplicates | ForEach-Object { $_.Name }) -join ", "
        throw "Duplicate skill folder name(s) found under $RepoSkills`: $names"
    }

    return $skills
}

function Test-PathIsUnder {
    param([string]$Path, [string]$Parent)

    $candidate = (ConvertTo-ComparablePath $Path).TrimEnd("\")
    $root = (ConvertTo-ComparablePath $Parent).TrimEnd("\")
    return $candidate.StartsWith("$root\", [System.StringComparison]::OrdinalIgnoreCase)
}

function Remove-StaleManagedSkills {
    param([string]$SkillsRoot, [string]$RepoSkills, [object[]]$Skills)

    $expectedNames = @{}
    $Skills | ForEach-Object { $expectedNames[$_.Name] = $true }

    Get-ChildItem -LiteralPath $SkillsRoot -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -ne ".system") {
            $managedMarker = Join-Path $_.FullName ".managed-by-ops-developer-config"
            $isExpected = $expectedNames.ContainsKey($_.Name)
            $isReparse = $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint

            if ($isReparse) {
                $targets = @(@($_.Target) | Where-Object { $_ })
                $pointsIntoRepoSkills = $targets | Where-Object { Test-PathIsUnder $_ $RepoSkills }

                if ($pointsIntoRepoSkills -and ((-not $isExpected) -or (-not (Test-Path -LiteralPath ($targets[0]))))) {
                    Remove-DirectoryReparsePoint $_.FullName
                    Write-Host "  [remove] $($_.FullName) stale managed skill" -ForegroundColor Yellow
                }
            } elseif ((Test-Path -LiteralPath $managedMarker) -and (-not $isExpected)) {
                Remove-Item -LiteralPath $_.FullName -Recurse -Force
                Write-Host "  [remove] $($_.FullName) stale managed skill copy" -ForegroundColor Yellow
            }
        }
    }
}

function Install-Skill {
    param([string]$Source, [string]$Destination)

    $managedMarker = Join-Path $Destination ".managed-by-ops-developer-config"
    $item = Get-Item -LiteralPath $Destination -ErrorAction SilentlyContinue

    if ($item) {
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            if (Test-ReparseTarget $Destination $Source) {
                Write-Host "  [skip] $Destination already linked" -ForegroundColor DarkGray
                return
            }

            Remove-DirectoryReparsePoint $Destination
        } elseif (Test-Path -LiteralPath $managedMarker) {
            Remove-Item -LiteralPath $Destination -Recurse -Force
        } else {
            Write-Host "  [skip] $Destination exists and is not managed" -ForegroundColor Yellow
            return
        }
    }

    New-Item -ItemType Directory -Path (Split-Path $Destination) -Force | Out-Null

    try {
        New-Item -ItemType Junction -Path $Destination -Target $Source -ErrorAction Stop | Out-Null
        Write-Host "  [junction] $Destination -> $Source" -ForegroundColor Green
    } catch {
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
        New-Item -ItemType File -Path $managedMarker -Force | Out-Null
        Write-Host "  [copy]     $Destination <- $Source" -ForegroundColor Cyan
        $script:copyFallback++
    }
}

function Install-Skills {
    param([string]$SkillsRoot, [string]$RepoSkills, [string]$ToolName, [object[]]$Skills)

    if (-not (Initialize-SkillsDirectory $SkillsRoot $RepoSkills $ToolName)) {
        return
    }

    Remove-StaleManagedSkills $SkillsRoot $RepoSkills $Skills

    $Skills | ForEach-Object {
        Install-Skill $_.FullName (Join-Path $SkillsRoot $_.Name)
    }
}

function Remove-LegacyAgentsSkillsJunction {
    param([string]$Link, [string]$RepoSkills)
    $item = Get-Item -LiteralPath $Link -ErrorAction SilentlyContinue
    if (-not $item) { return }

    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -and (Test-ReparseTarget $Link $RepoSkills)) {
        Remove-DirectoryReparsePoint $Link
        Write-Host "  [remove] $Link legacy Codex skills junction" -ForegroundColor Yellow
        return
    }

    Write-Host "  [skip] $Link exists and is not the legacy repo junction" -ForegroundColor DarkGray
}

function ConvertTo-TaskArgument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return '"' + ($Value -replace '"', '\"') + '"'
}

function Register-UserLogonTask {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,

        [Parameter(Mandatory = $true)]
        [string]$RepoPath,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $powerShellPath = Join-Path -Path $PSHOME -ChildPath "powershell.exe"
    $arguments = @(
        "-NoProfile"
        "-ExecutionPolicy"
        "Bypass"
        "-File"
        (ConvertTo-TaskArgument -Value $ScriptPath)
        "-Repo"
        (ConvertTo-TaskArgument -Value $RepoPath)
    )

    $action = New-ScheduledTaskAction -Execute $powerShellPath -Argument ($arguments -join " ")
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
        -MultipleInstances IgnoreNew

    if ($PSCmdlet.ShouldProcess($Name, "Register per-user scheduled task")) {
        Register-ScheduledTask `
            -TaskName $Name `
            -Action $action `
            -Trigger $trigger `
            -Principal $principal `
            -Settings $settings `
            -Description "Runs $ScriptPath at user logon." `
            -Force | Out-Null

        return $true
    }

    return $false
}

if ($InstallScheduledTask) {
    $scriptPath = (Resolve-Path -LiteralPath $PSCommandPath -ErrorAction Stop).Path
    $repoPath = (Resolve-Path -LiteralPath $Repo -ErrorAction Stop).Path
    $taskRegistered = Register-UserLogonTask `
        -ScriptPath $scriptPath `
        -RepoPath $repoPath `
        -Name $TaskName

    if ($taskRegistered) {
        Write-Host "Scheduled task registered: $TaskName"
    } else {
        Write-Host "Scheduled task registration skipped: $TaskName"
    }
    Write-Host "Script path: $scriptPath"
    Write-Host "Repo path: $repoPath"
    return
}

# -- Preflight: can we create file symlinks? -------------------------------

$canSymlink = $false
$testTarget = [System.IO.Path]::GetTempFileName()
$testLink = $testTarget + ".lnk"
try {
    New-Item -ItemType SymbolicLink -Path $testLink -Value $testTarget -ErrorAction Stop | Out-Null
    Remove-Item $testLink -Force -ErrorAction SilentlyContinue
    $canSymlink = $true
} catch { }
finally {
    Remove-Item $testTarget -Force -ErrorAction SilentlyContinue
}

if (-not $canSymlink) {
    Write-Host @"

  WARNING: File symlinks are not available on this machine.
  Cause:   Group Policy likely overrides Developer Mode (common on domain-joined
           corporate machines). Admin shells are unaffected.

  Falling back to file copies for all symlink targets.
  After each 'git pull', re-run this script to refresh the copies.

  To get true symlinks: re-run from an Administrator shell.

"@ -ForegroundColor Yellow
}

# -- Skills (repo source of truth) -----------------------------------------

Write-Host "`nSkills" -ForegroundColor Cyan
$claude = "$env:USERPROFILE\.claude"
$codex = "$env:USERPROFILE\.codex"
$repoSkills = "$Repo\skills"
$skills = @(Get-RepoSkills $repoSkills)
Install-Skills "$claude\skills" $repoSkills "Claude" $skills
Install-Skills "$codex\skills" $repoSkills "Codex" $skills
Remove-LegacyAgentsSkillsJunction "$env:USERPROFILE\.agents\skills" "$Repo\skills"

# -- Claude ----------------------------------------------------------------

Write-Host "`nClaude" -ForegroundColor Cyan
New-Junction "$claude\docs" "$Repo\docs"
New-Symlink "$claude\CLAUDE.md" "$Repo\CLAUDE.md"
New-Symlink "$claude\settings.json" "$Repo\claude\settings.json"

# -- Codex -----------------------------------------------------------------

Write-Host "`nCodex" -ForegroundColor Cyan
New-Symlink "$codex\instructions.md" "$Repo\codex\instructions.md"
New-Symlink "$codex\config.toml" "$Repo\codex\config.toml"

# -- VS Code ---------------------------------------------------------------

Write-Host "`nVS Code" -ForegroundColor Cyan
$vscodeUser = "$env:APPDATA\Code\User"
New-Symlink "$vscodeUser\settings.json" "$Repo\vscode\settings.json"
New-Symlink "$vscodeUser\keybindings.json" "$Repo\vscode\keybindings.json"

# -- Git -------------------------------------------------------------------

Write-Host "`nGit" -ForegroundColor Cyan
$gitignorePath = "$env:USERPROFILE\.gitignore_global"
New-Symlink $gitignorePath "$Repo\git\gitignore_global"

# Wire the global gitignore if not already set
$currentExcludesFile = git config --global core.excludesfile 2>$null
if (-not $currentExcludesFile) {
    git config --global core.excludesfile $gitignorePath
    Write-Host "  [config] core.excludesfile = $gitignorePath" -ForegroundColor Green
} else {
    Write-Host "  [skip] core.excludesfile already set to $currentExcludesFile" -ForegroundColor DarkGray
}

# Wire global git hooks
$hooksPath = "$Repo\git\hooks"
$currentHooksPath = git config --global core.hooksPath 2>$null
if (-not $currentHooksPath) {
    git config --global core.hooksPath $hooksPath
    Write-Host "  [config] core.hooksPath = $hooksPath" -ForegroundColor Green
} else {
    Write-Host "  [skip] core.hooksPath already set to $currentHooksPath" -ForegroundColor DarkGray
}

# Remind about the shared git config include
$configShared = "$Repo\git\config.shared"
Write-Host @"

  To enable shared git aliases and settings, add this to ~/.gitconfig:

      [include]
          path = $configShared

"@ -ForegroundColor Yellow

# -- Done ------------------------------------------------------------------

if ($script:copyFallback -gt 0) {
    Write-Host "Done. $($script:copyFallback) file(s) copied (not linked) -- re-run this script after git pull.`n" -ForegroundColor Cyan
} else {
    Write-Host "Done. All links created.`n" -ForegroundColor Green
}
