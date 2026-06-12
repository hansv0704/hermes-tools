@echo off
REM Gateway watchdog — 每 5 分鐘檢查一次，掛掉就重啟
REM 由 Windows Task Scheduler 觸發 (Hermes_Gateway_Watchdog)

set HERMES=C:\Users\User\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe
set LOGFILE=%LOCALAPPDATA%\hermes\profiles\alice\logs\gateway_watchdog.log
set LOGDIR=%LOCALAPPDATA%\hermes\profiles\alice\logs

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM 檢查 gateway 是否活著
"%HERMES%" -p alice gateway status 2>&1 | findstr /C:"running" >nul
if %ERRORLEVEL% EQU 0 (
    REM 活著，安靜退出
    exit /b 0
)

REM 掛了 → 記錄並重啟
echo [%DATE% %TIME%] Gateway 掛了，重新啟動... >> "%LOGFILE%"
"%HERMES%" -p alice gateway run >> "%LOGFILE%" 2>&1
echo [%DATE% %TIME%] Gateway 已重新啟動 >> "%LOGFILE%"
