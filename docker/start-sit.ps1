#!/usr/bin/env pwsh
# ============================================
# SIT 测试环境 (sit) 启动 / 打包部署脚本
# 用法：
#   ./start-sit.ps1                              # 全量打包部署 (profile=full，首次用)
#   ./start-sit.ps1 -Services backend            # 只重新打包部署 backend
#   ./start-sit.ps1 -Services backend,gateway    # 重新打包部署 backend + gateway
#   ./start-sit.ps1 -Services backend -NoBuild   # 只重启 backend，不重新构建
#   ./start-sit.ps1 -Profile app                 # 只起应用层(前端+后端+网关)
#   ./start-sit.ps1 -Profile core                # 仅核心服务(Redis+后端+网关)
# 兼容旧写法：
#   ./start-sit.ps1 full backend                 # 位置参数：profile + 单服务
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

$EnvFile = '.env.sit'
$Tag = 'sit'
$Color = 'Cyan'

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
