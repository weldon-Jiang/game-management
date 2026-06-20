@echo off
REM Bend Agent dependency installer
chcp 65001 > nul
setlocal

set PROJECT_ROOT=%~dp0..
echo ========================================
echo Bend Agent - Install Dependencies
echo ========================================
echo.

cd /d "%PROJECT_ROOT%"

echo [1/2] Installing from requirements.txt ...
pip install -r "%PROJECT_ROOT%\requirements.txt"
if errorlevel 1 (
    echo.
    echo PyPI default failed, retrying with Aliyun mirror ...
    pip install -r "%PROJECT_ROOT%\requirements.txt" -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    if errorlevel 1 (
        echo.
        echo [ERROR] Dependency installation failed.
        exit /b 1
    )
)

echo.
echo [2/2] Verifying core modules ...
set PYTHONPATH=%PROJECT_ROOT%\src
python -c "import pygame, compress_pickle, psutil; from agent.vision.ocr_engine import recognize_line; from agent.vision.profile_name_reader import gamertag_matches; from agent.xbox.lan_media_session import establish_lan_media_security; from agent.xbox.stream_recovery import reconnect_input_channel; print('pygame', pygame.ver); print('OCR/profile modules OK'); print('LAN stream modules OK')"
if errorlevel 1 (
    echo [ERROR] Module verification failed. Ensure PYTHONPATH includes src or run from bend-agent with:
    echo   set PYTHONPATH=src
    exit /b 1
)

echo.
echo ========================================
echo Dependencies installed successfully.
echo ========================================
endlocal
