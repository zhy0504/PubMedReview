$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$systemPython = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not (Test-Path -LiteralPath $python)) {
  if (-not $systemPython) { Write-Error '未找到 Python，请先安装 Python 3.10 或更高版本。'; exit 1 }
  Write-Host 'Creating project virtual environment...' -ForegroundColor Cyan
  & $systemPython -m venv (Join-Path $PSScriptRoot '.venv')
  if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'requirements.txt'))) { throw '未找到 requirements.txt' }
Write-Host 'Checking project dependencies...' -ForegroundColor Cyan
& $python (Join-Path $PSScriptRoot 'tools/check_dependencies.py')
if ($LASTEXITCODE -eq 0) {
  Write-Host 'Dependencies already installed; skipping download.' -ForegroundColor Green
} else {
  Write-Host 'Installing missing or incompatible dependencies...' -ForegroundColor Yellow
$indexes = @(& $python (Join-Path $PSScriptRoot 'tools/select_package_indexes.py'))
if (-not $indexes.Count) { $indexes = @('https://pypi.org/simple') }
$installed = $false
foreach ($index in $indexes) {
  Write-Host "Installing from $index (ranked by response time)..."
  & $python -m pip --isolated install -r (Join-Path $PSScriptRoot 'requirements.txt') --index-url $index --timeout 30 --retries 1
  if ($LASTEXITCODE -eq 0) { $installed = $true; break }
}
if (-not $installed) { throw '依赖安装失败，请检查网络连接' }
}
Write-Host 'Starting local Web workbench: http://127.0.0.1:8765' -ForegroundColor Cyan
$webScript = Join-Path $PSScriptRoot 'src\web.py'
$webArguments = @($webScript) + @($args)
$env:WORKBENCH_LAUNCHER_PID = $PID
if ($env:WORKBENCH_TRAY -ne '1') { Start-Process 'http://127.0.0.1:8765' }
& $python -u $webScript @args
exit $LASTEXITCODE

