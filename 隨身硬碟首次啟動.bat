@echo off
:: ╔══════════════════════════════════════╗
:: ║   Alice 隨身硬碟首次啟動腳本       ║
:: ║   用於新電腦 / 新環境首次使用       ║
:: ╚══════════════════════════════════════╝
chcp 65001 >nul

title Alice 首次環境配置
color 0B

cd /d "%~dp0"

echo =================================================
echo    Alice 隨身硬碟首次啟動
echo    此腳本會自動安裝所有必要套件
echo =================================================
echo.

:: ── 檢查 Python ──
echo [1/5] 檢查 Python 環境...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 未找到 Python！
    echo    請先安裝 Python 3.11+，並勾選「Add Python to PATH」
    echo    下載: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do @set PYVER=%%v
echo ✅ Python %PYVER%

echo.

:: ── 升級 pip ──
echo [2/5] 升級 pip...
python -m pip install --upgrade pip --quiet
echo ✅ pip 升級完成

echo.

:: ── 檢查 Ollama（記憶系統依賴） ──
echo [3/5] 檢查 Ollama 記憶系統...
echo.

:: 3a. 檢查 ollama 本體是否已安裝
ollama --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ 未找到 Ollama！
    echo    Ollama 是 Alice 記憶系統的向量化引擎。
    echo    請從 https://ollama.com/download 下載並安裝。
    echo.
    set /p OLLAMA_CHOICE="是否已安裝完成，要繼續？(Y/N): "
    if /i not "%OLLAMA_CHOICE%"=="Y" (
        echo ❌ 使用者取消。請安裝 Ollama 後再試。
        pause
        exit /b 1
    )
    :: 再次檢查
    ollama --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ 仍未偵測到 Ollama，請確認安裝後重新執行。
        pause
        exit /b 1
    )
)
echo ✅ Ollama 已安裝

:: 3b. 檢查 Ollama 服務是否正常運作
echo    檢查 Ollama 服務狀態...
ollama list >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo    ⚠️ Ollama 服務未啟動或無法連線。
    echo    請手動啟動 Ollama 應用程式（開始選單 → Ollama）
    echo    等待狀態列圖示出現後，按任意鍵繼續...
    pause >nul
    
    :: 再次檢查
    ollama list >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo    ❌ 仍無法連線至 Ollama 服務。
        echo    請確認 Ollama 已正確安裝且正在運行。
        echo    若問題持續，請重新開機後再試。
        pause
        exit /b 1
    )
)
echo    ✅ Ollama 服務正常運作

:: 3c. 檢查 nomic-embed-text 模型（768 維向量嵌入）
echo    檢查 nomic-embed-text 模型...
ollama list 2>nul | findstr /C:"nomic-embed-text" >nul
if %ERRORLEVEL% NEQ 0 (
    echo    ⏳ 正在下載 nomic-embed-text 模型 (約 274MB)...
    echo    這可能需要幾分鐘，請耐心等候...
    echo.
    ollama pull nomic-embed-text
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ 模型下載失敗！請檢查網路連線後再試。
        echo    或手動執行: ollama pull nomic-embed-text
        pause
        exit /b 1
    )
    echo ✅ nomic-embed-text 模型下載完成
) else (
    echo ✅ nomic-embed-text 模型已就緒
)

echo.

:: ── 安裝依賴 ──
echo [4/5] 安裝依賴套件 (這可能需要幾分鐘)...
echo.
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 部分套件安裝失敗！
    echo    請確認網路連線正常後再試。
    echo    或手動執行: pip install -r requirements.txt
    pause
    exit /b 1
)
echo.
echo ✅ 所有依賴安裝完成

echo.

:: ── 完整環境檢查 ──
echo [5/5] 執行完整環境檢查...
python setup_check.py --no-install
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ 部分非關鍵項目未通過，但 Alice 仍可嘗試啟動。
)

echo.
echo =================================================
echo    環境配置完成！
echo    今後只需執行「啟動Alice.bat」即可。
echo =================================================
echo.
echo 正在啟動 Alice...
echo.
echo ╔══════════════════════════════════════╗
echo ║  按 Ctrl+C 可安全停止 Alice         ║
echo ║  停止後會自動回到此畫面              ║
echo ╚══════════════════════════════════════╝
echo.
python main.py
set ALICE_EXIT=%ERRORLEVEL%

echo.
echo =================================================
echo        Alice 已停止運作 (代碼: %ALICE_EXIT%)
echo =================================================
echo.
set /p DUMMY="按 Enter 鍵關閉此視窗..."
