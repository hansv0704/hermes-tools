@echo off
chcp 65001 >nul
cd /d "%~dp0"
git stash push -m "auto-sync-stash" >nul 2>&1
git pull --rebase >nul 2>&1
if %errorlevel% neq 0 (
    git checkout -- . >nul 2>&1
    git pull --rebase >nul 2>&1
)
git stash pop >nul 2>&1
