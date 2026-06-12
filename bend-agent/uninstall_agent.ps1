<#
.SYNOPSIS
卸载 Bend Agent（便携版 / 服务版通用）

.DESCRIPTION
1. 停止 BendAgent Windows 服务（若存在）
2. 调用 BendAgent.exe 或 python main.py --uninstall 通知平台并清理本地凭证
3. 清除注册表 HKCU\SOFTWARE\BendPlatform\Agent
4. 可选删除安装目录

.NOTES
Author: Bend Platform Team
#>

$ErrorActionPreference = "Stop"

$serviceName = "BendAgent"
$agentDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$registryPath = "HKCU:\SOFTWARE\BendPlatform\Agent"
$nssmPath = Join-Path $agentDir "nssm.exe"

function Clear-AgentInstallRegistry {
    if (Test-Path $registryPath) {
        Write-Host "正在清除注册表: $registryPath"
        Remove-Item -Path $registryPath -Recurse -Force
        Write-Host "注册表已清除" -ForegroundColor Green
    } else {
        Write-Host "未发现 Agent 注册表项，跳过" -ForegroundColor Yellow
    }
}

function Stop-AgentServiceIfExists {
    $existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if (-not $existingService) {
        return
    }

    Write-Host "正在停止服务 $serviceName..."
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    Write-Host "正在移除服务 $serviceName..."
    if (Test-Path $nssmPath) {
        & $nssmPath remove $serviceName confirm
    } else {
        sc.exe delete $serviceName | Out-Null
    }
    Write-Host "服务已移除" -ForegroundColor Green
}

function Invoke-AgentUninstallCommand {
    $exePath = Join-Path $agentDir "BendAgent.exe"
    $mainScript = Join-Path $agentDir "src\main.py"

    if (Test-Path $exePath) {
        Write-Host "正在执行: $exePath --uninstall"
        & $exePath --uninstall
        return $LASTEXITCODE -eq 0
    }

    if (Test-Path $mainScript) {
        $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
        if ($pythonPath) {
            Write-Host "正在执行: python main.py --uninstall"
            Push-Location (Join-Path $agentDir "src")
            try {
                & $pythonPath -X utf8 main.py --uninstall
                return $LASTEXITCODE -eq 0
            } finally {
                Pop-Location
            }
        }
    }

    return $false
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Bend Agent 卸载" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Stop-AgentServiceIfExists

$commandSucceeded = Invoke-AgentUninstallCommand
if (-not $commandSucceeded) {
    Write-Host "未能通过 Agent 程序卸载，将仅清理本地注册表与凭证目录" -ForegroundColor Yellow
    Clear-AgentInstallRegistry

    $credentialsDir = Join-Path $agentDir "credentials"
    if (Test-Path $credentialsDir) {
        Remove-Item -Path $credentialsDir -Recurse -Force
        Write-Host "已删除凭证目录: $credentialsDir" -ForegroundColor Green
    }
} else {
    # perform_agent_uninstall 已清注册表；此处兜底
    Clear-AgentInstallRegistry
}

$deleteFiles = Read-Host "是否删除 Agent 安装目录？(Y/N)"
if ($deleteFiles -eq "Y" -or $deleteFiles -eq "y") {
    Write-Host "请手动确认安装目录未被占用后删除: $agentDir"
    Write-Host "（脚本不从自身所在目录自删，请关闭本窗口后手动删除文件夹）" -ForegroundColor Yellow
} else {
    Write-Host "保留安装目录: $agentDir" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "卸载完成！如需重新安装，可将 Agent 解压到新目录并重新激活。" -ForegroundColor Green
