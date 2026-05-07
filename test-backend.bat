@echo off
REM 后端快速测试脚本
REM 运行所有后端测试

echo ========================================
echo   后端自动化测试开始
echo ========================================

cd bend-platform

echo.
echo [1/2] 清理并编译...
call mvn clean compile
if %errorlevel% neq 0 (
    echo ❌ 编译失败！
    pause
    exit /b %errorlevel%
)

echo.
echo [2/2] 运行所有测试...
call mvn test
if %errorlevel% neq 0 (
    echo ❌ 后端测试失败！
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================
echo   ✅ 后端所有测试通过！
echo ========================================
pause
