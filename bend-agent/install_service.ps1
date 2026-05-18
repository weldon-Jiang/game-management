<#
.SYNOPSIS
安装 Bend Agent 为 Windows 服务

.DESCRIPTION
将 Bend Agent 注册为 Windows 服务，使其可以在后台运行，不受终端关闭影响。

.REQUIREMENTS
- 以管理员身份运行 PowerShell
- 需要安装 NSSM (Non-Sucking Service Manager)

.NOTES
Author: Bend Platform Team
Version: 1.0
#>

$ErrorActionPreference = "Stop"

# 服务配置
$serviceName = "BendAgent"
$serviceDisplayName = "Bend Agent Service"
$serviceDescription = "Bend Platform Agent - Xbox自动化服务"

# 文件路径
$agentDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$pythonPath = (Get-Command python).Source
$mainScript = Join-Path $agentDir "src/main.py"
$nssmPath = Join-Path $agentDir "nssm.exe"

# 检查管理员权限
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "请以管理员身份运行此脚本"
    exit 1
}

# 检查 NSSM 是否存在
if (-not (Test-Path $nssmPath)) {
    Write-Host "正在下载 NSSM..."
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $nssmZip = Join-Path $env:TEMP "nssm-2.24.zip"
    
    # 下载并解压
    Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip
    Expand-Archive -Path $nssmZip -DestinationPath $agentDir
    Move-Item -Path (Join-Path $agentDir "nssm-2.24\win64\nssm.exe") -Destination $nssmPath -Force
    Remove-Item -Path (Join-Path $agentDir "nssm-2.24") -Recurse -Force
    Remove-Item -Path $nssmZip -Force
    
    Write-Host "NSSM 下载完成"
}

# 检查服务是否已存在
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "服务 $serviceName 已存在，正在删除..."
    & $nssmPath remove $serviceName confirm
}

# 安装服务
Write-Host "正在安装服务 $serviceName..."
& $nssmPath install $serviceName $pythonPath $mainScript

# 配置服务参数
Write-Host "正在配置服务参数..."
& $nssmPath set $serviceName DisplayName "$serviceDisplayName"
& $nssmPath set $serviceName Description "$serviceDescription"
& $nssmPath set $serviceName Start SERVICE_AUTO_START
& $nssmPath set $serviceName AppDirectory "$agentDir"
& $nssmPath set $serviceName AppStdout (Join-Path $agentDir "logs/service_stdout.log")
& $nssmPath set $serviceName AppStderr (Join-Path $agentDir "logs/service_stderr.log")
& $nssmPath set $serviceName AppExit Default Exit

# 创建日志目录
New-Item -Path (Join-Path $agentDir "logs") -ItemType Directory -Force | Out-Null

# 启动服务
Write-Host "正在启动服务..."
Start-Service -Name $serviceName

# 检查服务状态
Start-Sleep -Seconds 2
$service = Get-Service -Name $serviceName
if ($service.Status -eq "Running") {
    Write-Host "`n服务安装并启动成功！" -ForegroundColor Green
    Write-Host "服务名称: $serviceName"
    Write-Host "服务状态: $($service.Status)"
    Write-Host "日志位置: $(Join-Path $agentDir "logs")"
    Write-Host "`n管理命令:"
    Write-Host "  启动服务: Start-Service $serviceName"
    Write-Host "  停止服务: Stop-Service $serviceName"
    Write-Host "  查看状态: Get-Service $serviceName"
    Write-Host "  卸载服务: & '$nssmPath' remove $serviceName confirm"
} else {
    Write-Error "服务启动失败，请检查日志"
    exit 1
}