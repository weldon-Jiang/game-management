@echo off
chcp 65001 >nul
REM ================================================
REM 打开分控平台(默认浏览器,用本机局域网IP,地址栏显示局域网地址)
REM 这样商户可直接把地址栏的地址复制给同局域网其他电脑访问。
REM ================================================

REM 取本机首个 IPv4 地址(排除回环)
set "IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
    if not defined IP set "IP=%%a"
)
if defined IP set "IP=%IP: =%"
if not defined IP set "IP=localhost"

echo 分控平台访问地址: http://%IP%:8090
echo 本机访问: http://localhost:8090
echo 同局域网其他电脑访问: http://%IP%:8090
echo.
echo 正在打开浏览器...

start "" "http://%IP%:8090"
