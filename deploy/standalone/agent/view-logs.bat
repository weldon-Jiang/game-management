@echo off
chcp 65001 >nul
REM ================================================
REM 查看 Agent 运行日志
REM ================================================
cd /d "%~dp0"
echo 正在打开日志目录: %~dp0logs
if not exist "%~dp0logs" mkdir "%~dp0logs" 2>nul
explorer "%~dp0logs"
