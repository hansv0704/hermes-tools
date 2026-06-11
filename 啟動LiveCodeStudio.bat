@echo off
title Live Code Studio v5.0
cd /d "C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953"

echo.
echo ╔════════════════════════════════════════╗
echo ║   Live Code Studio v5.0               ║
echo ║   Hermes 協作面板                      ║
echo ╚════════════════════════════════════════╝
echo.

REM 檢查是否已在運行
python -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',5001)); s.close(); exit(r)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ LCS v5.0 已在運行中！
    echo 🌐 http://localhost:5001
    echo.
    start http://localhost:5001
    pause
    exit /b 0
)

echo 🚀 正在背景啟動 LCS v5.0...
echo.

REM 使用 pythonw 背景啟動（無 CMD 視窗）
REM 若 pythonw 不可用，fallback 到 start /min python
where pythonw >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" pythonw run_studio.py --daemon
) else (
    start "" /min python run_studio.py
)

REM 等待啟動完成
timeout /t 3 /nobreak >nul

REM 驗證
python -c "import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('127.0.0.1',5001)); s.close(); exit(0 if r==0 else 1)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ 啟動成功！
    echo 🌐 http://localhost:5001
    start http://localhost:5001
) else (
    echo ❌ 啟動失敗，請檢查 run_studio.py
)

echo.
echo 💡 此視窗可安全關閉，LCS 在背景運行中
echo 💡 關閉 LCS 請執行「關閉LiveCodeStudio.bat」
pause
