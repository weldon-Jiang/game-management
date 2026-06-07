#!/usr/bin/env pwsh
# ============================================
# 生产环境 (prod) 启动 / 打包部署脚本
# 用法：
#   ./start-prod.ps1                              # 全量打包部署 (profile=full，首次用)
#   ./start-prod.ps1 -Services backend            # 只重新打包部署 backend
#   ./start-prod.ps1 -Services backend,gateway    # 重新打包部署 backend + gateway
#   ./start-prod.ps1 -Services backend -NoBuild   # 只重启 backend，不重新构建
#   ./start-prod.ps1 -Profile app                 # 只起应用层(前端+后端+网关)
#   ./start-prod.ps1 -Profile core                # 仅核心服务(Redis+后端+网关)
# 兼容旧写法：
#   ./start-prod.ps1 full backend                 # 位置参数：profile + 单服务
# 提示：上线前请确认 .env.prod 中的密钥已替换为真实值。
# ============================================
param(
    [string]$Profile = 'full',
    [string[]]$Services = @(),
    [switch]$NoBuild,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Positional = @()
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$EnvFile = '.env.prod'
$Tag = 'prod'
$Color = 'Yellow'

# 上线前密钥确认：拦截 .env.prod 中未替换的占位符（CHANGE_ME），避免用默认密钥部署生产
$envPath = Join-Path $PSScriptRoot $EnvFile
if (-not (Test-Path $envPath)) {
    Write-Host "[prod] 找不到 $EnvFile，请先创建并填入真实密钥。" -ForegroundColor Red
    exit 1
}
$placeholders = Select-String -Path $envPath -Pattern 'CHANGE_ME' -SimpleMatch
if ($placeholders) {
    Write-Host "[prod] 检测到 $EnvFile 中仍存在未替换的占位符 CHANGE_ME：" -ForegroundColor Red
    $placeholders | ForEach-Object { Write-Host ("  L{0}: {1}" -f $_.LineNumber, $_.Line.Trim()) -ForegroundColor Red }
    Write-Host "[prod] 请先替换为真实值后再部署生产环境。" -ForegroundColor Red
    exit 1
}
$answer = Read-Host "[prod] 即将部署【生产环境】，确认 .env.prod 密钥已是真实值？输入 yes 继续"
if ($answer -ne 'yes') {
    Write-Host "[prod] 已取消部署。" -ForegroundColor Yellow
    exit 0
}

# 兼容旧的位置参数写法：start-xxx.ps1 <profile> [service...]
if ($Positional.Count -ge 1 -and -not $PSBoundParameters.ContainsKey('Profile')) {
    $Profile = $Positional[0]
    if ($Positional.Count -ge 2 -and $Services.Count -eq 0) {
        $Services = $Positional[1..($Positional.Count - 1)]
    }
}

# 指定单/多服务时强制用 full profile，确保依赖服务名可解析
if ($Services.Count -gt 0 -and -not $PSBoundParameters.ContainsKey('Profile')) {
    $Profile = 'full'
}

$BuildFlag = if ($NoBuild) { @() } else { @('--build') }
$ServiceDesc = if ($Services.Count -gt 0) { ($Services -join ', ') } else { '全部' }
$BuildDesc = if ($NoBuild) { '不构建' } else { '构建' }

Write-Host "[$Tag] env-file=$EnvFile, profile=$Profile, 服务=$ServiceDesc, $BuildDesc 启动中..." -ForegroundColor $Color
docker compose --env-file $EnvFile -f docker-compose.yml --profile $Profile up -d @BuildFlag @Services
docker compose --env-file $EnvFile -f docker-compose.yml ps
