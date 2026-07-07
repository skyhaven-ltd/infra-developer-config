<#
.SYNOPSIS
    Pulls all Git repositories under a configurable repositories root.

.DESCRIPTION
    Recursively discovers Git working trees below -RepositoriesRoot and runs
    "git pull --ff-only" in each repository. Fast-forward-only pulls are used by
    default so an unattended scheduled task does not create merge commits or
    prompt for conflict resolution.

    The script can also register a per-user scheduled task that runs at user
    logon. This does not require local administrator privileges.

    To restrict which repositories are pulled, create a machine-specific include
    list at scripts\git-repositories\<COMPUTERNAME>.txt in this repository. Each
    line is a path to include (directory or exact repo); lines beginning with #
    are treated as comments. The script discovers the file automatically by
    hostname. Use -ConfigPath to override the location explicitly.

.PARAMETER RepositoriesRoot
    Root directory below which Git repositories are discovered.
    Defaults to:
      1. $env:REPOSITORIES_ROOT, when set
      2. C:\Local Files\Repositories, when it exists
      3. the current user's Documents\Repositories path

.PARAMETER ConfigPath
    Path to a plain-text include list. Each non-blank, non-comment line is a
    directory or repository path to include. Repositories whose path does not
    start with any listed path are skipped. When omitted, the script looks for
    config\git-repositories\<COMPUTERNAME>.txt relative to the repository root;
    if that file is absent, all discovered repositories are pulled.

.PARAMETER InstallScheduledTask
    Register or update a per-user scheduled task that runs this script at user
    logon. The task stores the resolved -RepositoriesRoot path in its action.
    Config file discovery is hostname-based, so no extra argument is needed.

.PARAMETER TaskName
    Name of the scheduled task created by -InstallScheduledTask.

.PARAMETER LogPath
    Optional log file path. When omitted, a per-user log is written under:
    $env:LOCALAPPDATA\ops-developer-config\git-pull-all.log

.PARAMETER AllowMerge
    Run "git pull" instead of "git pull --ff-only". This is not recommended for
    unattended scheduled runs because it may create merge commits or require
    conflict resolution.

.EXAMPLE
    .\Update-GitRepositories.ps1

.EXAMPLE
    .\Update-GitRepositories.ps1 -RepositoriesRoot "D:\Repos"

.EXAMPLE
    .\Update-GitRepositories.ps1 -InstallScheduledTask -RepositoriesRoot "D:\Repos"

.EXAMPLE
    .\Update-GitRepositories.ps1 -ConfigPath "C:\config\my-repos.txt"
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param (
    [string]$RepositoriesRoot,
    [string]$ConfigPath,
    [switch]$InstallScheduledTask,
    [string]$TaskName = "Git Pull All Repositories",
    [string]$LogPath,
    [switch]$AllowMerge
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

function Resolve-Directory {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $resolved) {
        throw "Directory does not exist: $Path"
    }

    $item = Get-Item -LiteralPath $resolved.Path -ErrorAction Stop
    if (-not $item.PSIsContainer) {
        throw "Path is not a directory: $($item.FullName)"
    }

    return $item.FullName
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

function Get-IncludeList {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    $entries = Get-Content -LiteralPath $Path | ForEach-Object {
        $trimmed = $_.Trim()
        if (-not [string]::IsNullOrWhiteSpace($trimmed) -and -not $trimmed.StartsWith('#')) {
            $trimmed
        }
    }

    return @($entries | Where-Object { $_ })
}

function Get-GitRepositories {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [string[]]$IncludeList
    )

    $gitMarkers = Get-ChildItem -LiteralPath $Root -Force -Recurse -Filter ".git" -ErrorAction SilentlyContinue
    foreach ($gitMarker in $gitMarkers) {
        $repo = if ($gitMarker.PSIsContainer) { $gitMarker.Parent } else { $gitMarker.Directory }
        if (-not $repo) { continue }

        if ($IncludeList -and $IncludeList.Count -gt 0) {
            $included = $false
            foreach ($entry in $IncludeList) {
                if ($repo.FullName -eq $entry -or $repo.FullName.StartsWith($entry.TrimEnd('\') + '\')) {
                    $included = $true
                    break
                }
            }
            if (-not $included) { continue }
        }

        [pscustomobject]@{
            Path = $repo.FullName
        }
    }
}

function Register-UserLogonTask {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param (
        [Parameter(Mandatory = $true)]
        [string]$ResolvedRepositoriesRoot,

        [Parameter(Mandatory = $true)]
        [string]$ResolvedScriptPath,

        [Parameter(Mandatory = $true)]
        [string]$ResolvedLogPath,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [bool]$UsePlainGitPull
    )

    $powerShellPath = Get-PowerShellExecutablePath
    $arguments = @(
        "-NoProfile"
        "-ExecutionPolicy"
        "Bypass"
        "-File"
        (ConvertTo-TaskArgument -Value $ResolvedScriptPath)
        "-RepositoriesRoot"
        (ConvertTo-TaskArgument -Value $ResolvedRepositoriesRoot)
        "-LogPath"
        (ConvertTo-TaskArgument -Value $ResolvedLogPath)
    )

    if ($UsePlainGitPull) {
        $arguments += "-AllowMerge"
    }

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
            -Description "Runs git pull for repositories under $ResolvedRepositoriesRoot at user logon." `
            -Force | Out-Null

        return $true
    }

    return $false
}

if ([string]::IsNullOrWhiteSpace($RepositoriesRoot)) {
    $RepositoriesRoot = Get-DefaultRepositoriesRoot
}

$repositoriesRootPath = Resolve-Directory -Path $RepositoriesRoot
$scriptPath = (Resolve-Path -LiteralPath $PSCommandPath -ErrorAction Stop).Path

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $logDirectory = Join-Path -Path $env:LOCALAPPDATA -ChildPath "ops-developer-config"
    $LogPath = Join-Path -Path $logDirectory -ChildPath "git-pull-all.log"
}

$logDirectoryPath = Split-Path -Path $LogPath -Parent
if (-not [string]::IsNullOrWhiteSpace($logDirectoryPath)) {
    New-Item -ItemType Directory -Path $logDirectoryPath -Force | Out-Null
}

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $scriptsDirectory = Split-Path -Path $scriptPath -Parent
    $autoConfigPath = Join-Path -Path $scriptsDirectory -ChildPath "git-repositories\$env:COMPUTERNAME.txt"
    if (Test-Path -LiteralPath $autoConfigPath -PathType Leaf) {
        $ConfigPath = $autoConfigPath
    }
}

$includeList = $null
if (-not [string]::IsNullOrWhiteSpace($ConfigPath)) {
    $includeList = @(Get-IncludeList -Path $ConfigPath)
    if ($null -eq $includeList) {
        Write-Warning "Config file not found: $ConfigPath"
    } elseif ($includeList.Count -eq 0) {
        Write-Warning "Config file is empty, no repositories will be pulled: $ConfigPath"
    }
}

if ($InstallScheduledTask) {
    $taskRegistered = Register-UserLogonTask `
        -ResolvedRepositoriesRoot $repositoriesRootPath `
        -ResolvedScriptPath $scriptPath `
        -ResolvedLogPath $LogPath `
        -Name $TaskName `
        -UsePlainGitPull ([bool]$AllowMerge)

    if ($taskRegistered) {
        Write-Host "Scheduled task registered: $TaskName"
    } else {
        Write-Host "Scheduled task registration skipped: $TaskName"
    }
    Write-Host "Repositories root: $repositoriesRootPath"
    Write-Host "Log path: $LogPath"
    if (-not [string]::IsNullOrWhiteSpace($ConfigPath)) {
        Write-Host "Include list: $ConfigPath"
    } else {
        Write-Host "Include list: none (all repositories will be pulled)"
    }
    return
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ssK"
Add-Content -LiteralPath $LogPath -Value ""
Add-Content -LiteralPath $LogPath -Value "[$timestamp] Starting git pull run under: $repositoriesRootPath"

if ($includeList) {
    Add-Content -LiteralPath $LogPath -Value "[$timestamp] Include list: $ConfigPath ($($includeList.Count) entries)"
}

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    $message = "git executable was not found on PATH."
    Add-Content -LiteralPath $LogPath -Value "ERROR: $message"
    throw $message
}

$repositories = @(Get-GitRepositories -Root $repositoriesRootPath -IncludeList $includeList | Sort-Object -Property Path -Unique)
if ($repositories.Count -eq 0) {
    $message = "No Git repositories found under: $repositoriesRootPath"
    Write-Host $message -ForegroundColor Yellow
    Add-Content -LiteralPath $LogPath -Value $message
    return
}

$failed = New-Object System.Collections.Generic.List[string]
$pullArguments = @("pull")
if (-not $AllowMerge) {
    $pullArguments += "--ff-only"
}

foreach ($repository in $repositories) {
    Write-Host "Pulling $($repository.Path)"
    Add-Content -LiteralPath $LogPath -Value "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ssK")] Pulling $($repository.Path)"

    $output = & git -C $repository.Path @pullArguments
    $exitCode = $LASTEXITCODE

    if ($output) {
        Add-Content -LiteralPath $LogPath -Value ($output | ForEach-Object { $_.ToString() })
    }

    if ($exitCode -ne 0) {
        $failed.Add($repository.Path)
        Add-Content -LiteralPath $LogPath -Value "ERROR: git pull failed with exit code $exitCode"
        Write-Host "  failed with exit code $exitCode" -ForegroundColor Red
    }
}

$completedMessage = "Completed git pull run. Repositories: $($repositories.Count). Failed: $($failed.Count)."
Write-Host $completedMessage
Add-Content -LiteralPath $LogPath -Value "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ssK")] $completedMessage"

if ($failed.Count -gt 0) {
    Add-Content -LiteralPath $LogPath -Value "Failed repositories:"
    foreach ($failedRepository in $failed) {
        Add-Content -LiteralPath $LogPath -Value "  $failedRepository"
    }

    exit 1
}
