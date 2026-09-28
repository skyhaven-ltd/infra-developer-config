$ErrorActionPreference = "Stop"
$compiler = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$output = Join-Path $PSScriptRoot "dist\Evergreen.exe"
New-Item -ItemType Directory -Path (Split-Path -Parent $output) -Force | Out-Null
& $compiler /nologo /target:winexe /platform:anycpu /optimize+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/win32icon:$(Join-Path $PSScriptRoot 'Evergreen.ico')" "/out:$output" (Join-Path $PSScriptRoot "Evergreen.cs")
if ($LASTEXITCODE -ne 0) { throw "Evergreen build failed." }
Write-Host "Executable: $output"
