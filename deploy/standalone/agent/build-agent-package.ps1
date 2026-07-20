# =================================================================
# Agent 包打包脚本
# =================================================================
# 用途: 打 Agent 安装包(含 BendAgent.exe + Chromium + VC++ redist)
# 前置:
#   - Python 环境可用(或直接用已有的 dist/BendAgent.exe)
#   - 已执行 bend-agent/scripts/build.bat 生成 BendAgent.exe
#   - Chromium 目录 + vc_redist.x64.exe + nssm.exe 放 deploy/standalone/staging/agent/
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File deploy\standalone\agent\build-agent-package.ps1 `
#     -TenantBaseUrl "http://192.168.1.10:8060" `
#     -RegistrationCode "AGENT-XXXX-XXXX-XXXX"
# =================================================================

param(
    # Agent 现在自动发现分控(UDP),不再需要预填地址/注册码。
    # 以下参数保留兼容:非强制,留空=Agent 启动后 UDP 自动发现分控。
    [string] $TenantBaseUrl = "",       # 留空=自动发现; 填地址=强制指定(如 http://192.168.1.10:8060)
    [string] $RegistrationCode = "",   # 免注册码自动注册场景下留空即可
    [string] $AgentStagingDir = "deploy\standalone\agent\staging\agent",
    [string] $IsccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
$ErrorActionPreference = "Stop"
# 脚本位于 deploy/standalone/agent/ → 上溯 3 级到仓库根
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $RepoRoot
function Log($m){ Write-Host "[build-agent] $m" -ForegroundColor Cyan }

Log "构建 BendAgent.exe(若已存在则跳过)"
$agentExe = "bend-agent\dist\BendAgent.exe"
if (-not (Test-Path $agentExe)) {
    Push-Location bend-agent
    & .\scripts\build.bat
    Pop-Location
}
New-Item -ItemType Directory -Force -Path $AgentStagingDir | Out-Null
Copy-Item $agentExe "$AgentStagingDir\BendAgent.exe" -Force

Log "生成 agent.yaml(留空占位=安装后UDP自动发现分控)"
if ($TenantBaseUrl -ne "") {
    $wsUrl = $TenantBaseUrl -replace "^http", "ws"
    $yaml = @"
backend:
  base_url: "$TenantBaseUrl"
  ws_url: "$wsUrl/ws/agent"
  api_prefix: "/api"
  registration_code: "$RegistrationCode"
"@
} else {
    # 占位:Agent 首启动识别为占位,触发 UDP 自动发现分控 IP 并回写
    $yaml = @"
backend:
  base_url: "本机分控地址"
  ws_url: "本机分控地址"
  api_prefix: "/api"
  registration_code: "$RegistrationCode"
"@
}
$yaml | Out-File "$AgentStagingDir\agent.yaml" -Encoding utf8

Log "复制场景模板"
Copy-Item bend-agent\templates\* "$AgentStagingDir\templates" -Recurse -Force -ErrorAction SilentlyContinue

Log "复制卸载脚本"
Copy-Item bend-agent\uninstall_agent.ps1 "$AgentStagingDir\" -Force -ErrorAction SilentlyContinue

# 打包者需预先放入: chromium/, vc_redist.x64.exe, nssm.exe
Log "请确保 staging/agent 下已有: chromium/ (Playwright浏览器), vc_redist.x64.exe, nssm.exe"

Log "调 ISCC 编译 Agent 安装包"
& $IsccPath deploy\standalone\agent\agent.iss
Log "完成: deploy\standalone\agent\Output\BendAgentSetup.exe"
