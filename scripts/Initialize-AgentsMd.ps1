<#
.SYNOPSIS
    Creates Codex AGENTS.md files across local Git repositories.

.DESCRIPTION
    Recursively discovers Git working trees below -RepositoriesRoot and creates
    an AGENTS.md file in each repository. When a repository already has a
    CLAUDE.md file, the content is reused with the title and introductory line
    adapted for Codex and other AI coding agents.

    Existing AGENTS.md files are left unchanged unless -Overwrite is supplied.
    Repositories without CLAUDE.md are skipped by default; use
    -UseReadmeFallback to create a small generic AGENTS.md from README.md.

.PARAMETER RepositoriesRoot
    Root directory below which Git repositories are discovered.
    Defaults to:
      1. $env:REPOSITORIES_ROOT, when set
      2. C:\Local Files\Repositories, when it exists
      3. the current user's Documents\Repositories path

.PARAMETER Overwrite
    Replace existing AGENTS.md files.

.PARAMETER UseReadmeFallback
    For repositories without CLAUDE.md, create a minimal AGENTS.md using the
    README title and first non-heading paragraph when available.

.EXAMPLE
    .\Initialize-AgentsMd.ps1 -RepositoriesRoot "C:\Local Files\Repositories\Sky Haven"

.EXAMPLE
    .\Initialize-AgentsMd.ps1 -UseReadmeFallback -WhatIf
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param (
    [string]$RepositoriesRoot,
    [switch]$Overwrite,
    [switch]$UseReadmeFallback
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

    return Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Repositories"
}

function Get-GitRepositories {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    Get-ChildItem -LiteralPath $Root -Directory -Recurse -Force |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName ".git") -PathType Container } |
        Sort-Object -Property FullName
}

function Convert-ClaudeToAgentsContent {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $converted = $Content -replace "^# CLAUDE\.md", "# AGENTS.md"
    $converted = $converted -replace "This file provides guidance to Claude Code \(claude\.ai/code\) when working with code in this repository\.", "This file provides guidance to Codex CLI and other AI coding agents when working with code in this repository."
    return $converted.TrimEnd() + [Environment]::NewLine
}

function New-ReadmeFallbackContent {
    param (
        [Parameter(Mandatory = $true)]
        [string]$RepositoryPath
    )

    $repoName = Split-Path -Leaf $RepositoryPath
    $readmePath = Join-Path $RepositoryPath "README.md"
    $description = "Repository-specific context was not available when this file was generated. Inspect the repository structure and README before making changes."

    if (Test-Path -LiteralPath $readmePath -PathType Leaf) {
        $paragraph = Get-Content -LiteralPath $readmePath |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and $_ -notmatch "^#" } |
            Select-Object -First 1

        if (-not [string]::IsNullOrWhiteSpace($paragraph)) {
            $description = $paragraph.Trim()
        }
    }

    return @"
# AGENTS.md

This file provides guidance to Codex CLI and other AI coding agents when working with code in this repository.

## Repository Purpose

$description

## Working Guidelines

- Review the repository structure before making changes.
- Prefer small, focused edits that match existing conventions.
- Run the most specific available validation before handing work back.
- Do not expose secrets from local settings, environment files, or tfvars files.

## Repository

``$repoName``
"@
}

if ([string]::IsNullOrWhiteSpace($RepositoriesRoot)) {
    $RepositoriesRoot = Get-DefaultRepositoriesRoot
}

$resolvedRoot = (Resolve-Path -LiteralPath $RepositoriesRoot).Path
$repositories = Get-GitRepositories -Root $resolvedRoot

foreach ($repository in $repositories) {
    $agentsPath = Join-Path $repository.FullName "AGENTS.md"
    $claudePath = Join-Path $repository.FullName "CLAUDE.md"

    if ((Test-Path -LiteralPath $agentsPath -PathType Leaf) -and -not $Overwrite) {
        Write-Host "SKIP existing AGENTS.md: $($repository.FullName)"
        continue
    }

    if (Test-Path -LiteralPath $claudePath -PathType Leaf) {
        $content = Convert-ClaudeToAgentsContent -Content (Get-Content -LiteralPath $claudePath -Raw)
    } elseif ($UseReadmeFallback) {
        $content = New-ReadmeFallbackContent -RepositoryPath $repository.FullName
    } else {
        Write-Host "SKIP missing CLAUDE.md: $($repository.FullName)"
        continue
    }

    if ($PSCmdlet.ShouldProcess($agentsPath, "Create AGENTS.md")) {
        Set-Content -LiteralPath $agentsPath -Value $content -NoNewline -Encoding UTF8
        Write-Host "WROTE $agentsPath"
    }
}
