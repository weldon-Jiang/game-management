#!/usr/bin/env pwsh
# ============================================
# 生产环境 (prod) 停服 / 清理脚本
# 用法：
#   ./stop-prod.ps1                  # 停止并移除容器（保留数据卷）
#   ./stop-prod.ps1 -RemoveVolumes   # 停止并移除容器 + 数据卷（清空 MySQL/Redis 数据，危险！）
#   ./stop-prod.ps1 -RemoveImages    # 同时移除本项目构建的镜像
# 提示：生产环境停服为高危操作，脚本会要求二次确认。
# ============================================
param(
    [switch]$RemoveVolumes,
    [switch]$RemoveImages
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$EnvFile = '.env.prod'
$Tag = 'prod'

# 生产停服二次确认；删数据卷需额外强确认
$answer = Read-Host "[prod] 即将停止【生产环境】服务，确认继续？输入 yes 继续"
if ($answer -ne 'yes') {
    Write-Host "[prod] 已取消。" -ForegroundColor Yellow
    exit 0
}
if ($RemoveVolumes) {
    $vc = Read-Host "[prod] -RemoveVolumes 将永久删除生产数据卷(MySQL/Redis)，不可恢复！请输入 DELETE 以确认"
    if ($vc -ne 'DELETE') {
        Write-Host "[prod] 未确认删除数据卷，已取消。" -ForegroundColor Yellow
        exit 0
    }
}

$DownArgs = @('down')
if ($RemoveVolumes) { $DownArgs += '-v' }
if ($RemoveImages)  { $DownArgs += @('--rmi', 'local') }

Write-Host "[$Tag] env-file=$EnvFile, 执行 down $($DownArgs[1..($DownArgs.Count-1)] -join ' ') ..." -ForegroundColor Yellow
docker compose --env-file $EnvFile -f docker-compose.yml @DownArgs
docker compose --env-file $EnvFile -f docker-compose.yml ps
