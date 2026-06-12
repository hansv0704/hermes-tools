@echo off
chcp 65001 >nul
title Hermes 系統列
cd /d "%~dp0"
start "" "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\pythonw.exe" "%~dp0hermes_tray.pyw"
echo Hermes 系統列已啟動（右下角找綠色 H）
timeout /t 2 >nul
