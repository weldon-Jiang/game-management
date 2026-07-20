#!/usr/bin/env pwsh
# ============================================
# SIT 测试环境 (sit) 停服 / 清理脚本
# 用法：
#   ./stop-sit.ps1                  # 停止并移除容器（保留数据卷）
#   ./stop-sit.ps1 -RemoveVolumes   # 停止并移除容器 + 数据卷（清空 MySQL/Redis 数据）
#   ./stop-sit.ps1 -RemoveImages    # 同时移除本项目构建的镜像
# ============================================
param(
    [switch]$RemoveVolumes,
    [switch]$RemoveImages
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$EnvFiles = @('.env', '.env.sit')
$Tag = 'sit'

$DownArgs = @('down')
if ($RemoveVolumes) { $DownArgs += '-v' }
if ($RemoveImages)  { $DownArgs += @('--rmi', 'local') }

Write-Host "[$Tag] env-files=$($EnvFiles -join ', '), 执行 down $($DownArgs[1..($DownArgs.Count-1)] -join ' ') ..." -ForegroundColor Cyan
docker compose --env-file $($EnvFiles[0]) --env-file $($EnvFiles[1]) -f docker-compose.yml @DownArgs
docker compose --env-file $($EnvFiles[0]) --env-file $($EnvFiles[1]) -f docker-compose.yml ps
