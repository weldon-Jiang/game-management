@echo off
REM 全栈快速测试脚本
REM 同时运行前端和后端测试

echo ========================================
echo   全栈自动化测试开始
echo ========================================

echo.
echo 正在运行后端测试...
call test-backend.bat
if %errorlevel% neq 0 (
    echo ❌ 后端测试失败！
    pause
    exit /b %errorlevel%
)

echo.
echo 正在运行前端测试...
call test-frontend.bat
if %errorlevel% neq 0 (
    echo ❌ 前端测试失败！
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================
echo   ✅ 全栈所有测试通过！
echo ========================================
pause
