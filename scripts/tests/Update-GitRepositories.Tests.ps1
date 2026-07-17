$scriptPath = (Resolve-Path (Join-Path $PSScriptRoot "..\Update-GitRepositories.ps1")).Path

function Invoke-Git {
    param (
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & git @Arguments | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Describe "Update-GitRepositories repository-state handling" {
    It "classifies conflicts, orphans, missing upstreams, and unavailable remotes" {
        $root = Join-Path $TestDrive "repositories"
        $managedRoot = Join-Path $root "Sky Haven"
        $remoteRoot = Join-Path $TestDrive "remotes"
        New-Item -ItemType Directory -Path $managedRoot, $remoteRoot -Force | Out-Null

        $seed = Join-Path $TestDrive "seed"
        Invoke-Git @("init", "--initial-branch=main", $seed)
        Invoke-Git @("-C", $seed, "config", "user.email", "test@example.invalid")
        Invoke-Git @("-C", $seed, "config", "user.name", "Test User")
        Set-Content -LiteralPath (Join-Path $seed "README.md") -Value "fixture"
        Invoke-Git @("-C", $seed, "add", "README.md")
        Invoke-Git @("-C", $seed, "commit", "-m", "fixture")

        $deletedBranchRemote = Join-Path $remoteRoot "deleted-branch.git"
        Invoke-Git @("init", "--bare", $deletedBranchRemote)
        Invoke-Git @("-C", $seed, "remote", "add", "fixture", $deletedBranchRemote)
        Invoke-Git @("-C", $seed, "push", "fixture", "main")

        $deletedBranchRepo = Join-Path $root "deleted-branch"
        Invoke-Git @("clone", $deletedBranchRemote, $deletedBranchRepo)
        Invoke-Git @("-C", $deletedBranchRepo, "checkout", "-b", "removed")
        Invoke-Git @("-C", $deletedBranchRepo, "config", "branch.removed.remote", "origin")
        Invoke-Git @("-C", $deletedBranchRepo, "config", "branch.removed.merge", "refs/heads/removed")

        $unavailableRepo = Join-Path $root "unavailable"
        Invoke-Git @("clone", $deletedBranchRemote, $unavailableRepo)
        Invoke-Git @("-C", $unavailableRepo, "remote", "set-url", "origin", (Join-Path $remoteRoot "absent.git"))

        $conflictRepo = Join-Path $managedRoot ".github"
        Invoke-Git @("clone", $deletedBranchRemote, $conflictRepo)
        Invoke-Git @("-C", $conflictRepo, "remote", "set-url", "origin", "https://github.com/personal/.github.git")

        $orphanRepo = Join-Path $managedRoot "retired"
        Invoke-Git @("clone", $deletedBranchRemote, $orphanRepo)

        $logPath = Join-Path $TestDrive "update.log"
        $outputPath = Join-Path $TestDrive "output.txt"
        $command = @(
            "-NoProfile"
            "-File", $scriptPath
            "-RepositoriesRoot", $root
            "-ConfigPath", (Join-Path $TestDrive "no-include-list.txt")
            "-ManagedCloneRoot", $managedRoot
            "-ManagedOrganization", "skyhaven-ltd"
            "-ManagedRepositoryNames", ".github"
            "-LogPath", $logPath
        )
        $powerShellPath = (Get-Process -Id $PID).Path
        & $powerShellPath @command *> $outputPath
        $exitCode = $LASTEXITCODE
        $output = Get-Content -LiteralPath $outputPath -Raw

        $output | Should Match "PATH CONFLICT:"
        $output | Should Match "ORPHANED:"
        $output | Should Match "UPSTREAM MISSING:"
        $output | Should Match "REMOTE UNAVAILABLE:"
        $output | Should Match "Missing upstream: 1"
        $output | Should Match "Remote unavailable: 1"
        $output | Should Match "Path conflicts: 1"
        $output | Should Match "Orphaned: 1"
        $output | Should Match "Failed: 1"
        $exitCode | Should Be 1
    }
}
