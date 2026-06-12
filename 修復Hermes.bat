@echo off
chcp 65001 >nul
title Hermes 一鍵修復
echo ============================================
echo   Hermes 一鍵深度修復
echo   解決 0xC0000005 桌面版崩潰
echo ============================================
echo.

set HERMES_DIR=%LOCALAPPDATA%\hermes
set REPO_DIR=%HERMES_DIR%\hermes-agent
set VENV_DIR=%REPO_DIR%\venv
set UV=%HERMES_DIR%\bin\uv.exe

echo [1/6] 清理殘留行程...
taskkill /f /im Hermes.exe 2>nul
taskkill /f /im hermes.exe 2>nul
timeout /t 2 /nobreak >nul
echo   ✓ 已清理

echo.
echo [2/6] 釋放 Port 9122...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :9122') do taskkill /f /pid %%a 2>nul
echo   ✓ 已處理

echo.
echo [3/6] 嘗試 CLI 更新（如果 CLI 還能用）...
if exist "%VENV_DIR%\Scripts\hermes.exe" (
    call "%VENV_DIR%\Scripts\hermes.exe" update --yes --gateway 2>nul
    if %errorlevel% equ 0 (
        echo   ✓ CLI 更新成功
        goto :rebuild_desktop
    )
)
echo   ⚠ CLI 更新失敗，進入深度修復...

echo.
echo [4/6] 深度修復：刪除損壞 venv...
if exist "%VENV_DIR%" (
    rmdir /s /q "%VENV_DIR%"
    echo   ✓ 已刪除 venv
)

echo.
echo [5/6] 重建 venv + 安裝依賴...
if not exist "%UV%" (
    echo [錯誤] uv.exe 不存在：%UV%
    echo         請重新安裝 Hermes
    pause
    exit /b 1
)

cd /d "%REPO_DIR%"
"%UV%" venv --python 3.11
if %errorlevel% neq 0 (
    echo [錯誤] uv venv 建立失敗
    pause
    exit /b 1
)

"%UV%" pip install pip setuptools wheel
"%UV%" pip install -e .
echo   ✓ venv 重建完成

echo.
echo [6/6] 執行 hermes update...
call "%VENV_DIR%\Scripts\hermes.exe" update --yes --gateway
echo   ✓ 更新完成

:rebuild_desktop
echo.
echo [額外] 重建桌面版...
call "%VENV_DIR%\Scripts\hermes.exe" desktop --build-only 2>nul
if %errorlevel% equ 0 (
    echo   ✓ 桌面版已重建
) else (
    echo   ⚠ 桌面版重建失敗（CLI 仍可用）
)

echo.
echo ============================================
echo   修復完成！
echo   請重新啟動 Hermes 桌面版
echo   若仍無法啟動，請先執行 Defender排除Hermes.bat
echo ============================================
pause
