# 探测飞书多维表格 app_token：逐个候选调用真实 Bitable 接口，打印可读结论。
# 用法：& '.\scripts\probe_feishu_bitable.ps1' -Candidates tok1,tok2,tok3
#
# 只读取 .env.local 中的 App ID / Secret / Table ID；不会打印或写入任何凭据值。

param(
    [Parameter(Mandatory = $true)][string[]]$Candidates
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$envFile = Join-Path $projectRoot ".env.local"
if (-not (Test-Path -LiteralPath $envFile)) { throw "未找到 .env.local。" }

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
$tableId = $env:FEISHU_BITABLE_TABLE_ID
if (-not $appId -or -not $appSecret) { throw "缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET。" }
if (-not $tableId) { throw "缺少 FEISHU_BITABLE_TABLE_ID。" }

$tokenParams = @{
    Uri         = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    Method      = "Post"
    ContentType = "application/json; charset=utf-8"
    Body        = (@{ app_id = $appId; app_secret = $appSecret } | ConvertTo-Json -Compress)
}
$tokenResponse = Invoke-RestMethod @tokenParams
if ($tokenResponse.code -ne 0) { throw "鉴权失败：code=$($tokenResponse.code) msg=$($tokenResponse.msg)" }
$headers = @{ Authorization = "Bearer $($tokenResponse.tenant_access_token)" }
Write-Host "鉴权成功。开始逐个探测候选 app_token（资源标识符不显示）。" -ForegroundColor Green
Write-Host ""

foreach ($candidate in $Candidates) {
    $candidate = $candidate.Trim()
    if (-not $candidate) { continue }
    $uri = "https://open.feishu.cn/open-apis/bitable/v1/apps/$candidate/tables/$tableId/records/search?page_size=1"
    Write-Host "---- 探测一个候选（值不显示）" -ForegroundColor Cyan
    $params = @{
        Uri         = $uri
        Method      = "Post"
        Headers     = $headers
        ContentType = "application/json; charset=utf-8"
        Body        = '{"automatic_fields":true}'
    }
    try {
        $result = Invoke-RestMethod @params
        if ($result.code -eq 0) {
            $count = 0
            if ($result.data -and $result.data.items) { $count = $result.data.items.Count }
            Write-Host "   ✅ 成功！本页返回 $count 条记录。这个 token 是对的。" -ForegroundColor Green
            Write-Host "   token 值不显示；请从本次传入的对应候选写入本机 .env.local。"
        } else {
            Write-Host "   ❌ code=$($result.code) msg=$($result.msg)" -ForegroundColor Red
        }
    } catch {
        $status = "?"
        $body = ""
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
            try { $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); $body = $sr.ReadToEnd() } catch {}
        }
        Write-Host "   ❌ HTTP=$status $($_.Exception.Message)" -ForegroundColor Red
        if ($body) { Write-Host "      飞书返回了错误正文（为避免泄露资源信息，不显示）。" -ForegroundColor DarkGray }
    }
    Write-Host ""
}
