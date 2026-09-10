$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$icon = Join-Path $PSScriptRoot 'workbench.ico'
if (-not (Test-Path $icon)) { & (Join-Path $PSScriptRoot 'make-icon.ps1') | Out-Null }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework C# compiler not found' }
$targetName = ([char]0x6587) + ([char]0x732e) + ([char]0x7efc) + ([char]0x8ff0) + ([char]0x5de5) + ([char]0x4f5c) + ([char]0x53f0) + '.exe'
$target = Join-Path $root $targetName
$temporary = Join-Path $root 'workbench-tray.build.exe'
$backup = "$target.bak"
& $compiler /nologo /target:winexe /platform:anycpu /win32icon:$icon /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/out:$temporary" (Join-Path $PSScriptRoot 'WorkbenchTray.cs')
if ($LASTEXITCODE -ne 0) { throw 'Tray launcher build failed' }
if (-not (Test-Path -LiteralPath $temporary)) { throw 'Tray launcher output was not created' }
if (Test-Path -LiteralPath $target) { [System.IO.File]::Copy($target, $backup, $true) }
[System.IO.File]::Copy($temporary, $target, $true)
Write-Output "Built $target"
