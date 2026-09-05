$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "未找到 .venv，请先按 README 安装依赖。" }
Push-Location $root
try {
    & $python -c "import flask, openpyxl, docx, pypdf"
    if ($LASTEXITCODE -ne 0) { throw "项目依赖不完整，请运行 .venv\Scripts\python.exe -m pip install -r requirements.txt" }
    if (-not $env:SAASGUIDE_PORT) { $env:SAASGUIDE_PORT = "4173" }
    Write-Host "SaaSGuide V2 本地工作台：http://127.0.0.1:$env:SAASGUIDE_PORT/" -ForegroundColor Cyan
    & $python server.py
}
finally { Pop-Location }
