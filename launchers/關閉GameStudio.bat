@echo off
chcp 65001 >nul
title 關閉 Game Studio
cd /d "%~dp0.."
python "%~dp0..\apps\run_game_studio.py" --stop
pause
