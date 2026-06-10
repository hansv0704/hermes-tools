@echo off
chcp 65001 >nul
title Hermes Alice 一鍵安裝
echo.
echo   ╔══════════════════════════════════════╗
echo   ║    Hermes Alice 一鍵完整安裝         ║
echo   ╚══════════════════════════════════════╝
echo.

:: === 檢查必要工具 ===
echo [1/6] 檢查必要工具...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未安裝 Python 3.11+
    echo    請先安裝：https://www.python.org/downloads/
    pause && exit /b 1
)

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未安裝 Git
    echo    請先安裝：https://git-scm.com/download/win
    pause && exit /b 1
)

where hermes >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未安裝 Hermes Agent
    echo.
    echo 正在安裝 Hermes Agent...
    powershell -Command "irm https://hermes-agent.nousresearch.com/install.ps1 | iex"
    echo.
    echo ✅ Hermes 安裝完成，請重新開啟終端機後再執行此腳本
    pause && exit /b 0
)

echo ✅ Python、Git、Hermes 已就緒
echo.

:: === 安裝 Python 依賴 ===
echo [2/6] 安裝 Python 依賴...
pip install watchdog matplotlib yfinance pandas python-dotenv requests 2>nul
echo ✅ 依賴已安裝
echo.

:: === 下載工具工作區 ===
echo [3/6] 下載工具工作區...
set WORKSPACE=%USERPROFILE%\Desktop\Hermes工具區
if exist "%WORKSPACE%" (
    echo 目錄已存在，正在更新...
    cd /d "%WORKSPACE%"
    git pull
) else (
    git clone https://github.com/hansv0704/hermes-tools.git "%WORKSPACE%"
    cd /d "%WORKSPACE%"
)
echo ✅ 工具區已就緒
echo.

:: === 設定 API Keys ===
echo [4/6] 設定 API Keys...
echo.
set /p DEEPSEEK_KEY="請貼上 DEEPSEEK_API_KEY (直接按 Enter 跳過): "
set /p TG_TOKEN=*** 請貼上 TELEGRAM_BOT_TOKEN (直接按 Enter 跳過): "

:: 建立 Hermes alice profile（如果不存在）
hermes profile list 2>nul | findstr "alice" >nul
if %errorlevel% neq 0 (
    hermes profile create alice --clone
)

:: 寫入 API keys
if not "%DEEPSEEK_KEY%"=="" (
    echo DEEPSEEK_API_KEY=%DEEPSEEK_KEY%>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
)
if not "%TG_TOKEN%"=="" (
    echo TELEGRAM_BOT_TOKEN=*** "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
    echo TELEGRAM_ALLOWED_USERS=8138000028>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
    echo TELEGRAM_HOME_CHANNEL=8138000028>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
)

:: 設定 Telegram config
hermes -p alice config set telegram.allowed_chats "8138000028" >nul 2>nul
hermes -p alice config set telegram.allowed_users "8138000028" >nul 2>nul
hermes -p alice config set telegram.home_channel "8138000028" >nul 2>nul

:: 設定 quick_commands
hermes -p alice config set quick_commands.studio.type exec >nul 2>nul
hermes -p alice config set "quick_commands.studio.command" "start python \"%WORKSPACE%\run_studio.py\"" >nul 2>nul
hermes -p alice config set quick_commands.invest.type exec >nul 2>nul
hermes -p alice config set "quick_commands.invest.command" "start \"\" \"%WORKSPACE%\啟動投資代理人儀表板.bat\"" >nul 2>nul
echo ✅ API Keys 已設定
echo.

:: === 複製技能 + 人格 ===
echo [5/6] 安裝技能與人格...
set SKILLS_DIR=%USERPROFILE%\AppData\Local\hermes\profiles\alice\skills\alice
xcopy /E /Y "%WORKSPACE%\hermes_skills\*" "%SKILLS_DIR%\" >nul 2>nul
copy /Y "%WORKSPACE%\hermes_skills\..\SOUL.md" "%USERPROFILE%\AppData\Local\hermes\SOUL.md" >nul 2>nul
echo ✅ 技能與人格已安裝
echo.

:: === 拉取記憶（如果 MEGA 有備份） ===
echo [6/6] 拉取雲端記憶...
set MEGA_MEMORY=%USERPROFILE%\Desktop\大崩儀器DATA回傳\MEGA備份\hermes_memory
if exist "%MEGA_MEMORY%\USER.md" (
    copy /Y "%MEGA_MEMORY%\USER.md" "%USERPROFILE%\AppData\Local\hermes\profiles\alice\memories\" >nul
    copy /Y "%MEGA_MEMORY%\MEMORY.md" "%USERPROFILE%\AppData\Local\hermes\profiles\alice\memories\" >nul
    echo ✅ 記憶已從雲端恢復
) else (
    echo ⚠️ 無雲端備份，使用全新記憶
)
echo.

:: === 完成 ===
echo.
echo   ╔══════════════════════════════════════╗
echo   ║         ✅ 安裝完成！               ║
echo   ╠══════════════════════════════════════╣
echo   ║                                    ║
echo   ║  啟動 Gateway：                    ║
echo   ║    hermes -p alice gateway run     ║
echo   ║                                    ║
echo   ║  啟動 GIS Watchdog：               ║
echo   ║    python "%WORKSPACE%\scripts\gis_watchdog.py" ║
echo   ║                                    ║
echo   ║  Telegram 指令：                   ║
echo   ║    /studio  /invest  /game  /n8n   ║
echo   ║                                    ║
echo   ╚══════════════════════════════════════╝
echo.
echo 按任意鍵啟動 Gateway...
pause >nul
start "Hermes Gateway" hermes -p alice gateway run
echo ✅ Gateway 已啟動
pause
