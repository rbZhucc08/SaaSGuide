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
    # 原生命令写到 stderr 的进度输出（unittest 的进度点）在 "Stop" 偏好下会被当成
    # 终止性错误。因此调用期间临时放宽偏好，改用退出码作为唯一判据，调用后恢复。
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $pythonPath .\scripts\run_checks.py 2>&1 | Out-Host
        $checkExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($checkExitCode -ne 0) { throw "项目检查失败。" }
    Write-Host "全部检查通过：自动测试、数据、Markdown、JavaScript 和 Git 差异。" -ForegroundColor Green
}
finally {
    Pop-Location
}
