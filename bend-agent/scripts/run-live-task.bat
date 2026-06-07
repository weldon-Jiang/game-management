@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
set PYTHONPATH=%CD%\src;%CD%
python -X utf8 scripts\run_live_task.py %*
