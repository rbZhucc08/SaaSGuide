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
    & $pythonPath -m unittest test_validator.py test_deepseek_ask_build.py test_risk_assistant.py test_server.py
    if ($LASTEXITCODE -ne 0) { throw "Python 自动测试失败。" }

    & $pythonPath .\validate_data.py
    if ($LASTEXITCODE -ne 0) { throw "JSON 与页面校验失败。" }

    node --check app.js
    if ($LASTEXITCODE -ne 0) { throw "app.js 语法检查失败。" }

    node --check builder.js
    if ($LASTEXITCODE -ne 0) { throw "builder.js 语法检查失败。" }

    Write-Host "全部检查通过：38 项自动测试、数据校验和 JavaScript 语法检查。" -ForegroundColor Green
}
finally {
    Pop-Location
}
