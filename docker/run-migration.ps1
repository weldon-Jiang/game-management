# ============================================
# Bend Platform 数据库迁移执行脚本
# ============================================
# 功能：
#   1. 检查数据库连接
#   2. 执行数据库迁移脚本
#   3. 验证迁移结果
# ============================================

param(
    [string]$EnvFile = ".env",
    [string]$MigrationScript = "../bend-platform/db/migration/20260516_add_system_info_fields.sql",
    [switch]$VerifyOnly
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Bend Platform 数据库迁移工具" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查环境文件
if (-not (Test-Path $EnvFile)) {
    Write-Host "错误：找不到环境配置文件 $EnvFile" -ForegroundColor Red
    Write-Host "请先复制 .env.example 为 .env 并配置相应参数" -ForegroundColor Yellow
    exit 1
}

# 加载环境变量
Write-Host "正在加载环境配置..." -ForegroundColor Yellow
$envContent = Get-Content $EnvFile
foreach ($line in $envContent) {
    if ($line -match '^\s*([^#=]+)\s*=\s*(.+)\s*$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value)
    }
}

# 获取数据库配置
$MYSQL_HOST = [Environment]::GetEnvironmentVariable("MYSQL_HOST") ?? "127.0.0.1"
$MYSQL_PORT = [Environment]::GetEnvironmentVariable("MYSQL_PORT") ?? "3306"
$MYSQL_DATABASE = [Environment]::GetEnvironmentVariable("MYSQL_DATABASE") ?? "bend_platform"
$MYSQL_USER = [Environment]::GetEnvironmentVariable("MYSQL_USER") ?? "root"
$MYSQL_PASSWORD = [Environment]::GetEnvironmentVariable("MYSQL_PASSWORD")
$MYSQL_ROOT_PASSWORD = [Environment]::GetEnvironmentVariable("MYSQL_ROOT_PASSWORD")

# 解析端口
if ($MYSQL_PORT -match ':(\d+)$') {
    $MYSQL_PORT = $matches[1]
}

Write-Host "数据库配置：" -ForegroundColor Green
Write-Host "  Host: $MYSQL_HOST" -ForegroundColor Gray
Write-Host "  Port: $MYSQL_PORT" -ForegroundColor Gray
Write-Host "  Database: $MYSQL_DATABASE" -ForegroundColor Gray
Write-Host "  User: $MYSQL_USER" -ForegroundColor Gray
Write-Host ""

# 检查Docker MySQL是否在运行
Write-Host "检查MySQL容器状态..." -ForegroundColor Yellow
$mysqlContainer = docker ps --filter "name=bend-xbox-mysql" --format "{{.Names}}" 2>$null
if ($mysqlContainer -eq "bend-xbox-mysql") {
    Write-Host "✓ MySQL容器正在运行" -ForegroundColor Green
    $useDocker = $true
} else {
    Write-Host "⚠ MySQL容器未运行或未找到" -ForegroundColor Yellow
    Write-Host "尝试直接连接MySQL..." -ForegroundColor Yellow
    $useDocker = $false
}

Write-Host ""

# 检查迁移脚本
if (-not (Test-Path $MigrationScript)) {
    Write-Host "错误：找不到迁移脚本 $MigrationScript" -ForegroundColor Red
    exit 1
}

Write-Host "迁移脚本：$MigrationScript" -ForegroundColor Green
Write-Host ""

if ($VerifyOnly) {
    Write-Host "仅验证模式，不执行迁移" -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

# 确认执行
$confirm = Read-Host "是否执行数据库迁移? (y/N)"
if ($confirm -notmatch '^[Yy]') {
    Write-Host "迁移已取消" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "开始执行数据库迁移..." -ForegroundColor Cyan
Write-Host ""

try {
    if ($useDocker) {
        # 使用Docker容器执行
        Write-Host "通过Docker容器执行迁移..." -ForegroundColor Yellow
        
        # 复制迁移脚本到容器
        docker cp $MigrationScript bend-xbox-mysql:/tmp/migration.sql
        if ($LASTEXITCODE -ne 0) {
            throw "复制迁移脚本到容器失败"
        }
        
        # 执行迁移
        $env:MYSQL_PWD = $MYSQL_ROOT_PASSWORD
        docker exec -i bend-xbox-mysql mysql -u root -D $MYSQL_DATABASE < $MigrationScript
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "============================================" -ForegroundColor Green
            Write-Host "✓ 数据库迁移执行成功！" -ForegroundColor Green
            Write-Host "============================================" -ForegroundColor Green
        } else {
            throw "迁移脚本执行失败"
        }
        
    } else {
        # 尝试直接使用mysql命令
        Write-Host "尝试直接使用mysql命令执行迁移..." -ForegroundColor Yellow
        
        $env:MYSQL_PWD = $MYSQL_ROOT_PASSWORD
        $mysqlCmd = "mysql -h $MYSQL_HOST -P $MYSQL_PORT -u root -D $MYSQL_DATABASE -e `"source $((Resolve-Path $MigrationScript).Path)`""
        
        Invoke-Expression $mysqlCmd
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "============================================" -ForegroundColor Green
            Write-Host "✓ 数据库迁移执行成功！" -ForegroundColor Green
            Write-Host "============================================" -ForegroundColor Green
        } else {
            throw "迁移脚本执行失败，请确保MySQL正在运行且可访问"
        }
    }
    
} catch {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "✗ 数据库迁移失败：" -ForegroundColor Red
    Write-Host "  $_" -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "请检查：" -ForegroundColor Yellow
    Write-Host "  1. MySQL服务是否在运行" -ForegroundColor Gray
    Write-Host "  2. 数据库连接配置是否正确" -ForegroundColor Gray
    Write-Host "  3. 用户权限是否足够" -ForegroundColor Gray
    Write-Host ""
    exit 1
}