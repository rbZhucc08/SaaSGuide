$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = "utf-8"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "未找到项目虚拟环境，请先按照 README 安装依赖。"
}

Push-Location $projectRoot
try {
    & $pythonPath .\scripts\run_checks.py
    if ($LASTEXITCODE -ne 0) { throw "项目检查失败。" }
}
finally {
    Pop-Location
}
