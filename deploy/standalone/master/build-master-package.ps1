# =================================================================
# 总控包打包脚本
# =================================================================
# 用途: 打公网部署的总控安装包(backend+gateway+web+MySQL+Redis)
# 前置: 已装 Maven/Node/ISCC; JRE/MySQL/Redis/nginx green 放 deploy/standalone/staging/base/
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File deploy\standalone\master\build-master-package.ps1
# =================================================================

param(
    [string] $BaseStagingDir = "deploy\standalone\staging\base",
    [string] $MasterStagingDir = "deploy\standalone\master\staging\master",
    [string] $IsccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
$ErrorActionPreference = "Stop"
# 脚本位于 deploy/standalone/master/ → 上溯 3 级到仓库根
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $RepoRoot
function Log($m){ Write-Host "[build-master] $m" -ForegroundColor Cyan }

Log "构建 backend.jar"
& mvn -f bend-platform\pom.xml -DskipTests clean package | Out-Null
Copy-Item bend-platform\target\*.jar "$MasterStagingDir\backend.jar" -Force

Log "构建 gateway.jar"
& mvn -f bend-gateway\pom.xml -DskipTests clean package | Out-Null
Copy-Item bend-gateway\target\*.jar "$MasterStagingDir\gateway.jar" -Force

Log "构建 web dist"
Push-Location bend-platform-web
& npm install --silent
& npm run build
Pop-Location
New-Item -ItemType Directory -Force -Path "$MasterStagingDir\web" | Out-Null
Copy-Item bend-platform-web\dist\* "$MasterStagingDir\web" -Recurse -Force

Log "复制 green 基础资源"
Copy-Item "$BaseStagingDir\jre"   "$MasterStagingDir\jre"   -Recurse -Force
Copy-Item "$BaseStagingDir\mysql" "$MasterStagingDir\mysql" -Recurse -Force
Copy-Item "$BaseStagingDir\redis" "$MasterStagingDir\redis" -Recurse -Force
Copy-Item "$BaseStagingDir\nginx" "$MasterStagingDir\nginx" -Recurse -Force
Copy-Item "$BaseStagingDir\nssm.exe" "$MasterStagingDir" -Force
# schema.sql(总控建库脚本,安装时由 mysql 客户端执行)
Copy-Item bend-platform\db\schema.sql "$MasterStagingDir\schema.sql" -Force

Log "调 ISCC 编译总控安装包"
& $IsccPath deploy\standalone\master\master.iss
Log "完成: deploy\standalone\master\Output\BendPlatformMasterSetup.exe"
