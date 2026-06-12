<#
.SYNOPSIS
卸载 Bend Agent Windows 服务

.DESCRIPTION
停止并移除 Bend Agent Windows 服务，并可选删除相关文件。

.REQUIREMENTS
- 以管理员身份运行 PowerShell

.NOTES
Author: Bend Platform Team
Version: 1.0
#>

$ErrorActionPreference = "Stop"

# 服务配置
$serviceName = "BendAgent"
$agentDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$nssmPath = Join-Path $agentDir "nssm.exe"
$registryPath = "HKCU:\SOFTWARE\BendPlatform\Agent"

function Clear-AgentInstallRegistry {
    if (Test-Path $registryPath) {
        Write-Host "正在清除 Agent 注册表..."
        Remove-Item -Path $registryPath -Recurse -Force
        Write-Host "注册表已清除" -ForegroundColor Green
    }
}

# 检查管理员权限
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "请以管理员身份运行此脚本"
    exit 1
}

# 检查服务是否存在
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "正在停止服务 $serviceName..."
    Stop-Service -Name $serviceName -Force
    Start-Sleep -Seconds 2
    
    Write-Host "正在移除服务 $serviceName..."
    if (Test-Path $nssmPath) {
        & $nssmPath remove $serviceName confirm
    } else {
        # 如果没有 nssm，尝试使用 sc 命令
        sc.exe delete $serviceName
    }
    
    Write-Host "服务已移除" -ForegroundColor Green
} else {
    Write-Host "服务 $serviceName 不存在，跳过服务移除" -ForegroundColor Yellow
}

# 询问是否删除文件
$deleteFiles = Read-Host "是否删除 Agent 安装目录？(Y/N)"
if ($deleteFiles -eq "Y" -or $deleteFiles -eq "y") {
    Write-Host "正在删除目录: $agentDir"
    Remove-Item -Path $agentDir -Recurse -Force
    Write-Host "目录已删除" -ForegroundColor Green
} else {
    Write-Host "保留安装目录" -ForegroundColor Yellow
}

Clear-AgentInstallRegistry

Write-Host "`n卸载完成！" -ForegroundColor Green
Write-Host "如需彻底卸载凭证与平台绑定，请运行 uninstall_agent.ps1 或 BendAgent.exe --uninstall"