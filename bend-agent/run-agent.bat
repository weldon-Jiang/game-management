@echo off
chcp 65001 > nul
cd /d "%~dp0src"
python -X utf8 main.py %*
