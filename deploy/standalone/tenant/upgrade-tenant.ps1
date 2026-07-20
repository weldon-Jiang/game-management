# =================================================================
# 分控升级脚本
# =================================================================
# 由 tenant.iss 安装器在 [Run] 段调用（仅升级模式）。
#
# 流程：
#   1. 读取 tenant.env 获取数据库连接信息
#   2. 创建迁移追踪表 _migrations（不存在则建）
#   3. 扫描 mysql\migration\V*.sql，按文件名字典序
#   4. 跳过已执行的，执行未执行的
#   5. 记录执行结果
#
# 调用方式：
#   powershell -ExecutionPolicy Bypass -File upgrade-tenant.ps1 -AppDir "C:\BendPlatformTenant"
# =================================================================

param(
    [Parameter(Mandatory=$true)] [string] $AppDir
)

$ErrorActionPreference = "Stop"

$tenantEnvFile = Join-Path $AppDir "tenant.env"
$mysqlBin      = Join-Path $AppDir "mysql\bin\mysql.exe"
$migrationDir  = Join-Path $AppDir "mysql\migration"
$logFile       = Join-Path $AppDir "logs\upgrade.log"

# 确保日志目录存在
$logsDir = Join-Path $AppDir "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
}

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [upgrade] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

# ---------- 1. 读取 tenant.env ----------
Log "读取 tenant.env..."
if (-not (Test-Path $tenantEnvFile)) {
    Log "错误: tenant.env 不存在,无法确定数据库连接信息。"
    Log "如果是首次安装,不应执行此升级脚本。"
    exit 1
}

$envContent = Get-Content $tenantEnvFile -Raw
$dbHost     = "127.0.0.1"
$dbPort     = "3306"
$dbName     = "bend_platform"
$dbUser     = "root"
$dbPassword = ""

foreach ($line in ($envContent -split "`n")) {
    if ($line -match '^\s*DB_HOST\s*=\s*(.+)\s*$')       { $dbHost     = $matches[1].Trim() }
    if ($line -match '^\s*DB_PORT\s*=\s*(.+)\s*$')       { $dbPort     = $matches[1].Trim() }
    if ($line -match '^\s*DB_NAME\s*=\s*(.+)\s*$')       { $dbName     = $matches[1].Trim() }
    if ($line -match '^\s*DB_USERNAME\s*=\s*(.+)\s*$')   { $dbUser     = $matches[1].Trim() }
    if ($line -match '^\s*DB_PASSWORD\s*=\s*(.+)\s*$')   { $dbPassword = $matches[1].Trim() }
}

Log "数据库: ${dbHost}:${dbPort}/${dbName} user=${dbUser}"

# ---------- 2. 构建 MySQL 命令行 ----------
$mysqlArgs = @("-u", $dbUser, "-h", $dbHost, "-P", $dbPort, "-D", $dbName)
if ($dbPassword -and $dbPassword -ne "") {
    # 通过环境变量传密码，避免命令行暴露
    $env:MYSQL_PWD = $dbPassword
}

function Invoke-MySQL($sql) {
    if ($dbPassword -and $dbPassword -ne "") {
        $env:MYSQL_PWD = $dbPassword
    }
    & $mysqlBin @mysqlArgs -e $sql 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "MySQL 执行失败 (exit=$LASTEXITCODE): $sql"
    }
}

function Invoke-MySQLFile($file) {
    if ($dbPassword -and $dbPassword -ne "") {
        $env:MYSQL_PWD = $dbPassword
    }
    Get-Content $file | & $mysqlBin @mysqlArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "MySQL 文件执行失败 (exit=$LASTEXITCODE): $file"
    }
}

# ---------- 3. 测试数据库连通性 ----------
Log "测试数据库连接..."
try {
    Invoke-MySQL "SELECT 1" | Out-Null
    Log "数据库连接成功"
} catch {
    Log "错误: 无法连接数据库 —— $_"
    Log "请确认 BendTenantMySQL 服务已启动。"
    exit 1
}

# ---------- 4. 创建迁移追踪表 ----------
Log "检查迁移追踪表..."
$createTrackingTable = @"
CREATE TABLE IF NOT EXISTS `_migrations` (
    `filename` VARCHAR(255) NOT NULL COMMENT '迁移脚本文件名',
    `executed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '执行时间',
    `duration_ms` INT NOT NULL DEFAULT 0 COMMENT '执行耗时(毫秒)',
    PRIMARY KEY (`filename`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库迁移追踪表(由 upgrade-tenant.ps1 维护)';
"@
try {
    Invoke-MySQL $createTrackingTable
    Log "迁移追踪表就绪"
} catch {
    Log "错误: 创建迁移追踪表失败 —— $_"
    exit 1
}

# ---------- 5. 读取已执行的迁移 ----------
$executedMigrations = @{}
try {
    $result = Invoke-MySQL "SELECT filename FROM _migrations ORDER BY filename"
    foreach ($line in $result) {
        $trimmed = $line.Trim()
        if ($trimmed -and $trimmed -ne 'filename') {
            $executedMigrations[$trimmed] = $true
        }
    }
    Log "已执行迁移: $($executedMigrations.Count) 个"
} catch {
    Log "警告: 读取迁移记录失败,将尝试执行所有迁移 —— $_"
}

# ---------- 6. 扫描并执行增量迁移 ----------
if (-not (Test-Path $migrationDir)) {
    Log "迁移目录不存在: $migrationDir (无可执行迁移)"
    Log "升级完成!"
    exit 0
}

$migrationFiles = Get-ChildItem -Path $migrationDir -Filter "V*.sql" | Sort-Object Name

if ($migrationFiles.Count -eq 0) {
    Log "未找到增量迁移脚本(V*.sql)"
    Log "升级完成!"
    exit 0
}

$executedCount = 0
$skippedCount  = 0
$failedCount   = 0

foreach ($file in $migrationFiles) {
    $filename = $file.Name

    # 跳过非版本化脚本（utility_ 前缀等）
    if ($filename -notmatch '^V\d{8}_\d{3}_.*\.sql$') {
        Log "跳过非版本化脚本: $filename"
        continue
    }

    if ($executedMigrations.ContainsKey($filename)) {
        Log "跳过(已执行): $filename"
        $skippedCount++
        continue
    }

    Log "执行: $filename"
    $startTime = Get-Date
    try {
        Invoke-MySQLFile $file.FullName
        $elapsed = [int]((Get-Date) - $startTime).TotalMilliseconds

        # 记录执行成功
        $escapedName = $filename -replace "'", "''"
        Invoke-MySQL "INSERT INTO _migrations (filename, duration_ms) VALUES ('$escapedName', $elapsed)"
        Log "  成功 (${elapsed}ms)"
        $executedCount++
    } catch {
        Log "  失败: $_"
        $failedCount++
        # 不退出：后续迁移可能独立于此迁移
    }
}

# ---------- 7. 汇总 ----------
Log "============================================"
Log "升级完成: 执行 $executedCount 个, 跳过 $skippedCount 个, 失败 $failedCount 个"
if ($failedCount -gt 0) {
    Log "警告: 有迁移执行失败,请检查日志: $logFile"
    exit 1
}
Log "============================================"
exit 0
