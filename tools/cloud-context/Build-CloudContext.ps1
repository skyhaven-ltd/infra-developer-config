param(
    [ValidateSet("win-x64", "win-arm64")][string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"
$project = Join-Path $PSScriptRoot "gui\CloudContext.csproj"
$output = Join-Path $PSScriptRoot "dist\$Runtime"
dotnet publish $project -c Release -r $Runtime --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=None -p:DebugSymbols=false -o $output
if ($LASTEXITCODE -ne 0) { throw "Cloud Context publish failed." }
Write-Host "Executable: $(Join-Path $output 'CloudContext.exe')"
