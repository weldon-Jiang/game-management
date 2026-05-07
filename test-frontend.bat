@echo off
REM 前端快速测试脚本
REM 运行所有前端测试（单元、集成、E2E）

echo ========================================
echo   前端自动化测试开始
echo ========================================

cd bend-platform-web

echo.
echo [1/4] 运行 Lint 检查...
call npm run lint:check
if %errorlevel% neq 0 (
    echo ❌ Lint 检查失败！
    pause
    exit /b %errorlevel%
)

echo.
echo [2/4] 运行单元和集成测试...
call npm run test:coverage
if %errorlevel% neq 0 (
    echo ❌ 单元/集成测试失败！
    pause
    exit /b %errorlevel%
)

echo.
echo [3/4] 运行 E2E 测试...
echo (注：确保前端开发服务器正在运行)
echo.
pause
call npm run test:e2e
if %errorlevel% neq 0 (
    echo ❌ E2E 测试失败！
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================
echo   ✅ 前端所有测试通过！
echo ========================================
pause
