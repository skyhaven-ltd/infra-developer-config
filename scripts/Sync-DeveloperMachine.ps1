<#
.SYNOPSIS
    One-shot machine sync: clone/pull all organisation repositories and install
    developer config.

.DESCRIPTION
    Idempotent orchestrator intended to be the single entry point on any
    machine. Each run:

      1. Registers (or refreshes) a per-user scheduled task that re-runs this
         script at every user logon, and removes the legacy per-script tasks
         ("Git Pull All Repositories", "Install Developer Config"). Per-user
         tasks run at RunLevel Limited and need no local administrator rights.
      2. Lists all non-archived repositories in the GitHub organisation via the
         gh CLI and clones any that are missing under -CloneRoot, so the set of
         repositories can change over time without touching the machine.
      3. Runs Update-GitRepositories.ps1 to fast-forward pull every repository
         under -RepositoriesRoot (honouring the per-machine include list).
      4. Runs Install-DeveloperConfig.ps1 to (re)install skills and config
         links, including every ~/.claude* and ~/.codex* profile directory.

    Run it once manually on a new machine; the scheduled task keeps everything
    in sync from then on.

    Requires the gh CLI to be installed and authenticated (gh auth login) and
    git credentials for HTTPS clones (gh auth setup-git wires gh in as the git
    credential helper).

.PARAMETER Organization
    GitHub organisation whose repositories are cloned. Defaults to skyhaven-ltd.

.PARAMETER RepositoriesRoot
    Root directory below which Git repositories are discovered and pulled.
    Defaults to:
      1. $env:REPOSITORIES_ROOT, when set
      2. C:\Local Files\Repositories, when it exists
      3. the current user's Documents\Repositories path

.PARAMETER CloneRoot
    Directory where missing organisation repositories are cloned. Defaults to
    "<RepositoriesRoot>\Sky Haven".

.PARAMETER NoScheduledTask
    Skip registering/refreshing the per-user logon scheduled task and skip
    removing the legacy per-script tasks.

.PARAMETER TaskName
    Name of the per-user logon scheduled task.

.PARAMETER LogPath
    Optional log file path. When omitted, a per-user log is written under:
    $env:LOCALAPPDATA\ops-developer-config\sync-developer-machine.log

.PARAMETER SkipClone
    Skip the organisation clone step (pull and install only). Useful offline
    or when gh is unavailable.

.EXAMPLE
    .\Sync-DeveloperMachine.ps1

.EXAMPLE
    .\Sync-DeveloperMachine.ps1 -RepositoriesRoot "D:\Repos" -CloneRoot "D:\Repos\Sky Haven"

.EXAMPLE
    .\Sync-DeveloperMachine.ps1 -NoScheduledTask -SkipClone
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param (
    [string]$Organization = "skyhaven-ltd",
    [string]$RepositoriesRoot,
    [string]$CloneRoot,
    [switch]$NoScheduledTask,
    [string]$TaskName = "Sync Developer Machine",
    [string]$LogPath,
    [switch]$SkipClone
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DefaultRepositoriesRoot {
    if (-not [string]::IsNullOrWhiteSpace($env:REPOSITORIES_ROOT)) {
        return $env:REPOSITORIES_ROOT
    }

    $standardRoot = "C:\Local Files\Repositories"
    if (Test-Path -LiteralPath $standardRoot -PathType Container) {
        return $standardRoot
    }

    return (Join-Path -Path ([Environment]::GetFolderPath("MyDocuments")) -ChildPath "Repositories")
}

function ConvertTo-TaskArgument {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return '"' + ($Value -replace '"', '\"') + '"'
}

function Get-PowerShellExecutablePath {
    $currentPowerShell = Join-Path -Path $PSHOME -ChildPath "powershell.exe"
    if (Test-Path -LiteralPath $currentPowerShell -PathType Leaf) {
        return $currentPowerShell
    }

    $windowsPowerShell = Join-Path -Path $env:WINDIR -ChildPath "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf) {
        return $windowsPowerShell
    }

    $pathPowerShell = Get-Command powershell.exe -ErrorAction SilentlyContinue
    if ($pathPowerShell) {
        return $pathPowerShell.Source
    }

    throw "Unable to find powershell.exe for scheduled task action."
}

function Get-GhExecutablePath {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) {
        return $gh.Source
    }

    $defaultPath = "C:\Program Files\GitHub CLI\gh.exe"
    if (Test-Path -LiteralPath $defaultPath -PathType Leaf) {
        return $defaultPath
    }

    throw "gh CLI was not found. Install it from https://cli.github.com/ and run 'gh auth login'."
}

function Write-Log {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $line = "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ssK")] $Message"
    Write-Host $Message
    Add-Content -LiteralPath $script:resolvedLogPath -Value $line
}

function Register-UserLogonTask {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param (
        [Parameter(Mandatory = $true)]
        [string]$ResolvedScriptPath,

        [Parameter(Mandatory = $true)]
        [string]$ResolvedOrganization,

        [Parameter(Mandatory = $true)]
        [string]$ResolvedRepositoriesRoot,

        [Parameter(Mandatory = $true)]
        [string]$ResolvedCloneRoot,

        [Parameter(Mandatory = $true)]
        [string]$ResolvedLogPath,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $powerShellPath = Get-PowerShellExecutablePath
    $arguments = @(
        "-NoProfile"
        "-ExecutionPolicy"
        "Bypass"
        "-File"
        (ConvertTo-TaskArgument -Value $ResolvedScriptPath)
        "-Organization"
        (ConvertTo-TaskArgument -Value $ResolvedOrganization)
        "-RepositoriesRoot"
        (ConvertTo-TaskArgument -Value $ResolvedRepositoriesRoot)
        "-CloneRoot"
        (ConvertTo-TaskArgument -Value $ResolvedCloneRoot)
        "-LogPath"
        (ConvertTo-TaskArgument -Value $ResolvedLogPath)
    )

    $action = New-ScheduledTaskAction -Execute $powerShellPath -Argument ($arguments -join " ")
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
        -MultipleInstances IgnoreNew

    if ($PSCmdlet.ShouldProcess($Name, "Register per-user scheduled task")) {
        Register-ScheduledTask `
            -TaskName $Name `
            -Action $action `
            -Trigger $trigger `
            -Principal $principal `
            -Settings $settings `
            -Description "Clones/pulls $ResolvedOrganization repositories and installs developer config at user logon." `
            -Force | Out-Null

        return $true
    }

    return $false
}

function Remove-LegacyLogonTask {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $existingTask = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
        Write-Log "Removed legacy scheduled task: $Name"
    }
}

# -- Resolve parameters ------------------------------------------------------

if ([string]::IsNullOrWhiteSpace($RepositoriesRoot)) {
    $RepositoriesRoot = Get-DefaultRepositoriesRoot
}

if (-not (Test-Path -LiteralPath $RepositoriesRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $RepositoriesRoot -Force | Out-Null
}
$repositoriesRootPath = (Resolve-Path -LiteralPath $RepositoriesRoot).Path

if ([string]::IsNullOrWhiteSpace($CloneRoot)) {
    $CloneRoot = Join-Path -Path $repositoriesRootPath -ChildPath "Sky Haven"
}

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $logDirectory = Join-Path -Path $env:LOCALAPPDATA -ChildPath "ops-developer-config"
    $LogPath = Join-Path -Path $logDirectory -ChildPath "sync-developer-machine.log"
}

$logDirectoryPath = Split-Path -Path $LogPath -Parent
if (-not [string]::IsNullOrWhiteSpace($logDirectoryPath)) {
    New-Item -ItemType Directory -Path $logDirectoryPath -Force | Out-Null
}
$script:resolvedLogPath = $LogPath

$scriptPath = (Resolve-Path -LiteralPath $PSCommandPath -ErrorAction Stop).Path
$scriptsDirectory = Split-Path -Path $scriptPath -Parent
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptsDirectory "..")).Path

Add-Content -LiteralPath $script:resolvedLogPath -Value ""
Write-Log "Starting developer machine sync (organization: $Organization)"

$failedClones = New-Object System.Collections.Generic.List[string]

# -- Step 0: ensure the logon scheduled task ---------------------------------

if ($NoScheduledTask) {
    Write-Log "Scheduled task step skipped (-NoScheduledTask)."
} else {
    $taskRegistered = Register-UserLogonTask `
        -ResolvedScriptPath $scriptPath `
        -ResolvedOrganization $Organization `
        -ResolvedRepositoriesRoot $repositoriesRootPath `
        -ResolvedCloneRoot $CloneRoot `
        -ResolvedLogPath $LogPath `
        -Name $TaskName

    if ($taskRegistered) {
        Write-Log "Scheduled task ensured: $TaskName"
    }

    Remove-LegacyLogonTask "Git Pull All Repositories"
    Remove-LegacyLogonTask "Install Developer Config"
}

# -- Step 1: clone missing organisation repositories -------------------------

if ($SkipClone) {
    Write-Log "Clone step skipped (-SkipClone)."
} else {
    $ghPath = Get-GhExecutablePath

    & $ghPath auth status *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "gh CLI is not authenticated. Run: gh auth login"
    }

    $repositoriesJson = & $ghPath repo list $Organization --limit 1000 --json name,isArchived
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list repositories for organization: $Organization"
    }

    $organizationRepositories = @(($repositoriesJson | ConvertFrom-Json) | Where-Object { -not $_.isArchived })
    Write-Log "Found $($organizationRepositories.Count) non-archived repositories in $Organization"

    New-Item -ItemType Directory -Path $CloneRoot -Force | Out-Null

    foreach ($repository in $organizationRepositories) {
        $targetPath = Join-Path -Path $CloneRoot -ChildPath $repository.name

        if (Test-Path -LiteralPath (Join-Path $targetPath ".git")) {
            continue
        }

        if (Test-Path -LiteralPath $targetPath) {
            Write-Log "WARNING: $targetPath exists but is not a git repository; skipping clone."
            continue
        }

        Write-Log "Cloning $Organization/$($repository.name) -> $targetPath"
        & git clone --no-tags "https://github.com/$Organization/$($repository.name).git" $targetPath
        if ($LASTEXITCODE -ne 0) {
            $failedClones.Add($repository.name)
            Write-Log "ERROR: clone failed for $($repository.name) (exit code $LASTEXITCODE)"
        }
    }
}

# -- Step 2: pull all repositories -------------------------------------------

Write-Log "Pulling repositories under: $repositoriesRootPath"
$pullFailed = $false
$updateArguments = @{
    RepositoriesRoot = $repositoriesRootPath
}
if (-not $SkipClone) {
    $updateArguments.ManagedCloneRoot = $CloneRoot
    $updateArguments.ManagedOrganization = $Organization
    $updateArguments.ManagedRepositoryNames = @($organizationRepositories | ForEach-Object { $_.name })
}
& (Join-Path $scriptsDirectory "Update-GitRepositories.ps1") @updateArguments
if ($LASTEXITCODE -ne 0) {
    $pullFailed = $true
    Write-Log "WARNING: one or more repositories failed to pull (see git-pull-all.log)."
}

# -- Step 3: install developer config ----------------------------------------

Write-Log "Installing developer config from: $repoRoot"
& (Join-Path $scriptsDirectory "Install-DeveloperConfig.ps1") -Repo $repoRoot

# -- Done ---------------------------------------------------------------------

Write-Log "Sync complete. Failed clones: $($failedClones.Count). Pull failures: $(if ($pullFailed) { "yes" } else { "no" })."

if ($failedClones.Count -gt 0) {
    foreach ($failedClone in $failedClones) {
        Write-Log "  failed clone: $failedClone"
    }
}

if (($failedClones.Count -gt 0) -or $pullFailed) {
    exit 1
}
