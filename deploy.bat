@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   Bend Platform 部署脚本
echo ============================================
echo.

:: 检查 Docker 是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未安装或未启动
    echo 请先安装 Docker Desktop
    pause
    exit /b 1
)

:: 检查 Docker Compose 是否可用
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker Compose 不可用
    echo 请确保 docker-compose 已安装
    pause
    exit /b 1
)

:: 设置默认参数
set PROFILE=
set COMMAND=up -d
set CLEAN_VOLUMES=
set COMPOSE_FILE=%~dp0docker\docker-compose.yml

:: 解析参数
if "%~1"=="" goto menu
if /i "%~1"=="full" set PROFILE=--profile full& goto run
if /i "%~1"=="core" set PROFILE=--profile core& goto run
if /i "%~1"=="data" set PROFILE=--profile data& goto run
if /i "%~1"=="restart" goto do_restart
if /i "%~1"=="stop" goto do_stop
if /i "%~1"=="logs" goto do_logs
if /i "%~1"=="clean" set CLEAN_VOLUMES=-v& goto do_clean
if /i "%~1"=="status" goto do_status
if /i "%~1"=="rebuild" goto do_rebuild
goto menu

:menu
echo 请选择操作：
echo.
echo   [1] 启动完整环境（含前端）
echo   [2] 启动核心后端（无前端）
echo   [3] 启动数据层（MySQL + Redis）
echo   [4] 重启所有服务
echo   [5] 停止所有服务
echo   [6] 查看日志
echo   [7] 重新构建镜像
echo   [8] 完全清理（包括数据）
echo   [9] 查看服务状态
echo   [0] 退出
echo.
set /p choice=请输入选项 [1-9, 0]:

if "%choice%"=="1" set PROFILE=--profile full& goto run
if "%choice%"=="2" set PROFILE=--profile core& goto run
if "%choice%"=="3" set PROFILE=--profile data& goto run
if "%choice%"=="4" goto do_restart
if "%choice%"=="5" goto do_stop
if "%choice%"=="6" goto do_logs
if "%choice%"=="7" goto do_rebuild
if "%choice%"=="8" goto do_clean
if "%choice%"=="9" goto do_status
if "%choice%"=="0" exit /b
goto menu

:run
echo.
echo [%date% %time%] 正在启动服务...
echo PROFILE: %PROFILE%
echo.
docker compose -f "%COMPOSE_FILE%" %PROFILE% up -d --build
if errorlevel 1 (
    echo.
    echo [错误] 服务启动失败
    pause
    exit /b 1
)
echo.
echo [%date% %time%] 服务启动完成
echo.
echo 服务状态：
docker compose -f "%COMPOSE_FILE%" ps
echo.
echo 访问地址：
echo   前端:   http://localhost:3090
echo   网关:   http://localhost:8060
echo   后端:   http://localhost:8061
echo.
pause
exit /b 0

:do_restart
echo.
echo [%date% %time%] 正在重启服务...
docker compose -f "%COMPOSE_FILE%" restart
echo.
echo [%date% %time%] 重启完成
docker compose -f "%COMPOSE_FILE%" ps
pause
exit /b 0

:do_stop
echo.
echo [%date% %time%] 正在停止服务...
docker compose -f "%COMPOSE_FILE%" down
echo.
echo [%date% %time%] 服务已停止
pause
exit /b 0

:do_logs
echo.
echo 请选择要查看的日志：
echo.
echo   [1] 全部日志
echo   [2] Gateway 日志
echo   [3] 后端日志
echo   [4] MySQL 日志
echo   [5] Redis 日志
echo   [6] 前端日志
echo   [0] 返回
echo.
set /p log_choice=请输入选项:

if "%log_choice%"=="1" docker compose -f "%COMPOSE_FILE%" logs -f
if "%log_choice%"=="2" docker compose -f "%COMPOSE_FILE%" logs -f gateway
if "%log_choice%"=="3" docker compose -f "%COMPOSE_FILE%" logs -f backend
if "%log_choice%"=="4" docker compose -f "%COMPOSE_FILE%" logs -f mysql
if "%log_choice%"=="5" docker compose -f "%COMPOSE_FILE%" logs -f redis
if "%log_choice%"=="6" docker compose -f "%COMPOSE_FILE%" logs -f frontend
if "%log_choice%"=="0" goto menu
exit /b 0

:do_rebuild
echo.
echo [%date% %time%] 正在重新构建镜像...
docker compose -f "%COMPOSE_FILE%" build --no-cache
if errorlevel 1 (
    echo.
    echo [错误] 构建失败
    pause
    exit /b 1
)
echo.
echo [%date% %time%] 重新启动服务...
docker compose -f "%COMPOSE_FILE%" up -d
echo.
echo [%date% %time%] 完成
pause
exit /b 0

:do_clean
echo.
echo [警告] 即将删除所有容器、网络和数据卷！
echo.
set /p confirm=确认删除？ (y/n):
if /i not "%confirm%"=="y" goto menu

echo.
echo [%date% %time%] 正在清理...
docker compose -f "%COMPOSE_FILE%" down %CLEAN_VOLUMES% --remove-orphans
echo.
echo [%date% %time%] 清理完成
echo.
echo 如需重新部署，请运行: deploy.bat
pause
exit /b 0

:do_status
echo.
echo 服务状态：
docker compose -f "%COMPOSE_FILE%" ps
echo.
echo 端口监听：
netstat -ano | findstr ":3090 :8060 :8061 :3306 :6379" 2>nul
if errorlevel 1 echo   无端口占用
pause
exit /b 0
