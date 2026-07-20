@echo off
REM ================================================
REM 分控 Backend 启动脚本(由 nssm 服务调用)
REM 从 tenant.env 加载环境变量(LICENSE_KEY/LICENSE_SECRET/LICENSE_MASTER_URL 等)
REM 设 LOG_PATH 指向安装目录 logs/,再以 tenant profile 启动 backend
REM ================================================
cd /d "%~dp0"

set "LOG_PATH=%~dp0logs"
if not exist "%LOG_PATH%" mkdir "%LOG_PATH%"

REM 加载 tenant.env 到当前环境
if exist "%~dp0tenant.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0tenant.env") do (
        set "%%a=%%b"
    )
)

REM 以分控模式启动 backend
"%~dp0jre\bin\java.exe" -jar "%~dp0backend\backend.jar" --spring.profiles.active=tenant --server.port=8061
