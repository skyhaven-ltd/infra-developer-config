[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\artifacts\cloud-context"),
    [ValidateSet("win-x64", "win-arm64")]
    [string]$Runtime = "win-x64"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$projectPath = Join-Path $repositoryRoot "tools\cloud-context\gui\src\CloudContext.App\CloudContext.App.csproj"
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cloud-context-publish"
$stagingDirectory = Join-Path $temporaryRoot ([guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null

try {
    dotnet publish $projectPath `
        --configuration Release `
        --runtime $Runtime `
        --self-contained true `
        --output $stagingDirectory `
        -p:PublishSingleFile=true `
        -p:IncludeNativeLibrariesForSelfExtract=true `
        -p:DebugType=None `
        -p:DebugSymbols=false
    if ($LASTEXITCODE -ne 0) {
        throw "Cloud Context publish failed with exit code $LASTEXITCODE."
    }

    Copy-Item `
        -LiteralPath (Join-Path $repositoryRoot "tools\cloud-context\gui\PORTABLE-README.md") `
        -Destination (Join-Path $stagingDirectory "README.md")

    $archivePath = Join-Path $resolvedOutput "cloud-context-$Runtime.zip"
    Compress-Archive -Path (Join-Path $stagingDirectory "*") -DestinationPath $archivePath -Force
    Write-Output "Published portable Cloud Context application: $archivePath"
} finally {
    $resolvedStaging = [System.IO.Path]::GetFullPath($stagingDirectory)
    $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot).TrimEnd("\") + "\"
    if ($resolvedStaging.StartsWith($resolvedTemporaryRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $resolvedStaging -PathType Container)) {
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
    }
}
