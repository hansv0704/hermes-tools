@echo off
chcp 65001 >nul
title Hermes Windows Defender 排除設定

echo.
echo ╔══════════════════════════════════════════╗
echo ║  Hermes Defender 排除設定 v1.0         ║
echo ╚══════════════════════════════════════════╝
echo.
echo 此工具會將 Hermes 目錄加入 Windows Defender
echo 排除清單，避免更新時 Python 程序被誤判為
echo 惡意程式而觸發記憶體崩潰 (0xC0000005)。
echo.
echo [注意] 需要「系統管理員權限」
echo.

REM 檢查管理員權限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在要求管理員權限...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set "HERMES_HOME=%LOCALAPPDATA%\hermes"

echo [1/3] 加入資料夾排除...
powershell -Command "Add-MpPreference -ExclusionPath '%HERMES_HOME%'" 2>nul
if %errorlevel% equ 0 (
    echo       已排除: %HERMES_HOME%
) else (
    echo       [警告] 無法加入（可能已存在或權限不足）
)

echo [2/3] 加入程序排除...
powershell -Command "Add-MpPreference -ExclusionProcess 'Hermes.exe'" 2>nul
powershell -Command "Add-MpPreference -ExclusionProcess 'hermes.exe'" 2>nul
powershell -Command "Add-MpPreference -ExclusionProcess 'python.exe'" 2>nul
echo       已排除: Hermes.exe, hermes.exe, python.exe

echo [3/3] 確認目前排除清單...
echo.
powershell -Command "Get-MpPreference | Select-Object ExclusionPath, ExclusionProcess | Format-List"
echo.

echo ╔══════════════════════════════════════════╗
echo ║         設定完成！                      ║
echo ╚══════════════════════════════════════════╝
echo.
pause
