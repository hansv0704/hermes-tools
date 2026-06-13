@echo off
chcp 65001 >nul
title Alice AI Investment Agent v3

echo.
echo    ========================================
echo       Alice AI Investment Agent v3.0
echo    ========================================
echo.

:: 啟動 Hermes venv（若存在）
set VENV=%USERPROFILE%\AppData\Local\hermes\hermes-agent\venv\Scripts
if exist "%VENV%\activate.bat" (
    call "%VENV%\activate.bat"
    echo [*] Hermes venv activated
) else (
    echo [!] Hermes venv not found, using system Python
)

:: 從 apps 目錄以 module 方式啟動（避免相對 import 錯誤）
cd /d "%~dp0apps"

echo [*] Checking dependencies...
python -c "import aiosqlite, yfinance" 2>nul || (
    echo [!] Missing dependencies, installing...
    uv pip install aiosqlite yfinance 2>nul || python -m pip install aiosqlite yfinance
)

echo [*] Starting server on http://127.0.0.1:5002 ...
start "" http://127.0.0.1:5002
python -m investment.server

:: 若閃退，暫停看錯誤
pause
