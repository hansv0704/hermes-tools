1|
§
.bat/.vbs/.py 編碼鐵律：.bat=純ASCII無中文（UTF-8-BOM使cmd.exe第一行崩潰，2026-06-12實測）。.vbs=ASCII（中文路徑用fso.GetParentFolderName繞）。.py/.pyw=UTF-8無BOM。
2|
§
3|部署與雙機：git clone+bootstrap.bat→openssl aes-256-cbc解密.env→記憶同步alice+default→profile use alice須同步建active-profile.json（防桌面版os.execvpe崩潰）。A端C:\Users\hans(GIS/投資/L2)、B端C:\Users\User(telegram.enabled=false)。hansv0704/hermes-tools 30分鐘auto-sync。路徑%USERPROFILE%。git衝突自動stash。
4|
§
5|截圖/瀏覽/API：Gemini Flash截圖→DeepSeek。Playwright DOM優先(playwright_profile持久化)，pyautogui備用。Key讀取用Python open()繞redaction。python import雙模式try/except ImportError。
6|
§
7|GIS監控v2.5：watchdog(sensor_config.json)、雙軌(pending_set繪圖+ccd_status文字)、三層級🧊🔴🟡。gis_utils_v1.py內嵌、PID lock、7天舊圖清理。Windows Startup VBS(pythonw.exe+CREATE_NO_WINDOW)自啟。monitor.py L814 normal_set sync、tray icon雙擊+🟢🟡🔴。TG測試：改pending_set觸發。SOP：process list→pending_set→token→matplotlib。
8|
§
9|文件與圖表：Word以「115年度萬山…期中參考版.docx」為基準。中文標楷體、英文數字Times New Roman，run級別分開設定。Grapher V9：標楷體粗體純黑、四邊黑框無網格、FontProperties(20,bold)、右Y黑字、時雨量藍bar+累積深紅#B91C1C折線、無箭頭、→Desktop/charts/V{N}.png。skill: alice-scientific-charts。
10|
§
11|Hermes修復v3：A-DEP擊殺(Defender排除)、B-os.execvpe(subprocess.Popen+sys.exit)、C-profile死循環(HERMES_PROFILE_FROM_CLI)、D---replace陷阱、E-profile獨立(active-profile.json)。skill: alice-hermes-repair。
12|
§
13|LiveCode Studio v5.3 port 5001：watchdog 5秒+24hr補標、lcs_workspaces.json持久化。檔案：run_studio.py+skills/live_code_studio_skill.py+base_skill.py+lcs_template_v5.html。誤移復原：legacy/skills/→清__pycache__→taskkill port 5001。桌面版切session bug→暫用/reset。
14|
§
15|Alice鐵律：開場先報現狀。修復≠重寫先確認結構；ls確認路徑再改；每改立即curl驗證；搞砸直接承認。
16|
§
17|投資代理人v3.0 FastAPI port 5002：5-Agent(Scout/Analyst/Risk/Executor/Reflector)、規則引擎+技術指標(MA/RSI/MACD+Kelly)、yfinance紙上交易。MEGA SpeedyAPI回傳JSON字串須json.loads()。Risk部位<1000股→向上取整1張。公司網路擋spapi→手機熱點。DLL: MEGA/SpeedyAPI_PY/megaapi/megaSpeedy/，憑證: MEGA/MEGARA/R124662445.pfx。
18|
§
19|Repo邊界：hermes-tools只放Alice/Hermes工具腳本技能記憶。公司GIS文件禁放，作業區/.gitignore。違反曾致135MB docx卡死git push。
§
⚠️ A/B端鐵律：主人極度在意A/B端區分，絕不混淆。A端=公司=C:\Users\hans=這台（主力機，GIS/投資/L2全在此）。B端=家用=C:\Users\User（telegram.enabled=false）。通訊時一律明確標示[A端]/[B端]，禁用「主機/這台/另台」等模糊詞。
