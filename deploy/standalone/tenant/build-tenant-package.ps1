# =================================================================
# 分控通用安装包打包脚本
# =================================================================
# 用途: 打一个通用分控绿色安装包(不含 License + 商户数据)
#       商户安装时输入激活码,安装器向总控实时签发 License + 拉取数据
#
# 前置条件:
#   1. 本机已装: Maven, Node(npm), Inno Setup(ISCC)
#   2. 已准备好 JRE21 green、MySQL8 green、nginx green、nssm.exe 放到 deploy/standalone/staging/base/
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File deploy\standalone\tenant\build-tenant-package.ps1
#
# 流程:
#   1. 构建 backend.jar / gateway.jar / web dist
#   2. 组装 staging(基础资源 + 占位 tenant.env + schema.sql + activate-tenant.ps1)
#   3. 调 ISCC 编译 tenant.iss -> Output/BendPlatformTenantSetup.exe
# =================================================================

param(
    [string] $BaseStagingDir = "deploy\standalone\staging\base",
    [string] $TenantStagingDir = "deploy\standalone\tenant\staging\tenant",
    [string] $IsccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"
# 脚本位于 deploy/standalone/tenant/ → 上溯 3 级到仓库根
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $RepoRoot

function Log($msg) { Write-Host "[build-tenant] $msg" -ForegroundColor Cyan }

# ---------- 1. 构建产物 ----------
Log "1/3 构建 backend.jar"
& mvn -f bend-platform\pom.xml -DskipTests clean package | Out-Null
Copy-Item bend-platform\target\*.jar $TenantStagingDir\backend.jar -Force

Log "1/3 构建 gateway.jar"
& mvn -f bend-gateway\pom.xml -DskipTests clean package | Out-Null
Copy-Item bend-gateway\target\*.jar $TenantStagingDir\gateway.jar -Force

Log "1/3 构建 web dist"
Push-Location bend-platform-web
& npm install --silent
& npm run build
Pop-Location
Copy-Item bend-platform-web\dist\* $TenantStagingDir\web -Recurse -Force

# ---------- 2. 组装 staging ----------
Log "2/3 组装 staging(基础资源 + schema + 激活脚本)"

# schema.sql（全量建表 + 全局配置数据 merchant_group）
Copy-Item bend-platform\db\schema.sql $TenantStagingDir\schema.sql -Force

# 复制基础 green 资源(打包者预先放好)
Copy-Item "$BaseStagingDir\jre"      $TenantStagingDir\jre -Recurse -Force
Copy-Item "$BaseStagingDir\mysql"   $TenantStagingDir\mysql -Recurse -Force
Copy-Item "$BaseStagingDir\nginx"   $TenantStagingDir\nginx -Recurse -Force
# 用分控专用 nginx.conf 覆盖 green 自带的(监听 0.0.0.0:8090 + 反代本机 gateway)
New-Item -ItemType Directory -Force -Path "$TenantStagingDir\nginx\conf" | Out-Null
Copy-Item deploy\standalone\tenant\nginx.conf "$TenantStagingDir\nginx\conf\nginx.conf" -Force
Copy-Item "$BaseStagingDir\nssm.exe" $TenantStagingDir\nssm.exe -Force
Copy-Item deploy\standalone\tenant\start-backend.bat $TenantStagingDir -Force

# 安装时激活脚本(安装器 [Run] 段调用)
Copy-Item deploy\standalone\tenant\activate-tenant.ps1 $TenantStagingDir\activate-tenant.ps1 -Force
# 升级脚本(安装器 [Run] 段调用)
Copy-Item deploy\standalone\tenant\upgrade-tenant.ps1 $TenantStagingDir\upgrade-tenant.ps1 -Force
# 增量 migration SQL(升级用,安装器 [Files] 段复制到 {app}\mysql\migration\)
New-Item -ItemType Directory -Force -Path "$TenantStagingDir\migration" | Out-Null
Copy-Item bend-platform\db\migration\V*.sql $TenantStagingDir\migration\ -Force

# 生成占位 tenant.env(LICENSE_KEY/SECRET/MASTER_URL 安装时由激活脚本回写)
$envContent = @"
LICENSE_KEY=__ACTIVATION_PENDING__
LICENSE_SECRET=__ACTIVATION_PENDING__
LICENSE_MASTER_URL=__ACTIVATION_PENDING__
LICENSE_MODE=tenant
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=bend_platform
DB_USERNAME=root
DB_PASSWORD=
JWT_SECRET=__ACTIVATION_PENDING__
AES_SECRET=__ACTIVATION_PENDING__
CORS_ENABLED=false
"@
$envContent | Out-File "$TenantStagingDir\tenant.env" -Encoding ascii
Log "tenant.env 已生成(占位模式,安装时激活回写)"

# ---------- 3. 编译安装包 ----------
Log "3/3 调 ISCC 编译分控通用安装包"
if (-not (Test-Path $IsccPath)) {
    throw "ISCC 未找到: $IsccPath"
}
& $IsccPath deploy\standalone\tenant\tenant.iss
Log "完成: deploy\standalone\tenant\Output\BendPlatformTenantSetup.exe"
Log "此安装包为通用包,不含 License 和商户数据,商户安装时输入激活码激活。"
