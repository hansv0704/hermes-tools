@echo off
chcp 65001 >nul
title Hermes Alice 一鍵安裝
echo.
echo   +====================================+
echo   ^|    Hermes Alice 一鍵完整安裝         ^|
echo   +====================================+
echo.

:: === 檢查必要工具 ===
echo [1/5] 檢查必要工具...

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
echo [2/5] 安裝 Python 依賴...
pip install -r "%~dp0requirements.txt"
echo [OK] 依賴已安裝
echo.

:: === 建立 Hermes alice profile ===
hermes profile list 2>nul | findstr "alice" >nul
if %errorlevel% neq 0 (
    hermes profile create alice --clone
    echo [OK] Alice profile 已建立
) else (
    echo [OK] Alice profile 已存在
)

:: === 解密並安裝 API Keys ===
echo [3/5] 解密 API Keys...
set ALICE_ENV=%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env
call :find_openssl
if "%OPENSSL%"=="" (
    echo [X] 找不到 openssl（Git 安裝時應自帶）
    echo    請確認 Git 已安裝並重試
    pause && exit /b 1
)
"%OPENSSL%" enc -d -aes-256-cbc -pbkdf2 -pass pass:0704 -in "%~dp0.env.enc" -out "%ALICE_ENV%" 2>nul
if %errorlevel% neq 0 (
    echo [X] 解密失敗，請確認 .env.enc 檔案存在
    pause && exit /b 1
)
echo [OK] API Keys 已解密安裝
echo.

:: === 同步記憶 ===
echo [4/5] 同步記憶...
set MEM_DIR=%USERPROFILE%\AppData\Local\hermes\profiles\alice\memories
set DEF_MEM_DIR=%USERPROFILE%\AppData\Local\hermes\memories
mkdir "%MEM_DIR%" 2>nul
mkdir "%DEF_MEM_DIR%" 2>nul
copy /Y "%~dp0memory\USER.md" "%MEM_DIR%\USER.md" >nul
copy /Y "%~dp0memory\MEMORY.md" "%MEM_DIR%\MEMORY.md" >nul
copy /Y "%~dp0memory\USER.md" "%DEF_MEM_DIR%\USER.md" >nul
copy /Y "%~dp0memory\MEMORY.md" "%DEF_MEM_DIR%\MEMORY.md" >nul
echo [OK] 記憶已同步（alice + default）
echo.

:: === 安裝技能 ===
echo [5/5] 安裝技能...
set SKILLS_DIR=%USERPROFILE%\AppData\Local\hermes\profiles\alice\skills\alice
xcopy /E /Y "%~dp0hermes_skills\*" "%SKILLS_DIR%\" >nul 2>nul
echo [OK] 技能已安裝
echo.

:: === 設定 Telegram config ===
hermes -p alice config set telegram.allowed_chats "8138000028" >nul 2>nul
hermes -p alice config set telegram.allowed_users "8138000028" >nul 2>nul
hermes -p alice config set telegram.home_channel "8138000028" >nul 2>nul

:: === 完成 ===
echo.
echo   +===========================================+
echo   ^|            [OK] 安裝完成！                 ^|
echo   +===========================================+
echo   ^|                                           ^|
echo   ^|  啟動（務必加 -p alice）：                 ^|
echo   ^|    hermes -p alice                        ^|
echo   ^|    hermes -p alice gateway run            ^|
echo   ^|                                           ^|
echo   ^|  只用 hermes = default profile = 空的     ^|
echo   ^|                                           ^|
echo   +===========================================+
echo.
echo 按任意鍵啟動 Gateway...
pause >nul
start "Hermes Gateway" hermes -p alice gateway run
echo [OK] Gateway 已啟動
pause
exit /b 0

:: ====== 尋找 openssl ======
:find_openssl
set OPENSSL=
:: Git 自帶
if exist "C:\Program Files\Git\usr\bin\openssl.exe" set OPENSSL=C:\Program Files\Git\usr\bin\openssl.exe
if exist "C:\Program Files (x86)\Git\usr\bin\openssl.exe" set OPENSSL=C:\Program Files (x86)\Git\usr\bin\openssl.exe
:: 系統路徑
for %%i in (openssl.exe) do set OPENSSL=%%~$PATH:i
exit /b
