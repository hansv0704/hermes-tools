@echo off
chcp 65001 >nul
title Hermes Alice 一鍵安裝
echo.
echo   +====================================+
echo   ^|    Hermes Alice 一鍵完整安裝         ^|
echo   +====================================+
echo.

:: === 檢查必要工具 ===
echo [1/6] 檢查必要工具...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] 未安裝 Python 3.11+
    echo    請先安裝：https://www.python.org/downloads/
    pause && exit /b 1
)

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] 未安裝 Git
    echo    請先安裝：https://git-scm.com/download/win
    pause && exit /b 1
)

where hermes >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] 未安裝 Hermes Agent
    echo.
    echo 正在安裝 Hermes Agent...
    powershell -Command "irm https://hermes-agent.nousresearch.com/install.ps1 | iex"
    echo.
    echo [OK] Hermes 安裝完成，請重新開啟終端機後再執行此腳本
    pause && exit /b 0
)

echo [OK] Python、Git、Hermes 已就緒
echo.

:: === 安裝 Python 依賴 ===
echo [2/6] 安裝 Python 依賴...
pip install -r "%~dp0requirements.txt"
echo [OK] 依賴已安裝
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
echo [OK] 工具區已就緒
echo.

:: === 設定 API Keys ===
echo [4/6] 設定 API Keys...
echo.
set /p DEEPSEEK_KEY="請貼上 DEEPSEEK_API_KEY (直接按 Enter 跳過): "
set /p TG_TOKEN="請貼上 TELEGRAM_BOT_TOKEN (直接按 Enter 跳過): "

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
    echo TELEGRAM_BOT_TOKEN=%TG_TOKEN%>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
    echo TELEGRAM_ALLOWED_USERS=8138000028>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
    echo TELEGRAM_HOME_CHANNEL=8138000028>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
)

:: 寫入 MEGA 同步路徑（動態，不寫死使用者名稱）
echo MEGA_SYNC_DIR=%%USERPROFILE%%\Desktop\大崩儀器DATA回傳\MEGA備份\hermes_memory>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"

:: 設定 Telegram config
hermes -p alice config set telegram.allowed_chats "8138000028" >nul 2>nul
hermes -p alice config set telegram.allowed_users "8138000028" >nul 2>nul
hermes -p alice config set telegram.home_channel "8138000028" >nul 2>nul

:: 設定 quick_commands（使用動態 WORKSPACE 變數）
hermes -p alice config set quick_commands.studio.type exec >nul 2>nul
hermes -p alice config set "quick_commands.studio.command" "set WORKSPACE=%%USERPROFILE%%\Desktop\Hermes工具區 && start python \"%%WORKSPACE%%\run_studio.py\"" >nul 2>nul
hermes -p alice config set quick_commands.invest.type exec >nul 2>nul
hermes -p alice config set "quick_commands.invest.command" "set WORKSPACE=%%USERPROFILE%%\Desktop\Hermes工具區 && start \"\" \"%%WORKSPACE%%\啟動投資代理人儀表板.bat\"" >nul 2>nul
hermes -p alice config set quick_commands.game.type exec >nul 2>nul
hermes -p alice config set "quick_commands.game.command" "set WORKSPACE=%%USERPROFILE%%\Desktop\Hermes工具區 && start python \"%%WORKSPACE%%\run_game_studio.py\"" >nul 2>nul
hermes -p alice config set quick_commands.n8n.type exec >nul 2>nul
hermes -p alice config set "quick_commands.n8n.command" "set WORKSPACE=%%USERPROFILE%%\Desktop\Hermes工具區 && start \"\" \"%%WORKSPACE%%\啟動 N8N 伺服器.bat\"" >nul 2>nul
echo [OK] API Keys 已設定
echo.

:: === 複製技能 ===
echo [5/6] 安裝技能...
set SKILLS_DIR=%USERPROFILE%\AppData\Local\hermes\profiles\alice\skills\alice
xcopy /E /Y "%WORKSPACE%\hermes_skills\*" "%SKILLS_DIR%\" >nul 2>nul

:: 複製 sync_memory.py 到 alice scripts（給 cron 用）
set ALICE_SCRIPTS=%USERPROFILE%\AppData\Local\hermes\profiles\alice\scripts
mkdir "%ALICE_SCRIPTS%" 2>nul
copy /Y "%WORKSPACE%\scripts\sync_memory.py" "%ALICE_SCRIPTS%\sync_memory.py" >nul 2>nul

echo [OK] 技能已安裝
echo.

:: === 同步記憶（從雲端拉取） ===
echo [6/6] 同步記憶...
:: 先從 MEGA 備份拉取
set MEGA_MEMORY=%USERPROFILE%\Desktop\大崩儀器DATA回傳\MEGA備份\hermes_memory
if exist "%MEGA_MEMORY%\USER.md" (
    copy /Y "%MEGA_MEMORY%\USER.md" "%USERPROFILE%\AppData\Local\hermes\profiles\alice\memories\" >nul
    copy /Y "%MEGA_MEMORY%\MEMORY.md" "%USERPROFILE%\AppData\Local\hermes\profiles\alice\memories\" >nul
    echo [OK] 記憶已從 MEGA 恢復到 alice profile
) else (
    echo [!] MEGA 無備份，將在下一步自動同步
)

:: 同步到 default profile（防止用 hermes 不加 -p alice）
mkdir "%USERPROFILE%\AppData\Local\hermes\memories" 2>nul
copy /Y "%USERPROFILE%\AppData\Local\hermes\profiles\alice\memories\USER.md" "%USERPROFILE%\AppData\Local\hermes\memories\USER.md" >nul 2>nul
copy /Y "%USERPROFILE%\AppData\Local\hermes\profiles\alice\memories\MEMORY.md" "%USERPROFILE%\AppData\Local\hermes\memories\MEMORY.md" >nul 2>nul
echo [OK] 記憶已同步到 default profile
echo.

:: === 設定自動同步 cron ===
echo [7/7] 設定自動同步排程...
hermes -p alice cron create "every 30m" --script "scripts/sync_memory.py" --no_agent --deliver local --name "記憶雲端同步" >nul 2>nul
echo [OK] 每30分鐘自動同步記憶
echo.

:: === 完成 ===
echo.
echo   +===========================================+
echo   ^|            [OK] 安裝完成！                 ^|
echo   +===========================================+
echo   ^|                                           ^|
echo   ^|  重要：請務必使用以下指令啟動：            ^|
echo   ^|    hermes -p alice                        ^|
echo   ^|    hermes -p alice gateway run            ^|
echo   ^|                                           ^|
echo   ^|  如果只用 hermes（不加 -p alice）          ^|
echo   ^|  會使用 default profile，沒有技能和記憶    ^|
echo   ^|                                           ^|
echo   ^|  Telegram 指令：                          ^|
echo   ^|    /studio  /invest  /game  /n8n          ^|
echo   ^|                                           ^|
echo   ^|  記憶每30分鐘自動雙向同步到 MEGA           ^|
echo   ^|                                           ^|
echo   +===========================================+
echo.
echo 按任意鍵啟動 Gateway...
pause >nul
start "Hermes Gateway" hermes -p alice gateway run
echo [OK] Gateway 已啟動
pause
