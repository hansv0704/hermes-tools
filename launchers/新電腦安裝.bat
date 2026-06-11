@echo off
chcp 65001 >nul
title Hermes Alice 新電腦安裝
echo ========================================
echo   Hermes Alice 多電腦同步安裝
echo ========================================
echo.

REM === 1. 檢查必要工具 ===
echo [1/4] 檢查必要工具...
where python >nul 2>&1 || (echo ❌ 未安裝 Python && pause && exit /b 1)
where git >nul 2>&1 || (echo ❌ 未安裝 Git && pause && exit /b 1)
where hermes >nul 2>&1 || (echo ❌ 未安裝 Hermes Agent && echo 請先安裝: https://hermes-agent.nousresearch.com && pause && exit /b 1)
echo ✅ 工具齊全
echo.

REM === 2. Clone 工具工作區 ===
echo [2/4] 下載工具工作區...
set WORKSPACE_DIR=%USERPROFILE%\Desktop\Hermes工具區
if exist "%WORKSPACE_DIR%" (
    echo ⚠️ 目錄已存在，正在更新...
    cd /d "%WORKSPACE_DIR%"
    git pull
) else (
    echo 請先將此 repo 上傳到 GitHub，然後修改下方的 REPO_URL
    echo.
    echo 手動執行：
    echo   git clone YOUR_REPO_URL "%WORKSPACE_DIR%"
    echo.
)
echo.

REM === 3. 安裝 Python 依賴 ===
echo [3/4] 安裝 Python 套件...
cd /d "%WORKSPACE_DIR%"
pip install -r requirements.txt 2>nul
pip install watchdog matplotlib yfinance pandas python-dotenv 2>nul
echo ✅ 依賴已安裝
echo.

REM === 4. 設定 Hermes ===
echo [4/4] 設定 Hermes Alice profile...
echo.

REM 設定 API Key（從舊電腦複製）
echo 請貼上你的 DEEPSEEK_API_KEY：
set /p DEEPSEEK_KEY="> "
if not "%DEEPSEEK_KEY%"=="" (
    hermes -p alice config set model.api_key "%DEEPSEEK_KEY%"
)

echo 請貼上你的 TELEGRAM_BOT_TOKEN：
set /p TG_TOKEN="> "
if not "%TG_TOKEN%"=="" (
    echo TELEGRAM_BOT_TOKEN=%TG_TOKEN%>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
    echo TELEGRAM_ALLOWED_USERS=8138000028>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
    echo TELEGRAM_HOME_CHANNEL=8138000028>> "%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env"
)

REM 複製技能
echo 複製 Hermes 技能...
xcopy /E /Y "%WORKSPACE_DIR%\hermes_skills\*" "%USERPROFILE%\AppData\Local\hermes\profiles\alice\skills\alice\" >nul
echo ✅ 技能已安裝

REM 複製 SOUL.md 人格
copy /Y "%WORKSPACE_DIR%\hermes_skills\..\SOUL.md" "%USERPROFILE%\AppData\Local\hermes\SOUL.md" >nul 2>nul

echo.
echo ========================================
echo   ✅ 安裝完成！
echo.
echo   啟動 Gateway：
echo     hermes -p alice gateway run
echo.
echo   啟動 GIS Watchdog：
echo     python "%WORKSPACE_DIR%\scripts\gis_watchdog.py"
echo.
echo ========================================
pause
