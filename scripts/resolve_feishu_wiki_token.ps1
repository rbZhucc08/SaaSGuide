# 把知识库（wiki）链接里的节点 token 解析成真正的多维表格 app_token。
# 用法：& '.\scripts\resolve_feishu_wiki_token.ps1' -WikiToken <wiki节点token>
#
# 说明：本脚本不使用反引号续行，避免 PowerShell 5.1 在编码异常时破坏解析。
# 文件必须以 UTF-8 BOM 保存，否则 5.1 会把中文按 ANSI 读取并报 UnexpectedToken。

param(
    [Parameter(Mandatory = $true)][string]$WikiToken
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$envFile = Join-Path $projectRoot ".env.local"
if (-not (Test-Path -LiteralPath $envFile)) { throw "未找到 .env.local，请先复制 .env.example 为 .env.local 并填写应用凭据。" }

foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
    $index = $trimmed.IndexOf("=")
    if ($index -lt 1) { continue }
    $name = $trimmed.Substring(0, $index).Trim()
    $value = $trimmed.Substring($index + 1).Trim().Trim('"').Trim("'")
    if ($value) { [System.Environment]::SetEnvironmentVariable($name, $value, "Process") }
}

$appId = $env:FEISHU_APP_ID
$appSecret = $env:FEISHU_APP_SECRET
if (-not $appId -or -not $appSecret) { throw "缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET。" }
Write-Host "使用已配置应用凭据（值不显示）" -ForegroundColor DarkGray

$tokenUri = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
$tokenBody = @{ app_id = $appId; app_secret = $appSecret } | ConvertTo-Json -Compress
$tokenParams = @{
    Uri         = $tokenUri
    Method      = "Post"
    ContentType = "application/json; charset=utf-8"
    Body        = $tokenBody
}

try {
    $tokenResponse = Invoke-RestMethod @tokenParams
} catch {
    Write-Host "调用飞书鉴权接口失败：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "常见原因：App Secret 复制有误、含空格，或应用尚未发布。" -ForegroundColor Yellow
    exit 1
}

if ($tokenResponse.code -ne 0) {
    Write-Host "获取 tenant_access_token 失败：code=$($tokenResponse.code) msg=$($tokenResponse.msg)" -ForegroundColor Red
    if ($tokenResponse.code -eq 10003) {
        Write-Host "10003 通常表示 App ID 或 App Secret 不正确。" -ForegroundColor Yellow
    }
    exit 1
}
Write-Host "鉴权成功（tenant_access_token 已获取，不显示其值）" -ForegroundColor Green

$headers = @{ Authorization = "Bearer $($tokenResponse.tenant_access_token)" }
$nodeUri = "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token=$WikiToken&obj_type=wiki"
Write-Host "查询知识库节点（节点 token 不显示）" -ForegroundColor DarkGray

try {
    $node = Invoke-RestMethod -Uri $nodeUri -Headers $headers -Method Get
} catch {
    Write-Host "查询节点失败：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "请改用多维表格「···」→「更多」→「在浏览器中打开」，取 /base/ 直链。" -ForegroundColor Yellow
    exit 1
}

if ($node.code -ne 0) {
    Write-Host "查询节点返回错误：code=$($node.code) msg=$($node.msg)" -ForegroundColor Red
    if ($node.code -eq 131006) {
        Write-Host "131006 通常表示应用没有被添加为该文档的协作者。" -ForegroundColor Yellow
    }
    exit 1
}

$objToken = $node.data.node.obj_token
$objType = $node.data.node.obj_type
Write-Host ""
Write-Host "节点标题 : $($node.data.node.title)"
Write-Host "对象类型 : $objType"
Write-Host "obj_token: 已解析（值不显示）" -ForegroundColor Green
Write-Host ""
if ($objType -eq "bitable") {
    Write-Host "已解析到多维表格 app_token。为避免终端日志泄露，本脚本不显示该值。" -ForegroundColor Cyan
    Write-Host "如需配置，请在本机临时调试时读取 `$objToken，且不要复制到聊天、截图或提交。"
} else {
    Write-Host "注意：该节点类型不是 bitable（多维表格），请确认链接指向的是多维表格。" -ForegroundColor Yellow
}
