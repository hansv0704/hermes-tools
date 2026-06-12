@echo off
chcp 65001 >nul
cd /d "%LOCALAPPDATA%\hermes\hermes-agent"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     Hermes 急救 v2.0                 ║
echo  ║     含殭屍行程清理                    ║
echo  ╚══════════════════════════════════════╝
echo.

echo  [1/6] 全清後端行程...
:: 檢查桌面版狀態
tasklist /fi "IMAGENAME eq Hermes.exe" 2>nul | findstr /C:"Hermes.exe" >nul
if %errorlevel% equ 0 (
    echo    ⚠ 桌面版還在執行，請正常關閉（右下角右鍵→離開）
    echo    只清後端行程，保留桌面版以免語言設定遺失
)
:: 只殺後端行程，不動桌面版 Hermes.exe
taskkill /f /im hermes.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
:: 等一下確保全部死透
timeout /t 2 /nobreak >nul
:: 確認沒有殘留
tasklist /fi "IMAGENAME eq python.exe" 2>nul | findstr /C:"python.exe" >nul
if %errorlevel% equ 0 (
    echo    ⚠ 仍有殘留，強制再殺...
    wmic process where "name='python.exe' or name='hermes.exe' or name='Hermes.exe'" delete >nul 2>&1
)
echo    ✓ 行程已全清

echo  [2/6] 檢查 os.execvpe 修復...
git log --oneline -10 2>nul | findstr /C:"os.execvpe" >nul
if %errorlevel% neq 0 (
    echo    ⚠ 修復遺失，正在 git am 還原...
    for %%f in ("%USERPROFILE%\Desktop\Hermes工具區\0001-fix-replace-os.execvpe*.patch") do git am "%%f" 2>nul
    if %errorlevel% neq 0 (
        git am --abort >nul 2>&1
        echo    ⚠ patch 套用失敗（可能已合併或衝突）
    ) else (
        echo    ✓ 修復已還原
    )
) else (
    echo    ✓ 修復存在
)

echo  [3/6] 檢查桌面版 profile 設定...
set "PROFILE_JSON=%APPDATA%\Hermes\active-profile.json"
if not exist "%PROFILE_JSON%" (
    mkdir "%APPDATA%\Hermes" >nul 2>&1
    echo {"profile":"alice"}> "%PROFILE_JSON%"
    echo    ✓ 已建立
) else (
    echo    ✓ 存在
)

echo  [4/6] 設定 git pull rebase...
git config pull.rebase true >nul 2>&1
echo    ✓ pull.rebase = true

echo  [5/6] 殭屍防範：確認 active-profile 機制正常...
:: 如果 HERMES_PROFILE_FROM_CLI 修復在，re-exec 不會觸發 → 不產生新殭屍
git log --oneline -10 2>nul | findstr /C:"os.execvpe" >nul
if %errorlevel% equ 0 (
    echo    ✓ 殭屍防範已啟用（不再產生新殭屍）
) else (
    echo    ⚠ 防範遺失，請執行 git am 還原修復
)

echo  [6/6] 啟動 Hermes 系統列小工具...
start "" "%USERPROFILE%\Desktop\Hermes工具區\hermes_tray.pyw"
echo    ✓ 系統列圖示已啟動（右下角綠色 H）

echo.
echo  ╔══════════════════════════════════════╗
echo  ║  急救完成                            ║
echo  ║                                      ║
echo  ║  Gateway 啟動中，等 5 秒開桌面版      ║
echo  ║  以後殭屍不再累積，有就雙擊這個       ║
echo  ╚══════════════════════════════════════╝
echo.
pause
