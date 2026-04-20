@echo off
REM Bend Agent Build Script for Windows
REM This script packages the Agent using PyArmor and PyInstaller

echo ========================================
echo Bend Agent Build Script
echo ========================================
echo.

REM Set environment
set PROJECT_ROOT=%~dp0..
set SOURCE_DIR=%PROJECT_ROOT%\src
set OUTPUT_DIR=%PROJECT_ROOT%\dist
set BUILD_DIR=%PROJECT_ROOT%\build
set AGENT_SRC=%SOURCE_DIR%\agent

REM Clean previous builds
echo [1/7] Cleaning previous builds...
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%OUTPUT_DIR%"
mkdir "%BUILD_DIR%"

REM Install dependencies
echo [2/7] Installing dependencies...
pip install pyarmor aiohttp websockets Pillow opencv-python numpy pystray pyinstaller -q

REM Create build directory structure
echo [3/7] Creating build directory structure...
mkdir "%BUILD_DIR%\agent"

REM Copy agent source files
echo [4/7] Copying agent source files...
xcopy /s /e /i /y "%AGENT_SRC%" "%BUILD_DIR%\agent\"

REM Copy main.py
echo [5/7] Copying main.py...
copy /y "%SOURCE_DIR%\main.py" "%BUILD_DIR%\main.py"

REM Run PyArmor obfuscation
echo [6/7] Running PyArmor obfuscation...
cd /d "%BUILD_DIR%"
pyarmor gen -O "%BUILD_DIR%\obfuscated" --output "%BUILD_DIR%\obfuscated" main.py agent 2>nul
if errorlevel 1 (
    echo PyArmor obfuscation skipped or failed, using original code
    set OBFUSCATED_DIR=%BUILD_DIR%
) else (
    set OBFUSCATED_DIR=%BUILD_DIR%\obfuscated
)

REM Run PyInstaller
echo [7/7] Running PyInstaller...
pyinstaller --name "BendAgent" ^
    --onefile ^
    --windowed ^
    --add-data "%OBFUSCATED_DIR%;agent" ^
    --hidden-import=asyncio ^
    --hidden-import=aiohttp ^
    --hidden-import=websockets ^
    --hidden-import=PIL ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=pystray ^
    --collect-all=pystray ^
    --noconfirm ^
    "%OBFUSCATED_DIR%\main.py"

REM Move output
echo.
echo [Done] Moving output...
if exist "%BUILD_DIR%\dist\BendAgent.exe" (
    move /y "%BUILD_DIR%\dist\BendAgent.exe" "%OUTPUT_DIR%\"
    echo.
    echo ========================================
    echo Build completed successfully!
    echo Output: %OUTPUT_DIR%\BendAgent.exe
    echo ========================================
) else (
    echo.
    echo Build failed!
    exit /b 1
)

REM Cleanup
cd /d %PROJECT_ROOT%
rmdir /s /q "%BUILD_DIR%" 2>nul

echo.
pause