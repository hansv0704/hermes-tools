@echo off
chcp 65001 >nul
title Alice Game Studio
echo ========================================
echo    Alice Game Studio v1.5
echo ========================================
echo.
echo [檢查] 正在檢查 port 5003 是否已被佔用...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5003 ^| findstr LISTENING') do (
    echo [清理] 發現舊進程 PID %%a，正在終止...
    taskkill /f /pid %%a 2>nul
    timeout /t 1 /nobreak >nul
    echo [清理] 舊進程已終止
)
echo [啟動] 正在啟動 Game Studio...
cd /d "%~dp0"
python run_game_studio.py
pause
