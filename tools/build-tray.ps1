$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$icon = Join-Path $PSScriptRoot 'workbench.ico'
if (-not (Test-Path $icon)) { & (Join-Path $PSScriptRoot 'make-icon.ps1') | Out-Null }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework C# compiler not found' }
& $compiler /nologo /target:winexe /platform:anycpu /win32icon:$icon /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/out:$root\文献综述工作台.exe" (Join-Path $PSScriptRoot 'WorkbenchTray.cs')
if ($LASTEXITCODE -ne 0) { throw 'Tray launcher build failed' }
