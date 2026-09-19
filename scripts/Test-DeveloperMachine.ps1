[CmdletBinding()]
param (
    [string]$Repo = (Split-Path $PSScriptRoot -Parent),
    [switch]$Offline,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$python = Get-Command python -ErrorAction SilentlyContinue
$arguments = @((Join-Path $PSScriptRoot "test-developer-machine.py"), "--repo", $Repo)
if ($Offline) { $arguments += "--offline" }
if ($Json) { $arguments += "--json" }
if ($python) {
    & $python.Source @arguments
} else {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) { throw "Install Python 3.11 or newer to run the machine checks." }
    & $launcher.Source -3 @arguments
}
exit $LASTEXITCODE
