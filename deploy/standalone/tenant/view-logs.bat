@echo off
chcp 65001 >nul
REM ================================================
REM 查看分控运行日志(一键用记事本打开 logs 目录)
REM ================================================
cd /d "%~dp0"
echo 正在打开日志目录: %~dp0logs
if not exist "%~dp0logs" (
    echo 日志目录不存在,可能服务尚未启动产生日志。
    mkdir "%~dp0logs" 2>nul
)
explorer "%~dp0logs"
