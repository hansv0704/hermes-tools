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
echo.
set ALICE_ENV=%USERPROFILE%\AppData\Local\hermes\profiles\alice\.env
call :find_openssl
if "%OPENSSL%"=="" (
    echo [X] 找不到 openssl（Git 安裝時應自帶）
    echo    請確認 Git 已安裝並重試
    pause && exit /b 1
)
:decrypt_retry
set /p PASSWORD="請輸入解密密碼: "
"%OPENSSL%" enc -d -aes-256-cbc -pbkdf2 -pass pass:%PASSWORD% -in "%~dp0.env.enc" -out "%ALICE_ENV%" 2>nul
if %errorlevel% neq 0 (
    echo [X] 解密失敗，密碼錯誤或檔案損毀
    echo.
    goto decrypt_retry
)
echo [OK] API Keys 已解密安裝
echo.
:: 追加工作區路徑到 .env（sync 腳本需要）
echo HERMES_WORKSPACE=%%USERPROFILE%%\Desktop\Hermes工具區>> "%ALICE_ENV%"

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

:: === 設定自動同步 ===
echo [6/6] 設定自動同步...
:: 複製同步腳本
set ALICE_SCRIPTS=%USERPROFILE%\AppData\Local\hermes\profiles\alice\scripts
mkdir "%ALICE_SCRIPTS%" 2>nul
copy /Y "%~dp0scripts\sync_memory_github.py" "%ALICE_SCRIPTS%\sync_memory_github.py" >nul 2>nul
:: 初次同步（push 本地記憶到 GitHub）
python "%~dp0scripts\sync_memory_github.py" push
echo [OK] 記憶已同步到 GitHub
echo.

:: === 設定預設 profile ===
hermes profile use alice >nul 2>nul
echo [OK] 已設 Alice 為預設 profile
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
echo   ^|  直接打開桌面版 Hermes 即可                 ^|
echo   ^|  已自動設為 Alice profile                  ^|
echo   ^|                                           ^|
echo   ^|  打開後第一句話：                           ^|
echo   ^|  「幫我建立記憶同步 cron」                  ^|
echo   ^|  我會自動幫你設定完成                       ^|
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
