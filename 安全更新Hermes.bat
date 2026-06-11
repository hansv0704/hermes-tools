@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================
echo     安全更新工具 v1.0
echo     (CLI 直更新，避開桌面版 Bug)
echo ============================================
echo.

set "INSTALL_ROOT=%LOCALAPPDATA%\hermes\hermes-agent"
set "HERMES_CLI=%INSTALL_ROOT%\venv\Scripts\hermes.exe"

if not exist "%HERMES_CLI%" (
    echo [錯誤] 找不到 Hermes CLI，請先執行「一鍵修復Hermes.bat」
    pause
    exit /b 1
)

echo [注意事項]
echo   此工具直接透過 CLI 更新，不會觸發桌面版的
echo   Electron handoff 機制，可避免 Windows 記憶體
echo   保護誤殺更新程序（錯誤碼 0xC0000005）。
echo.
echo   建議：永遠使用此工具更新，不要點桌面版的
echo        「Update」按鈕。
echo.
echo ═══════════════════════════════════════════
echo.

cd /d "%INSTALL_ROOT%"

echo [1/3] 拉取最新代碼...
git pull
if %errorlevel% neq 0 (
    echo [錯誤] git pull 失敗，可能是網路問題或本地有未提交的修改
    echo        嘗試 git stash 後再試...
    git stash
    git pull
)
echo.

echo [2/3] 執行 Hermes CLI 更新...
echo   (這可能需要幾分鐘，請耐心等待)
echo.
"%HERMES_CLI%" update --yes --gateway
if %errorlevel% neq 0 (
    echo.
    echo [警告] CLI 更新回報錯誤，嘗試強制模式...
    "%HERMES_CLI%" update --yes --gateway --force
)
echo.

echo [3/3] 重建桌面版...
"%HERMES_CLI%" desktop --build-only
echo.

echo ============================================
echo          更新完成！
echo ============================================
echo.
echo 桌面版路徑: %INSTALL_ROOT%\apps\desktop\release\win-unpacked\Hermes.exe
echo.
pause
