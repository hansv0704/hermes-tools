@echo off
chcp 65001 >nul
title Hermes 安全更新（避開桌面版 bug）

echo ============================================
echo   Hermes 安全更新（治本方案）
echo   避開桌面版 Update 按鈕的 0xC0000005 bug
echo ============================================
echo.

echo  ⚠ 請先正常關閉桌面版（右下角右鍵 → 離開）
echo.
tasklist /fi "IMAGENAME eq Hermes.exe" 2>nul | findstr /C:"Hermes.exe" >nul
if %errorlevel% equ 0 (
    echo  ⛔ 桌面版還在執行中，請先正常關閉再繼續
    echo     右下角 Hermes 圖示 → 右鍵 → 離開
    echo.
    pause
    exit /b 1
)
echo  ✓ 桌面版已關閉，開始更新...
echo.

set "HERMES_DIR=%LOCALAPPDATA%\hermes"
set "REPO_DIR=%LOCALAPPDATA%\hermes\hermes-agent"

echo [1/4] git pull 更新原始碼...
cd /d "%REPO_DIR%"

rem 確保 git 有基本設定（不然 stash 會失敗）
git config user.email "hermes@local" >nul 2>&1
git config user.name "hermes" >nul 2>&1

rem 丟掉 npm install 產生的髒檔案（package-lock.json 等）
git checkout -- package-lock.json >nul 2>&1
git checkout -- web/package-lock.json >nul 2>&1

rem git pull --rebase（修復會保持在頂端）
git pull --rebase
if %errorlevel% neq 0 (
    echo [錯誤] git pull 失敗，嘗試強制重置...
    git reset --hard HEAD >nul 2>&1
    git pull --rebase
    if %errorlevel% neq 0 (
        echo [嚴重] git pull 仍然失敗，請手動處理
        pause
        exit /b 1
    )
)

echo [2/4] hermes update（安裝依賴 + 重啟 gateway）...
call "%HERMES_DIR%\hermes-agent\venv\Scripts\hermes.exe" update --yes
if %errorlevel% neq 0 (
    echo [警告] hermes update 回報錯誤，但通常不影響使用
)

echo [3/4] 確認 os.execvpe 修復還在...
git log --oneline -10 2>nul | findstr /C:"os.execvpe" >nul
if %errorlevel% neq 0 (
    echo [警告] 修復遺失，正在 git am 還原...
    for %%f in ("%USERPROFILE%\Desktop\Hermes工具區\0001-fix-replace-os.execvpe*.patch") do (
        git am "%%f" 2>nul
        if %errorlevel% neq 0 (
            echo [警告] patch 套用失敗（可能已合併）
            git am --abort >nul 2>&1
        ) else (
            echo    ✓ 修復已還原
        )
    )
) else (
    echo    ✓ 修復存在
)

echo [4/4] 設定 git pull.rebase 策略...
git config pull.rebase true
echo    ✓ 已設定

echo.
echo ============================================
echo   安全更新完成！
echo.
echo   下一步：雙擊 Hermes急救.bat 啟動
echo ============================================
pause
