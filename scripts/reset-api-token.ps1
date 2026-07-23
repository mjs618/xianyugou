<#
.SYNOPSIS
    重置后端 API Token（删除旧 token 文件 + 重启后端 + 读取新 token）。

.DESCRIPTION
    后端 API Token 通过 @lru_cache 缓存在进程内存中，仅删除文件无法生效，
    必须重启后端容器才能让 lru_cache 失效并触发重新生成。

    本脚本执行以下步骤：
    1. 检查后端容器是否运行
    2. 备份旧 token + 删除容器内 token 文件
    3. 重启后端容器（清除 lru_cache）
    4. 等待健康检查通过（最多 90 秒）
    5. 读取并验证新 token

.PARAMETER ComposeFile
    docker-compose.yml 路径，默认为脚本所在目录的上级 docker-compose.yml。

.EXAMPLE
    .\reset-api-token.ps1
    .\reset-api-token.ps1 -ComposeFile D:\myapp\docker-compose.yml

.NOTES
    - 不会丢失任何业务数据（token 文件独立于数据库）
    - 重置后前端 localStorage 中的旧 token 会失效，需在 Settings 页面手动更新
    - Volume 持久化：docker compose restart 不会删除 /app/data volume
#>
[CmdletBinding()]
param(
    [string]$ComposeFile = (Resolve-Path (Join-Path $PSScriptRoot ".." "docker-compose.yml")).Path
)

$ErrorActionPreference = "Stop"

function Write-Step([int]$step, [int]$total, [string]$msg) {
    Write-Host "`n[$step/$total] $msg" -ForegroundColor Cyan
}
function Write-Ok([string]$msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)  { Write-Host "    [X]  $msg" -ForegroundColor Red }

$TOTAL_STEPS = 5

# ---------- 0. 前置检查 ----------

if (-not (Test-Path $ComposeFile)) {
    Write-Err "docker-compose.yml 未找到：$ComposeFile"
    exit 1
}

$projectDir = Split-Path -Parent $ComposeFile
Write-Host "项目目录: $projectDir" -ForegroundColor DarkGray
Write-Host "Compose:  $ComposeFile" -ForegroundColor DarkGray

# ---------- 1. 检查后端容器是否运行 ----------

Write-Step 1 $TOTAL_STEPS "检查后端容器状态..."
$psOutput = docker compose -f $ComposeFile ps backend 2>&1 | Out-String
if ($psOutput -notmatch "backend.*Up") {
    Write-Err "后端容器未运行，请先执行：docker compose -f `"$ComposeFile`" up -d backend"
    Write-Host $psOutput -ForegroundColor DarkGray
    exit 1
}
Write-Ok "后端容器运行中"

# ---------- 2. 备份旧 token + 删除 token 文件 ----------

Write-Step 2 $TOTAL_STEPS "备份旧 token 并删除..."
$oldToken = $null
try {
    $oldToken = (docker compose -f $ComposeFile exec -T backend cat /app/data/api.token 2>$null | Out-String).Trim()
} catch {
    # 旧 token 文件不存在（首次启动场景）
}

if ($oldToken) {
    $backupPath = Join-Path $PSScriptRoot "api.token.bak"
    $oldToken | Out-File -FilePath $backupPath -Encoding utf8 -NoNewline
    Write-Ok "旧 token 已备份到：$backupPath"
    Write-Host "    旧 token: $($oldToken.Substring(0,8))...（已脱敏）" -ForegroundColor DarkGray
} else {
    Write-Warn "未找到旧 token 文件（可能是首次重置）"
}

# 删除容器内 token 文件
docker compose -f $ComposeFile exec -T backend rm -f /app/data/api.token 2>$null | Out-Null
Write-Ok "已删除容器内 /app/data/api.token"

# ---------- 3. 重启后端容器 ----------

Write-Step 3 $TOTAL_STEPS "重启后端容器（清除 lru_cache）..."
docker compose -f $ComposeFile restart backend 2>&1 | Out-Null
Write-Ok "后端容器已重启"

# ---------- 4. 等待健康检查通过 ----------

Write-Step 4 $TOTAL_STEPS "等待健康检查通过（最多 90 秒）..."
$maxWait = 90
$elapsed = 0
$healthy = $false
while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 5
    $elapsed += 5
    $statusOutput = docker compose -f $ComposeFile ps backend 2>&1 | Out-String
    if ($statusOutput -match "backend.*Up.*\(healthy\)") {
        $healthy = $true
        break
    }
    Write-Host "." -NoNewline -ForegroundColor DarkGray
}
Write-Host ""

if (-not $healthy) {
    Write-Err "后端容器在 ${maxWait}s 内未通过健康检查"
    Write-Warn "可能原因：数据库迁移耗时过长 / 启动失败"
    Write-Warn "请查看日志：docker compose -f `"$ComposeFile`" logs backend --tail 50"
    exit 1
}
Write-Ok "后端健康检查通过（耗时 ${elapsed}s）"

# ---------- 5. 读取并验证新 token ----------

Write-Step 5 $TOTAL_STEPS "读取并验证新 token..."
$newToken = (docker compose -f $ComposeFile exec -T backend cat /app/data/api.token 2>$null | Out-String).Trim()

if (-not $newToken) {
    Write-Err "新 token 读取失败"
    exit 1
}

# 获取端口映射
$portOutput = (docker compose -f $ComposeFile port backend 8000 2>$null | Out-String).Trim()
if ($portOutput) {
    $port = $portOutput
} else {
    # 回退到 docker-compose.yml 中配置的默认端口
    $port = "127.0.0.1:18001"
}

# 用新 token 验证 /api/health
try {
    $headers = @{ "X-API-Token" = $newToken }
    $response = Invoke-WebRequest -Uri "http://$port/api/health" -Headers $headers -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Ok "新 token 验证通过（/api/health 返回 200）"
    } else {
        Write-Warn "/api/health 返回非 200：$($response.StatusCode)"
    }
} catch {
    Write-Warn "验证请求失败：$($_.Exception.Message)"
    Write-Warn "请手动验证：curl -H `"X-API-Token: $newToken`" http://$port/api/health"
}

# ---------- 输出结果 ----------

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " API Token 重置成功" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "新 Token: " -NoNewline -ForegroundColor White
Write-Host $newToken -ForegroundColor Yellow
Write-Host ""
Write-Host "[后续操作]" -ForegroundColor Cyan
Write-Host "  1. 打开前端应用 → Settings（设置）页面"
Write-Host "  2. 在 API Token 输入框中粘贴上面的新 token"
Write-Host "  3. 保存"
Write-Host ""
Write-Host "[旧 token 备份]" -ForegroundColor Cyan
if ($oldToken) {
    Write-Host "  路径: $(Join-Path $PSScriptRoot 'api.token.bak')"
    Write-Host "  如需回滚，将该文件内容写回容器 /app/data/api.token 后重启"
} else {
    Write-Host "  无（首次重置，无旧 token）"
}
Write-Host ""
Write-Host "[快速测试命令]" -ForegroundColor Cyan
Write-Host "  curl -H `"X-API-Token: $newToken`" http://$port/api/health"
Write-Host ""
