@echo off
chcp 65001 >nul
title Windows Defender 排除 Hermes
echo ============================================
echo   Windows Defender 排除 Hermes（需管理員）
echo ============================================
echo.

:: 檢查管理員權限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 請以「系統管理員身分執行」此腳本
    echo         右鍵 → 以系統管理員身分執行
    pause
    exit /b 1
)

echo [1/4] 排除 Hermes 本體目錄...
powershell -Command "Add-MpPreference -ExclusionPath '%LOCALAPPDATA%\hermes'" 2>nul
if %errorlevel% equ 0 (echo   ✓ 已排除: %LOCALAPPDATA%\hermes) else (echo   ⚠ 排除失敗（可能已存在）)

echo [2/4] 排除 Hermes.exe 桌面版...
powershell -Command "Add-MpPreference -ExclusionPath '%LOCALAPPDATA%\hermes\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe'" 2>nul
echo   ✓ 已處理

echo [3/4] 排除 Python.exe（venv）...
powershell -Command "Add-MpPreference -ExclusionProcess 'python.exe'" 2>nul
echo   ✓ 已處理

echo [4/4] 排除 hermes.exe（CLI）...
powershell -Command "Add-MpPreference -ExclusionProcess 'hermes.exe'" 2>nul
echo   ✓ 已處理

echo.
echo ============================================
echo   排除完成！請重新啟動 Hermes 桌面版
echo ============================================
pause
