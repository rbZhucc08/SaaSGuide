# 从 .env.local 读取本机凭据后启动 SaaSGuide。
# 凭据只存在于本机文件与当前进程环境中，不写入源码、不进入 Git、不打印到日志。

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = "utf-8"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envFile = Join-Path $projectRoot ".env.local"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "未找到项目虚拟环境，请先按照 README 安装依赖。"
}

if (Test-Path -LiteralPath $envFile) {
    $loaded = 0
    foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $index = $trimmed.IndexOf("=")
        if ($index -lt 1) { continue }
        $name = $trimmed.Substring(0, $index).Trim()
        $value = $trimmed.Substring($index + 1).Trim().Trim('"').Trim("'")
        if ($value) {
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
            $loaded++
        }
    }
    Write-Host "已从 .env.local 载入 $loaded 项凭据（不显示具体值）" -ForegroundColor DarkGray
    foreach ($required in @("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_BITABLE_APP_TOKEN", "FEISHU_BITABLE_TABLE_ID")) {
        if (-not [System.Environment]::GetEnvironmentVariable($required, "Process")) {
            Write-Host "缺少 $required —— 飞书连接器会保持未授权状态" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "未找到 .env.local，以未授权状态启动（规则扫描与人工处理仍可用）" -ForegroundColor Yellow
}

if (-not $env:SAASGUIDE_PORT) { $env:SAASGUIDE_PORT = "4173" }

Push-Location $projectRoot
try {
    Write-Host "SaaSGuide 本地工作台：http://127.0.0.1:$env:SAASGUIDE_PORT/" -ForegroundColor Cyan
    & $pythonPath server.py
}
finally {
    Pop-Location
}
