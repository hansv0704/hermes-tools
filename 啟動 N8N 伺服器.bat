@echo off
chcp 65001 >nul
title Alice N8N 伺服器控制台

:: ==============================================
::  Alice N8N Server Launcher v1.1
::  完全對標 Live Code Studio 獨立伺服器模式
::  Port: 5678 | Web UI: http://localhost:5678
:: ==============================================

echo.
echo    +=====================================+
echo    ^|     🐙 Alice N8N 伺服器控制台        ^|
echo    ^|     Port 5678 ^| npx n8n start       ^|
echo    +=====================================+
echo.

:: ----- 1. 檢查 Node.js -----
echo 🔍 [1/4] 檢查 Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未偵測到 Node.js！
    echo.
    echo 請先安裝 Node.js：https://nodejs.org/
    echo （建議安裝 LTS 版本）
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do set NODE_VER=%%i
echo ✅ Node.js 已安裝：%NODE_VER%

:: ----- 2. 檢查 npx -----
echo 🔍 [2/4] 檢查 npx...
where npx >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未偵測到 npx！（Node.js 可能版本過舊）
    echo.
    pause
    exit /b 1
)
echo ✅ npx 可用

:: ----- 3. 檢查 Port 5678 -----
echo 🔍 [3/4] 檢查 Port 5678...
netstat -ano | findstr ":5678.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  Port 5678 已被佔用
    echo.
    echo n8n 可能已在運行中 → http://localhost:5678
    echo 若要重啟，請先手動關閉佔用進程或透過 Alice 執行 stop_n8n_server
    echo.
    start http://localhost:5678
    pause
    exit /b 0
)
echo ✅ Port 5678 空閒

:: ----- 4. 啟動 n8n -----
echo 🚀 [4/4] 正在啟動 n8n 伺服器...
echo.
echo    首次啟動需下載 n8n 依賴（約 200MB），請耐心等候...
echo    後續啟動約需 5-10 秒
echo.
echo 📊 編輯器將在啟動完成後自動開啟
echo 🌐 網址：http://localhost:5678
echo.
echo ==============================================
echo  按 Ctrl+C 可停止伺服器
echo ==============================================
echo.

:: 設定環境變數
set N8N_PORT=5678
set N8N_HOST=localhost
set N8N_PROTOCOL=http
set N8N_DIAGNOSTICS_ENABLED=false
set N8N_VERSION_NOTIFICATIONS_ENABLED=false
set N8N_SECURE_COOKIE=false

:: 建立資料目錄（若不存在）
if not exist ".n8n" mkdir ".n8n"
set N8N_USER_FOLDER=%CD%\.n8n

:: 等待 n8n 開始監聽後開啟瀏覽器
start "" cmd /c "timeout /t 8 /nobreak >nul && start http://localhost:5678"

:: 啟動 n8n
npx -y n8n start

:: ----- 結束 -----
echo.
echo 🛑 n8n 伺服器已停止
pause
