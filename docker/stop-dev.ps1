#!/usr/bin/env pwsh
# ============================================
# 开发环境 (dev) 停服 / 清理脚本
# 用法：
#   ./stop-dev.ps1                  # 停止并移除容器（保留数据卷）
#   ./stop-dev.ps1 -RemoveVolumes   # 停止并移除容器 + 数据卷（清空 MySQL/Redis 数据）
#   ./stop-dev.ps1 -RemoveImages    # 同时移除本项目构建的镜像
# ============================================
param(
    [switch]$RemoveVolumes,
    [switch]$RemoveImages
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$EnvFile = '.env.dev'
$Tag = 'dev'

$DownArgs = @('down')
if ($RemoveVolumes) { $DownArgs += '-v' }
if ($RemoveImages)  { $DownArgs += @('--rmi', 'local') }

Write-Host "[$Tag] env-file=$EnvFile, 执行 down $($DownArgs[1..($DownArgs.Count-1)] -join ' ') ..." -ForegroundColor Cyan
docker compose --env-file $EnvFile -f docker-compose.yml @DownArgs
docker compose --env-file $EnvFile -f docker-compose.yml ps
