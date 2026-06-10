@echo off
cd /d "%USERPROFILE%\Desktop"
if exist "Hermes工具區" (
    echo [OK] Already exists, updating...
    cd Hermes工具區
    git pull
) else (
    echo [>] Cloning from GitHub...
    git clone https://github.com/hansv0704/hermes-tools.git Hermes工具區
    cd Hermes工具區
)
echo [>] Starting setup...
call 一鍵安裝.bat
