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
    & $pythonPath -m unittest test_validator.py test_deepseek_ask_build.py test_risk_assistant.py test_server.py test_xlsx_import.py test_risk_rules.py test_text_evidence.py test_knowledge_base.py test_sqlite_store.py test_reporting.py test_multimodal_adapters.py test_ai_orchestrator.py test_company_data.py test_release.py
    if ($LASTEXITCODE -ne 0) { throw "Python 自动测试失败。" }

    & $pythonPath .\validate_data.py
    if ($LASTEXITCODE -ne 0) { throw "JSON 与页面校验失败。" }

    node --check app.js
    if ($LASTEXITCODE -ne 0) { throw "app.js 语法检查失败。" }

    node --check shell.js
    if ($LASTEXITCODE -ne 0) { throw "shell.js 语法检查失败。" }

    node --check builder.js
    if ($LASTEXITCODE -ne 0) { throw "builder.js 语法检查失败。" }

    node --check data-sources.js
    if ($LASTEXITCODE -ne 0) { throw "data-sources.js 语法检查失败。" }

    node --check risk-radar.js
    if ($LASTEXITCODE -ne 0) { throw "risk-radar.js 语法检查失败。" }

    node --check evidence-intake.js
    if ($LASTEXITCODE -ne 0) { throw "evidence-intake.js 语法检查失败。" }

    node --check knowledge-base.js
    if ($LASTEXITCODE -ne 0) { throw "knowledge-base.js 语法检查失败。" }

    node --check action-tracker.js
    if ($LASTEXITCODE -ne 0) { throw "action-tracker.js 语法检查失败。" }

    node --check reports.js
    if ($LASTEXITCODE -ne 0) { throw "reports.js 语法检查失败。" }

    node --check input-lab.js
    if ($LASTEXITCODE -ne 0) { throw "input-lab.js 语法检查失败。" }

    Write-Host "全部检查通过：V1 回归、V2-P1 至 P8、AI 编排、数据校验和 JavaScript 语法检查。" -ForegroundColor Green
}
finally {
    Pop-Location
}
