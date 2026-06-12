@echo off
title Alice AI Investment Agent v3

echo.
echo    ========================================
echo       Alice AI Investment Agent v3.0
echo    ========================================
echo.

cd /d "%~dp0apps\investment"

echo [*] Starting server on http://127.0.0.1:5002 ...
start "" http://127.0.0.1:5002
python server.py
