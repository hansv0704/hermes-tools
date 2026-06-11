@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================
echo     一鍵修復工具 v1.0
echo ============================================
echo.

REM === 路徑設定 ===
set "HERMES_HOME=%LOCALAPPDATA%\hermes"
set "INSTALL_ROOT=%HERMES_HOME%\hermes-agent"
set "VENV_PATH=%INSTALL_ROOT%\venv"
set "HERMES_CLI=%VENV_PATH%\Scripts\hermes.exe"
set "DESKTOP_EXE=%INSTALL_ROOT%\apps\desktop\release\win-unpacked\Hermes.exe"
set "UV_EXE=%HERMES_HOME%\bin\uv.exe"

echo [1/6] 終止所有 Hermes 程序...
taskkill /F /IM Hermes.exe >nul 2>&1
taskkill /F /IM hermes.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo       已終止

echo [2/6] 釋放 Port 9122...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":9122"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo       已釋放

echo [3/6] 檢查 CLI 是否可用...
if exist "%HERMES_CLI%" (
    echo       CLI 存在，嘗試直接修復更新...
    cd /d "%INSTALL_ROOT%"
    "%HERMES_CLI%" update --yes --gateway --force
    if !errorlevel! equ 0 (
        echo       CLI 更新成功
        goto :launch
    )
    echo       CLI 更新失敗，切換為深度修復模式
)

echo [4/6] 深度修復：刪除損壞的 venv...
if exist "%VENV_PATH%" (
    rd /s /q "%VENV_PATH%" 2>nul
    timeout /t 1 /nobreak >nul
    if exist "%VENV_PATH%" (
        echo       [警告] venv 刪除失敗（可能被占用），嘗試強制解鎖...
        taskkill /F /IM python.exe >nul 2>&1
        timeout /t 2 /nobreak >nul
        rd /s /q "%VENV_PATH%" 2>nul
    )
    echo       venv 已清除
) else (
    echo       venv 不存在，跳過刪除
)

echo [5/6] 重建環境...
cd /d "%INSTALL_ROOT%"

REM 用 uv 重建 venv
if exist "%UV_EXE%" (
    echo       使用 uv 重建虛擬環境...
    "%UV_EXE%" venv --python 3.11 "%VENV_PATH%" 2>&1
    if exist "%VENV_PATH%\Scripts\python.exe" (
        echo       venv 重建成功
        
        REM 安裝 hermes-agent 本身
        echo       安裝 hermes-agent...
        "%VENV_PATH%\Scripts\python.exe" -m pip install -e "%INSTALL_ROOT%" --quiet 2>&1
        
        REM 執行一次完整更新確保最新
        if exist "%HERMES_CLI%" (
            echo       執行最終更新檢查...
            "%HERMES_CLI%" update --yes --gateway --force 2>&1
        )
    ) else (
        echo       [錯誤] venv 重建失敗
        goto :fail
    )
) else (
    echo       [錯誤] 找不到 uv.exe，請確認 Hermes 是否正確安裝
    goto :fail
)

:launch
echo [6/6] 啟動 Hermes 桌面版...
if exist "%DESKTOP_EXE%" (
    start "" "%DESKTOP_EXE%"
    echo       已啟動
) else (
    echo       [警告] 找不到桌面版，嘗試重建...
    if exist "%HERMES_CLI%" (
        "%HERMES_CLI%" desktop --build-only 2>&1
        if exist "%DESKTOP_EXE%" (
            start "" "%DESKTOP_EXE%"
            echo       重建完成並已啟動
        )
    )
)

echo.
echo ============================================
echo          修復完成！
echo ============================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================
echo   修復失敗，請檢查上方錯誤訊息
echo   或手動重新執行一鍵安裝.bat
echo ============================================
echo.
pause
exit /b 1
