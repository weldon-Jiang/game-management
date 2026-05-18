# ============================================
# Bend Platform 完整部署脚本
# ============================================
# 功能：
#   1. 停止现有服务
#   2. 构建并启动所有Docker服务
#   3. 执行数据库迁移
#   4. 验证服务健康状态
# ============================================

param(
    [switch]$SkipBuild,
    [switch]$SkipMigration,
    [switch]$OnlyStart
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Bend Platform 自动化部署工具" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查Docker
Write-Host "检查Docker环境..." -ForegroundColor Yellow
try {
    docker version | Out-Null
    Write-Host "✓ Docker 正在运行" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker 未运行，请先启动Docker Desktop" -ForegroundColor Red
    exit 1
}

# 检查Docker Compose
try {
    docker compose version | Out-Null
    Write-Host "✓ Docker Compose 可用" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker Compose 不可用" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 步骤1：停止现有服务
if (-not $OnlyStart) {
    Write-Host "步骤1/5：停止现有服务..." -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor Gray
    try {
        docker compose -f docker-compose.yml down
        Write-Host "✓ 现有服务已停止" -ForegroundColor Green
    } catch {
        Write-Host "⚠ 停止服务时出现问题（可能服务未运行）" -ForegroundColor Yellow
    }
    Write-Host ""
}

# 步骤2：构建并启动服务
Write-Host "步骤2/5：构建并启动Docker服务..." -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray

if ($SkipBuild) {
    Write-Host "跳过构建，直接启动现有镜像..." -ForegroundColor Yellow
    $buildArgs = ""
} else {
    Write-Host "构建服务镜像（可能需要一些时间）..." -ForegroundColor Yellow
    $buildArgs = "--build"
}

try {
    docker compose -f docker-compose.yml --profile full up -d $buildArgs
    
    Write-Host ""
    Write-Host "✓ 服务启动命令已执行" -ForegroundColor Green
    Write-Host ""
    Write-Host "等待服务初始化（约2-5分钟）..." -ForegroundColor Yellow
    Write-Host "您可以按 Ctrl+C 跳过等待，稍后手动检查" -ForegroundColor Gray
    Write-Host ""
    
    # 等待服务启动
    $maxWait = 300  # 5分钟
    $waitInterval = 10
    $elapsed = 0
    
    while ($elapsed -lt $maxWait) {
        Write-Host -NoNewline "`r等待中... ${elapsed}s/${maxWait}s" -ForegroundColor Gray
        
        # 检查服务状态
        $healthy = $true
        $services = @("mysql", "redis", "backend", "gateway", "frontend")
        foreach ($svc in $services) {
            $status = docker inspect --format='{{.State.Health.Status}}' "bend-xbox-$svc" 2>$null
            if ($status -ne "healthy" -and $svc -ne "frontend") {
                $healthy = $false
                break
            }
        }
        
        if ($healthy) {
            Write-Host "`n✓ 所有核心服务健康检查通过！" -ForegroundColor Green
            break
        }
        
        Start-Sleep -Seconds $waitInterval
        $elapsed += $waitInterval
    }
    
    if ($elapsed -ge $maxWait) {
        Write-Host "`n⚠ 等待超时，请稍后检查服务状态" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "`n✗ 服务启动失败：$_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 步骤3：显示服务状态
Write-Host "步骤3/5：检查服务状态..." -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray
docker compose -f docker-compose.yml ps
Write-Host ""

# 步骤4：执行数据库迁移
if (-not $SkipMigration) {
    Write-Host "步骤4/5：执行数据库迁移..." -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor Gray
    
    # 先检查MySQL是否就绪
    $mysqlReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        $status = docker inspect --format='{{.State.Health.Status}}' bend-xbox-mysql 2>$null
        if ($status -eq "healthy") {
            $mysqlReady = $true
            break
        }
        Write-Host -NoNewline "`r等待MySQL就绪... ${i}s/30s" -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
    
    if (-not $mysqlReady) {
        Write-Host "`n⚠ MySQL未完全就绪，跳过自动迁移" -ForegroundColor Yellow
        Write-Host "稍后可以手动运行：.\run-migration.ps1" -ForegroundColor Gray
    } else {
        Write-Host "`nMySQL已就绪，执行迁移..." -ForegroundColor Green
        
        try {
            # 先检查是否有迁移脚本
            $migrationScript = "../bend-platform/db/migration/20260516_add_system_info_fields.sql"
            if (Test-Path $migrationScript) {
                # 复制脚本到Docker容器
                docker cp $migrationScript bend-xbox-mysql:/tmp/migration.sql 2>$null
                
                # 执行迁移
                $env:MYSQL_PWD = (Get-Content .env | Select-String '^MYSQL_ROOT_PASSWORD=').ToString().Split('=')[1]
                docker exec -i bend-xbox-mysql mysql -u root -D bend_platform < $migrationScript 2>&1 | Out-Null
                
                Write-Host "✓ 数据库迁移执行完成" -ForegroundColor Green
            } else {
                Write-Host "⚠ 迁移脚本不存在，跳过" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "⚠ 迁移执行过程有问题：$_" -ForegroundColor Yellow
            Write-Host "稍后可以手动运行：.\run-migration.ps1" -ForegroundColor Gray
        }
    }
    Write-Host ""
} else {
    Write-Host "步骤4/5：跳过数据库迁移" -ForegroundColor Yellow
    Write-Host ""
}

# 步骤5：显示访问信息
Write-Host "步骤5/5：部署完成！" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "✓ Bend Platform 部署成功！" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "服务访问地址：" -ForegroundColor Yellow
Write-Host "  前端界面：http://localhost:3090" -ForegroundColor White
Write-Host "  API网关： http://localhost:8060" -ForegroundColor White
Write-Host ""
Write-Host "常用命令：" -ForegroundColor Yellow
Write-Host "  查看日志：    docker compose -f docker-compose.yml logs -f [service]" -ForegroundColor Gray
Write-Host "  查看状态：    docker compose -f docker-compose.yml ps" -ForegroundColor Gray
Write-Host "  停止服务：    docker compose -f docker-compose.yml down" -ForegroundColor Gray
Write-Host "  启动服务：    docker compose -f docker-compose.yml --profile full up -d" -ForegroundColor Gray
Write-Host "  数据库迁移：  .\run-migration.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "服务状态检查中（30秒后自动关闭）..." -ForegroundColor Gray

# 最后再显示一次状态
Start-Sleep -Seconds 2
Write-Host ""
docker compose -f docker-compose.yml ps