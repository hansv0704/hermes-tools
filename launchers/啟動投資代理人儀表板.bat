@echo off
chcp 65001 > nul
title Alice 投資代理人儀表板
echo 正在啟動後端伺服器 (Port 5002)...
echo.
echo 儀表板將在瀏覽器開啟，CMD 保持開啟即為伺服器運行中。
echo 關閉此視窗即可停止伺服器。
echo.
start http://localhost:5002/dashboard
python "%~dp0..\apps\ui_server.py"
pause
