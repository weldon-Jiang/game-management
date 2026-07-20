@echo off
chcp 65001 >nul
setlocal
echo ============================================
echo   BendPlatform 分控卸载脚本
echo ============================================
echo.
echo 此脚本将停止并删除分控的 4 个 Windows 服务及防火墙规则,
echo 之后您可以安全删除整个安装目录。
echo.
echo 安装目录: %~dp0
echo.

REM 1. 停止所有服务
echo [1/5] 停止服务...
sc stop BendTenantBackend >nul 2>&1
sc stop BendTenantGateway >nul 2>&1
sc stop BendTenantNginx   >nul 2>&1
sc stop BendTenantMySQL   >nul 2>&1
timeout /t 3 /nobreak >nul

REM 2. 删除服务
echo [2/5] 删除 Windows 服务...
sc delete BendTenantBackend >nul 2>&1
sc delete BendTenantGateway >nul 2>&1
sc delete BendTenantNginx   >nul 2>&1
sc delete BendTenantMySQL   >nul 2>&1

REM 3. 防火墙规则
echo [3/5] 删除防火墙规则...
netsh advfirewall firewall delete rule name="BendTenant-Web"     >nul 2>&1
netsh advfirewall firewall delete rule name="BendTenant-Gateway" >nul 2>&1

REM 4. 也尝试用 nssm 清理(如果安装目录还在)
if exist "%~dp0nssm.exe" (
    echo [4/5] nssm 清理残留...
    "%~dp0nssm.exe" stop BendTenantBackend  >nul 2>&1
    "%~dp0nssm.exe" stop BendTenantGateway  >nul 2>&1
    "%~dp0nssm.exe" stop BendTenantNginx    >nul 2>&1
    "%~dp0nssm.exe" remove BendTenantBackend confirm >nul 2>&1
    "%~dp0nssm.exe" remove BendTenantGateway confirm >nul 2>&1
    "%~dp0nssm.exe" remove BendTenantNginx   confirm >nul 2>&1
)

REM 5. 停止 MySQL (mysqld --remove)
if exist "%~dp0mysql\bin\mysqld.exe" (
    echo [5/5] MySQL 清理...
    "%~dp0mysql\bin\mysqld.exe" --remove BendTenantMySQL >nul 2>&1
)

echo.
echo ============================================
echo   卸载完成!
echo   您现在可以删除此安装目录:
echo   %~dp0
echo.
echo   注意: 安装目录下的 mysql\data 包含商户数据,
echo   如需保留请先备份。
echo ============================================
pause
