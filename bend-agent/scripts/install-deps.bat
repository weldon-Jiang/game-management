@echo off
REM Bend Agent dependency installer (includes WebRTC / cloud streaming deps)
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
echo [2/2] Verifying cloud streaming modules ...
set PYTHONPATH=%PROJECT_ROOT%\src
python -c "from agent.xbox.cloud_stream_session import AIORTC_AVAILABLE; import compress_pickle; import av; print('aiortc available:', AIORTC_AVAILABLE); print('av:', av.__version__)"
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
