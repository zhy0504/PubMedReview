$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$systemPython = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not (Test-Path -LiteralPath $python)) {
  if (-not $systemPython) { Write-Error 'Python 3.10 or newer is required.'; exit 1 }
  Write-Host 'Creating project virtual environment...' -ForegroundColor Cyan
  & $systemPython -m venv (Join-Path $PSScriptRoot '.venv')
  if ($LASTEXITCODE -ne 0) { throw 'Failed to create project virtual environment.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'requirements.txt'))) { throw 'requirements.txt is missing.' }
Write-Host 'Checking and repairing project environment...' -ForegroundColor Cyan
& $python (Join-Path $PSScriptRoot 'tools/environment_manager.py') --ensure
if ($LASTEXITCODE -ne 0) { throw 'Environment is not ready. See the diagnostic log above.' }
Write-Host 'Starting local Web workbench: http://127.0.0.1:8765' -ForegroundColor Cyan
$webScript = Join-Path $PSScriptRoot 'src\web.py'
$webArguments = @($webScript) + @($args)
$env:WORKBENCH_LAUNCHER_PID = $PID
if ($env:WORKBENCH_TRAY -ne '1') { Start-Process 'http://127.0.0.1:8765' }
& $python -u $webScript @args
exit $LASTEXITCODE

