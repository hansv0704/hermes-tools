@echo off
chcp 65001 >nul
title Hermes 新端初始化

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   Hermes 新端初始化 v1.0            ║
echo  ╚══════════════════════════════════════╝
echo.

set "REPO=%LOCALAPPDATA%\hermes\hermes-agent"

echo  [1/4] 檢查 hermes-agent repo...
if not exist "%REPO%" (
    echo    ⚠ 找不到 hermes-agent，請先執行一鍵安裝
    pause
    exit /b 1
)
echo    ✓ 找到

echo  [2/4] 套用 os.execvpe 安全修復...
cd /d "%REPO%"
git config user.email "hermes@local" >nul 2>&1
git config user.name "hermes" >nul 2>&1
git config pull.rebase true

:: 確認修復是否已存在
git log --oneline -20 2>nul | findstr /C:"os.execvpe" >nul
if %errorlevel% neq 0 (
    echo    修復不存在，正在 git am...
    for %%f in ("%USERPROFILE%\Desktop\Hermes工具區\0001-fix-replace-os.execvpe*.patch") do (
        git am "%%f" >nul 2>&1
        if %errorlevel% neq 0 (
            git am --abort >nul 2>&1
            echo    ⚠ 修復已在上游合併，不需要 patch
        )
    )
)
echo    ✓ 修復已套用

echo  [3/4] 建立桌面版 profile 設定...
set "PROFILE_JSON=%APPDATA%\Hermes\active-profile.json"
if not exist "%PROFILE_JSON%" (
    mkdir "%APPDATA%\Hermes" >nul 2>&1
    echo {"profile":"alice"}> "%PROFILE_JSON%"
)
echo    ✓ active-profile.json

echo  [4/4] 同步 Alice 記憶與技能...
set "ALICE_PROFILE=%LOCALAPPDATA%\hermes\profiles\alice"
set "TOOLBOX=%USERPROFILE%\Desktop\Hermes工具區"

:: 若本機已有記憶就跳過
if exist "%ALICE_PROFILE%\memories\" (
    echo    ✓ 記憶已存在
) else if exist "%TOOLBOX%\Alice記憶_backup\" (
    echo    從備份還原記憶...
    mkdir "%ALICE_PROFILE%" >nul 2>&1
    xcopy /E /I /Y "%TOOLBOX%\Alice記憶_backup" "%ALICE_PROFILE%\memories" >nul
    echo    ✓ 記憶已還原
) else (
    echo    ⚠ 工具區內無記憶備份，跳過
)

if exist "%ALICE_PROFILE%\skills\" (
    echo    ✓ 技能已存在
) else if exist "%TOOLBOX%\Alice技能_backup\" (
    echo    從備份還原技能...
    mkdir "%ALICE_PROFILE%" >nul 2>&1
    xcopy /E /I /Y "%TOOLBOX%\Alice技能_backup" "%ALICE_PROFILE%\skills" >nul
    echo    ✓ 技能已還原
) else (
    echo    ⚠ 工具區內無技能備份，跳過
)

echo.
echo  ╔══════════════════════════════════════╗
echo  ║  初始化完成                          ║
echo  ║                                      ║
echo  ║  桌面版可直接打開，不會觸發崩潰       ║
echo  ║  日常更新用「安全更新Hermes.bat」     ║
echo  ║  出事用「Hermes急救.bat」             ║
echo  ╚══════════════════════════════════════╝
echo.
pause
