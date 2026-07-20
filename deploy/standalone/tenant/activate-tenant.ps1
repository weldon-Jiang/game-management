# =================================================================
# 分控安装激活脚本
# =================================================================
# 由 tenant.iss 安装器在 [Run] 段调用,在 MySQL 初始化完成后执行。
#
# 流程:
#   1. 收集本机指纹(MAC + 主机名)
#   2. POST {MasterUrl}/api/install/activate { activationCode, machineFingerprint }
#   3. 成功 → 回写 tenant.env(LICENSE_KEY/SECRET/MASTER_URL) + 保存 merchant_data.sql
#   4. 导入 merchant_data.sql 到本地 MySQL
#   5. 返回码: 0=成功 1=激活失败
#
# 调用方式:
#   powershell -ExecutionPolicy Bypass -File activate-tenant.ps1 `
#     -MasterUrl "http://总控地址:8060" `
#     -ActivationCode "激活码" `
#     -AppDir "C:\BendPlatformTenant"
# =================================================================

param(
    [Parameter(Mandatory=$true)] [string] $MasterUrl,
    [Parameter(Mandatory=$true)] [string] $ActivationCode,
    [Parameter(Mandatory=$true)] [string] $AppDir
)

$ErrorActionPreference = "Stop"

$tenantEnvFile = Join-Path $AppDir "tenant.env"
$merchantDataFile = Join-Path $AppDir "mysql\merchant_data.sql"
$mysqlBin = Join-Path $AppDir "mysql\bin\mysql.exe"

function Log($msg) { Write-Host "[activate-tenant] $msg" }

# ---------- 1. 收集机器指纹 ----------
Log "收集机器指纹..."
$mac = (Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object -First 1).MacAddress
if (-not $mac) {
    $mac = (Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled -eq $true } | Select-Object -First 1).MacAddress
}
$hostname = [System.Environment]::MachineName
$osVersion = (Get-WmiObject Win32_OperatingSystem).Caption

# SHA-256 哈希
$fingerprintRaw = "$mac|$hostname|$osVersion"
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$fingerprintBytes = $sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($fingerprintRaw))
$machineFingerprint = [BitConverter]::ToString($fingerprintBytes) -replace '-', ''
Log "机器指纹: $machineFingerprint"

# ---------- 2. 调总控激活接口 ----------
Log "向总控发送激活请求..."
$activateUrl = "$MasterUrl/api/install/activate"
$requestBody = @{
    activationCode     = $ActivationCode
    machineFingerprint = $machineFingerprint
} | ConvertTo-Json

try {
    # 使用 TLS 1.2
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

    $response = Invoke-RestMethod -Method Post -Uri $activateUrl `
        -ContentType "application/json" `
        -Body $requestBody `
        -TimeoutSec 30

    if ($response.code -ne 200) {
        $errorMsg = if ($response.message) { $response.message } else { "未知错误" }
        Log "激活失败: $errorMsg"
        Write-Host ""
        Write-Host "============================================" -ForegroundColor Red
        Write-Host "  激活失败: $errorMsg" -ForegroundColor Red
        Write-Host "  请检查:" -ForegroundColor Yellow
        Write-Host "  1. 总控地址是否正确: $MasterUrl" -ForegroundColor Yellow
        Write-Host "  2. 激活码是否输入正确且未使用" -ForegroundColor Yellow
        Write-Host "  3. 本机能访问总控网络" -ForegroundColor Yellow
        Write-Host "============================================" -ForegroundColor Red
        exit 1
    }

    $data = $response.data
    Log "激活成功! 商户: $($data.merchantName) ($($data.merchantId))"
    Log "License: $($data.licenseKey) 到期: $($data.expireAt)"
}
catch {
    $errMsg = $_.Exception.Message
    Log "激活请求失败: $errMsg"
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "  激活失败: 无法连接到总控" -ForegroundColor Red
    Write-Host "  错误: $errMsg" -ForegroundColor Red
    Write-Host "  请检查总控地址和网络连接: $MasterUrl" -ForegroundColor Yellow
    Write-Host "============================================" -ForegroundColor Red
    exit 1
}

# ---------- 3. 导入商户数据(设密码前,root 还无密码) ----------
Log "导入商户数据..."
$data.merchantData | Out-File $merchantDataFile -Encoding utf8
& $mysqlBin -u root bend_platform < $merchantDataFile 2>&1
if ($LASTEXITCODE -ne 0) {
    Log "商户数据导入失败(exit code=$LASTEXITCODE)"
    exit 1
}

# ---------- 4. 设置 MySQL root 密码(总控下发) ----------
$dbPassword = $data.dbPassword
if (-not $dbPassword -or $dbPassword -eq "") {
    $dbPassword = "D`$U@GAMECeKfidb"
}
Log "设置 MySQL root 密码..."
& $mysqlBin -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$dbPassword'; FLUSH PRIVILEGES;" 2>&1
if ($LASTEXITCODE -ne 0) {
    Log "WARN: MySQL 密码设置失败,继续安装(数据库无密码保护)"
}

# ---------- 5. 回写 tenant.env(含真实 DB_PASSWORD) ----------
Log "回写 tenant.env..."
$envContent = @"
LICENSE_KEY=$($data.licenseKey)
LICENSE_SECRET=$($data.licenseSecret)
LICENSE_MASTER_URL=$($data.masterUrl)
LICENSE_MODE=tenant
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=bend_platform
DB_USERNAME=root
DB_PASSWORD=$dbPassword
JWT_SECRET=tenant-$($data.merchantId)-$(Get-Random)
AES_SECRET=$([Convert]::ToBase64String([System.Security.Cryptography.Aes]::Create().Key))
CORS_ENABLED=false
"@
$envContent | Out-File $tenantEnvFile -Encoding ascii
Log "tenant.env 已回写"

Log "安装激活完成!"
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  激活成功! 商户: $($data.merchantName)" -ForegroundColor Green
Write-Host "  License 到期: $($data.expireAt)" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
exit 0
