@echo off
REM Bend Agent Build Script for Windows
REM This script packages the Agent using PyArmor and PyInstaller
REM Includes code obfuscation for commercial secret protection

echo ========================================
echo Bend Agent Build Script (Enhanced Security)
echo ========================================
echo.

REM Set environment
set PROJECT_ROOT=%~dp0..
set SOURCE_DIR=%PROJECT_ROOT%\src
set OUTPUT_DIR=%PROJECT_ROOT%\dist
set BUILD_DIR=%PROJECT_ROOT%\build
set AGENT_SRC=%SOURCE_DIR%\agent
set CONFIGS_DIR=%PROJECT_ROOT%\configs
set DISTRIBUTION_DIR=%PROJECT_ROOT%\distribution

REM Clean previous builds
echo [1/9] Cleaning previous builds...
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
mkdir "%OUTPUT_DIR%"
mkdir "%BUILD_DIR%"

REM Install dependencies
echo [2/9] Installing dependencies...
pip install pyarmor pyinstaller aiohttp websockets Pillow opencv-python numpy pystray pyautogui pydirectinput pywin32 inputs xlib PyYAML python-json-logger asyncio-throttle pycryptodome -q

REM Create build directory structure
echo [3/9] Creating build directory structure...
mkdir "%BUILD_DIR%\agent"
mkdir "%BUILD_DIR%\obfuscated"

REM Copy agent source files to build directory (excluding __pycache__ and tests)
echo [4/9] Copying agent source files (excluding __pycache__ and tests)...
robocopy "%AGENT_SRC%" "%BUILD_DIR%\agent" /E /XD "__pycache__" "tests" /NFL /NDL /NJH /NJS

REM Copy main.py
echo [5/9] Copying main.py...
copy /y "%SOURCE_DIR%\main.py" "%BUILD_DIR%\main.py"

REM Run PyArmor obfuscation with enhanced options
echo [6/9] Running PyArmor obfuscation (this may take a while)...
cd /d "%BUILD_DIR%"

REM Initialize PyArmor project for better protection
pyarmor init --src "%BUILD_DIR%" --output "%BUILD_DIR%\obfuscated" 2>nul

REM Generate obfuscated code (removed --protect to avoid entry point issues)
pyarmor gen ^
    --output "%BUILD_DIR%\obfuscated" ^
    --recursive ^
    main.py agent

if errorlevel 1 (
    echo.
    echo [WARNING] PyArmor obfuscation failed, attempting alternative method...
    REM Try alternative pyarmor command
    pyarmor gen --output "%BUILD_DIR%\obfuscated" main.py agent
    if errorlevel 1 (
        echo [ERROR] PyArmor obfuscation failed completely
        echo Will use un-obfuscated code (NOT RECOMMENDED FOR PRODUCTION)
        set OBFUSCATED_DIR=%BUILD_DIR%
    ) else (
        echo PyArmor obfuscation succeeded (alternative method)
        set OBFUSCATED_DIR=%BUILD_DIR%\obfuscated
    )
) else (
    echo PyArmor obfuscation succeeded
    set OBFUSCATED_DIR=%BUILD_DIR%\obfuscated
)

cd /d "%PROJECT_ROOT%"

REM Run PyInstaller with maximum protection
echo [7/9] Running PyInstaller...
REM Use --console instead of --windowed to see errors during testing
REM After testing passes, change to --windowed for production
pyinstaller --name "BendAgent" ^
    --onefile ^
    --console ^
    --add-data "%OBFUSCATED_DIR%\agent;agent" ^
    --hidden-import=asyncio ^
    --hidden-import=aiohttp ^
    --hidden-import=websockets ^
    --hidden-import=PIL ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=pystray ^
    --hidden-import=pyautogui ^
    --hidden-import=pydirectinput ^
    --hidden-import=win32api ^
    --hidden-import=win32gui ^
    --hidden-import=win32con ^
    --hidden-import=win32ui ^
    --hidden-import=inputs ^
    --hidden-import=yaml ^
    --hidden-import=cryptography ^
    --hidden-import=pycryptodome ^
    --hidden-import=pythonjsonlogger ^
    --hidden-import=pythonjsonlogger.jsonlogger ^
    --hidden-import=skimage ^
    --hidden-import=skimage.feature ^
    --hidden-import=skimage.transform ^
    --hidden-import=easyocr ^
    --hidden-import=asyncio_throttle ^
    --collect-all=pystray ^
    --noconfirm ^
    "%OBFUSCATED_DIR%\main.py"

REM Move output
echo.
echo [8/9] Moving output and copying distribution files...
if exist "%OUTPUT_DIR%\BendAgent.exe" (
    REM exe already in correct location, just copy additional files

    REM Copy config file
    if exist "%CONFIGS_DIR%\agent.yaml" (
        copy /y "%CONFIGS_DIR%\agent.yaml" "%OUTPUT_DIR%\"
        echo   - Copied agent.yaml
    )

    REM Copy README
    if exist "%DISTRIBUTION_DIR%\README.txt" (
        copy /y "%DISTRIBUTION_DIR%\README.txt" "%OUTPUT_DIR%\"
        echo   - Copied README.txt
    )

    REM Create templates directory (Agent will auto-create logs on first run)
    mkdir "%OUTPUT_DIR%\templates" 2>nul
    echo   - Created templates directory

    REM Create logs directory
    mkdir "%OUTPUT_DIR%\logs" 2>nul
    echo   - Created logs directory

    echo.
    echo ========================================
    echo Build completed successfully!
    echo ========================================
    echo.
    echo Output directory: %OUTPUT_DIR%
    echo Contents:
    dir /b "%OUTPUT_DIR%"
    echo.
    echo Ready for distribution!
    echo.
) else (
    echo.
    echo Build failed! Check errors above.
    exit /b 1
)

REM Cleanup
cd /d %PROJECT_ROOT%
rmdir /s /q "%BUILD_DIR%" 2>nul

echo Note: The obfuscated code includes runtime protection.
echo It is still possible to reverse-engineer, but significantly harder.
echo For maximum security, consider keeping core algorithms on the server side.
echo.
pause
