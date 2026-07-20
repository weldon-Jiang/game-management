@echo off
chcp 65001 >nul
setlocal
echo ============================================
echo   BendAgent 卸载脚本
echo ============================================
echo.
echo 此脚本将停止并删除 BendAgent 服务,
echo 之后您可以安全删除整个安装目录。
echo.
echo 安装目录: %~dp0
echo.

REM 停止服务
sc stop BendAgent >nul 2>&1
echo [1/3] 正在停止 BendAgent 服务...

REM 等待进程退出
timeout /t 2 /nobreak >nul

REM 删除服务
sc delete BendAgent >nul 2>&1
echo [2/3] 已删除 BendAgent 服务

REM 清理系统环境变量 PLAYWRIGHT_BROWSERS_PATH
setx PLAYWRIGHT_BROWSERS_PATH "" /M >nul 2>&1
echo [3/3] 已清理系统环境变量

echo.
echo ============================================
echo   卸载完成!
echo   您现在可以删除此安装目录:
echo   %~dp0
echo ============================================
pause
