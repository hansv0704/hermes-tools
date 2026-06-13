1|1|§ .bat/.vbs/.py編碼鐵律：.bat=純ASCII無中文（UTF-8-BOM使cmd.exe第一行崩潰，2026-06-12實測）。.vbs=ASCII（中文路徑用fso.GetParentFolderName繞）。.py/.pyw=UTF-8無BOM。
2|2|§
3|3|§ 部署、雙機、A/B端與Repo邊界：git clone+bootstrap.bat→openssl aes-256-cbc解密.env→記憶同步alice+default→profile use alice須同步建active-profile.json（防桌面版os.execvpe崩潰）。A端=C:\Users\hans（GIS/投資/L2主力機）、B端=C:\Users\User（telegram.enabled=false）。hansv0704/hermes-tools 30分鐘auto-sync，路徑%USERPROFILE%，git衝突自動stash。⚠️鐵律：對話中必須明確標示[A端]/[B端]，禁用「主機/這台/另台」。Repo邊界：hermes-tools只放Alice/Hermes工具腳本技能記憶，公司GIS文件禁放，作業區/.gitignore。違反曾致135MB docx卡死git push。
4|4|§
5|5|§ 截圖/瀏覽/API：Gemini Flash截圖→DeepSeek分析。Playwright DOM優先(playwright_profile持久化)，pyautogui備用。Key讀取用Python open()繞redaction。python import雙模式try/except ImportError。
6|6|§
7|7|§ GIS監控與儀器查詢：GIS監控v2.5：watchdog(sensor_config.json)、雙軌(pending_set繪圖+ccd_status文字)、三層級🧊🔴🟡。gis_utils_v1.py內嵌、PID lock、7天舊圖清理。Windows Startup VBS(pythonw.exe+CREATE_NO_WINDOW)自啟。monitor.py L814 normal_set sync、tray icon雙擊+🟢🟡🔴。TG測試：改pending_set觸發。SOP：process list→pending_set→token→matplotlib。儀器查詢鐵律：問任何儀器監測問題直接走gis_utils_v1.py的fetch_history(site_id,st_id)+generate_professional_chart(st_id,data)產圖，勿自寫繪圖腳本。路徑：大崩儀器DATA回傳\監測圖表\YYYYMMDD\。腳本：skills/alice/alice-gis-monitor/scripts/gis_utils_v1.py。
8|8|§
9|9|§ 文件與圖表規範：Word以「115年度萬山…期中參考版.docx」為基準。中文標楷體、英文數字Times New Roman，run級別分開設定。Grapher V9：標楷體粗體純黑、四邊黑框無網格、FontProperties(20,bold)、右Y黑字、時雨量藍bar+累積深紅#B91C1C折線、無箭頭、→Desktop/charts/V{N}.png。skill: alice-scientific-charts。
10|10|§
11|11|§ Hermes修復v3：A-DEP擊殺(Defender排除)、B-os.execvpe(subprocess.Popen+sys.exit)、C-profile死循環(HERMES_PROFILE_FROM_CLI)、D---replace陷阱、E-profile獨立(active-profile.json)。skill: alice-hermes-repair。
12|12|§
13|13|§ LiveCode Studio v5.3 port 5001：watchdog 5秒+24hr補標、lcs_workspaces.json持久化。檔案：run_studio.py+skills/live_code_studio_skill.py+base_skill.py+lcs_template_v5.html。誤移復原：legacy/skills/→清__pycache__→taskkill port 5001。桌面版切session bug→暫用/reset。
14|14|§
15|15|§ Alice行為鐵律全集：①開場先報現狀。②修復≠重寫先確認結構。③ls確認路徑再改。④每改立即curl驗證。⑤搞砸直接承認。⑥極簡優先：能用既有工具不造輪子，能50行不寫200行。⑦精準下刀：改程式只動目標段落，不順手整理鄰近程式碼、不擅自重構、跟隨現有風格。⑧先說假設：動手前先講清楚假設，避免基於錯誤前提執行。
16|16|§
17|17|§ 投資代理人v3.0 FastAPI port 5002：5-Agent(Scout/Analyst/Risk/Executor/Reflector)、規則引擎+技術指標(MA/RSI/MACD+Kelly)、yfinance紙上交易。MEGA SpeedyAPI回傳JSON字串須json.loads()。Risk部位<1000股→向上取整1張。公司網路擋spapi→手機熱點。DLL: MEGA/SpeedyAPI_PY/megaapi/megaSpeedy/，憑證: MEGA/MEGARA/R124662445.pfx。
18|18|§
19|19|§ 每日開源推薦過濾：✅優先=GIS/地理空間、Python資料分析、AI agent框架、投資量化、LLM結構化輸出、自動化、遊戲開發。❌禁止=前端框架、手機App、區塊鏈/NFT、醫療AI（非GIS）、純基礎設施。主人對遊戲開發有興趣，已加入cron job優先領域清單。
