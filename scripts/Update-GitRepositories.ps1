<#
.SYNOPSIS
    Pulls all Git repositories under a configurable repositories root.

.DESCRIPTION
    Recursively discovers Git working trees below -RepositoriesRoot and runs
    "git pull --no-tags --ff-only" in each repository. Fast-forward-only pulls
    are used by default so an unattended scheduled task does not create merge
    commits or prompt for conflict resolution.

    Tags are deliberately kept out of local clones: before each pull the script
    deletes any existing local tags, pulls with --no-tags so the underlying
    fetch never brings tags back, and sets remote.origin.tagOpt to --no-tags so
    other automated fetches in the clone stay tag-free.

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
    Run "git pull --no-tags" instead of "git pull --no-tags --ff-only". This is
    not recommended for unattended scheduled runs because it may create merge
    commits or require conflict resolution. Tag deletion and --no-tags apply
    either way.

.PARAMETER MaxParallel
    Maximum number of repositories pulled concurrently. Defaults to 4. Use 1
    for sequential operation.

.PARAMETER ManagedCloneRoot
    Root containing repositories managed from an external inventory. Repositories
    directly beneath this root that are absent from -ManagedRepositoryNames are
    reported as orphaned and skipped.

.PARAMETER ManagedRepositoryNames
    Names of active repositories beneath -ManagedCloneRoot.

.PARAMETER ManagedOrganization
    Expected GitHub organisation for managed repositories. Existing repositories
    whose origin does not match this organisation and repository name are reported
    as path conflicts and skipped.

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
    [switch]$AllowMerge,
    [ValidateRange(1, 32)]
    [int]$MaxParallel = 4,
    [string]$ManagedCloneRoot,
    [string[]]$ManagedRepositoryNames,
    [string]$ManagedOrganization
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

function ConvertTo-GitHubRepositoryName {
    param (
        [Parameter(Mandatory = $true)]
        [string]$RemoteUrl
    )

    $normalized = $RemoteUrl.Trim().TrimEnd('/') -replace '\.git$', ''
    if ($normalized -match '^(?:https?://github\.com/|git@github\.com:|ssh://git@github\.com/)(?<name>[^/]+/[^/]+)$') {
        return $Matches.name.ToLowerInvariant()
    }

    return $null
}

function Write-RepositoryResult {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Level,

        [Parameter(Mandatory = $true)]
        [string]$Message,

        [Parameter(Mandatory = $true)]
        [string]$ResolvedLogPath
    )

    $colour = switch ($Level) {
        "ERROR" { "Red" }
        "WARNING" { "Yellow" }
        default { "Gray" }
    }
    Write-Host "  $Level`: $Message" -ForegroundColor $colour
    Add-Content -LiteralPath $ResolvedLogPath -Value "$Level`: $Message"
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
        [bool]$UsePlainGitPull,

        [Parameter(Mandatory = $true)]
        [int]$ResolvedMaxParallel
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
    $arguments += @("-MaxParallel", $ResolvedMaxParallel)

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

$managedCloneRootPath = $null
if (-not [string]::IsNullOrWhiteSpace($ManagedCloneRoot)) {
    $managedCloneRootPath = Resolve-Directory -Path $ManagedCloneRoot
    if ([string]::IsNullOrWhiteSpace($ManagedOrganization)) {
        throw "-ManagedOrganization is required when -ManagedCloneRoot is specified."
    }
}

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
        -UsePlainGitPull ([bool]$AllowMerge) `
        -ResolvedMaxParallel $MaxParallel

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

$statusPaths = @{
    Failed = New-Object System.Collections.Generic.List[string]
    Updated = New-Object System.Collections.Generic.List[string]
    Unchanged = New-Object System.Collections.Generic.List[string]
    MissingUpstream = New-Object System.Collections.Generic.List[string]
    RemoteUnavailable = New-Object System.Collections.Generic.List[string]
    PathConflict = New-Object System.Collections.Generic.List[string]
    Orphaned = New-Object System.Collections.Generic.List[string]
}
$pullArguments = @("pull", "--no-tags")
if (-not $AllowMerge) {
    $pullArguments += "--ff-only"
}

$pullRepository = {
    param($RepositoryPath, $ManagedRoot, $Organization, $ManagedNames, $GitPullArguments)

    $logLines = New-Object System.Collections.Generic.List[string]
    $result = [ordered]@{ Path = $RepositoryPath; Status = "Failed"; AlsoFailed = $false; Message = $null; LogLines = $logLines }
    if ($ManagedRoot -and (Split-Path -Path $RepositoryPath -Parent) -eq $ManagedRoot) {
        $repositoryName = Split-Path -Path $RepositoryPath -Leaf
        if ($ManagedNames -notcontains $repositoryName) {
            $result.Status = "Orphaned"
            $result.Message = "ORPHANED: $repositoryName is not an active repository in $Organization; skipped."
            return [pscustomobject]$result
        }
        $originUrl = (& git -C $RepositoryPath remote get-url origin 2>$null | Select-Object -First 1)
        $normalized = if ($originUrl) { $originUrl.Trim().TrimEnd('/') -replace '\.git$', '' } else { $null }
        $actual = if ($normalized -match '^(?:https?://github\.com/|git@github\.com:|ssh://git@github\.com/)(?<name>[^/]+/[^/]+)$') { $Matches.name.ToLowerInvariant() } else { $null }
        $expected = "$Organization/$repositoryName".ToLowerInvariant()
        if ($actual -ne $expected) {
            $display = if ($originUrl) { $originUrl } else { "origin is not configured" }
            $result.Status = "PathConflict"
            $result.Message = "PATH CONFLICT: expected $expected at $RepositoryPath, actual remote: $display; skipped."
            return [pscustomobject]$result
        }
    }

    $localTags = @(& git -C $RepositoryPath tag | Where-Object { $_ })
    if ($localTags.Count -gt 0) {
        & git -C $RepositoryPath tag -d @localTags | Out-Null
        if ($LASTEXITCODE -ne 0) { $result.AlsoFailed = $true; $logLines.Add("ERROR: git tag -d failed with exit code $LASTEXITCODE") }
        else { $logLines.Add("Deleted $($localTags.Count) local tag(s): $($localTags -join ', ')") }
    }
    & git -C $RepositoryPath config remote.origin.tagOpt --no-tags
    if ($LASTEXITCODE -ne 0) { $result.Message = "Unable to configure origin for $RepositoryPath."; return [pscustomobject]$result }

    $fetchOutput = @(& git -C $RepositoryPath fetch origin --prune --no-tags 2>&1)
    $fetchExitCode = $LASTEXITCODE
    foreach ($line in $fetchOutput) { $logLines.Add($line.ToString()) }
    if ($fetchExitCode -ne 0) {
        $result.Status = "RemoteUnavailable"; $result.AlsoFailed = $true
        $result.Message = "REMOTE UNAVAILABLE: fetch failed for $RepositoryPath with exit code $fetchExitCode."
        return [pscustomobject]$result
    }
    $upstream = (& git -C $RepositoryPath rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>$null | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace($upstream)) {
        $result.Status = "MissingUpstream"; $result.Message = "UPSTREAM MISSING: the current branch in $RepositoryPath has no upstream; skipped."
        return [pscustomobject]$result
    }
    & git -C $RepositoryPath rev-parse --verify --quiet "$upstream^{commit}" *> $null
    if ($LASTEXITCODE -ne 0) {
        $result.Status = "MissingUpstream"; $result.Message = "UPSTREAM MISSING: $upstream no longer exists for $RepositoryPath; skipped."
        return [pscustomobject]$result
    }
    $output = @(& git -C $RepositoryPath @GitPullArguments 2>&1)
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) { $logLines.Add($line.ToString()) }
    if ($exitCode -ne 0) { $result.Message = "git pull failed with exit code $exitCode" }
    elseif ($output -match 'Already up[ -]to[ -]date') { $result.Status = "Unchanged" }
    else { $result.Status = "Updated" }
    return [pscustomobject]$result
}

$pending = [System.Collections.Queue]::new()
foreach ($repository in $repositories) { $pending.Enqueue($repository.Path) }
$jobs = New-Object System.Collections.Generic.List[object]
$results = New-Object System.Collections.Generic.List[object]
while ($pending.Count -gt 0 -or $jobs.Count -gt 0) {
    while ($pending.Count -gt 0 -and $jobs.Count -lt $MaxParallel) {
        $path = $pending.Dequeue()
        Write-Host "Pulling $path"
        Add-Content -LiteralPath $LogPath -Value "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ssK")] Pulling $path"
        $jobs.Add((Start-Job -ScriptBlock $pullRepository -ArgumentList $path, $managedCloneRootPath, $ManagedOrganization, @($ManagedRepositoryNames), @($pullArguments)))
    }
    $completed = $jobs | Wait-Job -Any
    $jobResult = Receive-Job -Job $completed
    Remove-Job -Job $completed
    $jobs.Remove($completed)
    $results.Add($jobResult)
}

foreach ($result in $results | Sort-Object Path) {
    if ($result.LogLines) { Add-Content -LiteralPath $LogPath -Value @($result.LogLines) }
    $statusPaths[$result.Status].Add($result.Path)
    if ($result.AlsoFailed -and $result.Status -ne "Failed") { $statusPaths.Failed.Add($result.Path) }
    if ($result.Message) {
        $level = if ($result.Status -in @("MissingUpstream", "PathConflict", "Orphaned")) { "WARNING" } else { "ERROR" }
        Write-RepositoryResult -Level $level -Message $result.Message -ResolvedLogPath $LogPath
    }
}

$completedMessage = "Completed git pull run. Repositories: $($repositories.Count). Updated: $($statusPaths.Updated.Count). Unchanged: $($statusPaths.Unchanged.Count). Missing upstream: $($statusPaths.MissingUpstream.Count). Remote unavailable: $($statusPaths.RemoteUnavailable.Count). Path conflicts: $($statusPaths.PathConflict.Count). Orphaned: $($statusPaths.Orphaned.Count). Failed: $($statusPaths.Failed.Count)."
Write-Host $completedMessage
Add-Content -LiteralPath $LogPath -Value "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ssK")] $completedMessage"

if ($statusPaths.Failed.Count -gt 0) {
    Add-Content -LiteralPath $LogPath -Value "Failed repositories:"
    foreach ($failedRepository in $statusPaths.Failed) {
        Add-Content -LiteralPath $LogPath -Value "  $failedRepository"
    }

    exit 1
}
