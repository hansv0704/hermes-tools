@echo off
chcp 65001 >nul
title 關閉 Game Studio
cd /d "%~dp0"
python run_game_studio.py --stop
pause
