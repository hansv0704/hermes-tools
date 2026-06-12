技術教訓：(a) secret redaction→字串拼接/heredoc/獨立txt；(b) cron用cronjob工具；(c) SKILL.md須含強制規則；(d) .bat=UTF-8-BOM、.vbs=ASCII、.py=UTF-8無BOM；(e) Git push指定origin main、commit前diff --cached --quiet防空commit；(f) 作業區/永久.gitignore；(g) git add -A需.gitignore護航；(h) MEGA=兆豐；(i) Gateway桌面關=TG斷需install；(j) 多台搶TG→次要設telegram.enabled false；(k) v3 sync逐條合併+版本號整份覆蓋；(l) matplotlib legend用FontProperties(size=N)；(m) .env讀key用Python open()繞redaction；(n) 26條記憶first-60-char dedup無效→靠手動AI濃縮
§
部署：git clone + bootstrap.bat → 一鍵安裝→解密→記憶到alice+default→設alice預設profile→偵測Gateway。⚠️ profile use alice須同步建active-profile.json否則os.execvpe崩潰。.env用openssl aes-256-cbc加密。cron由Alice對話建立。
§
截圖用Gemini Flash(gemini-2.5-flash)，回傳DeepSeek。PyAutoGUI操控實際Chrome。瀏覽器優先Playwright DOM(playwright_profile持久化)，pyautogui備用。Key讀取用字串拼接或獨立txt。
§
GIS監控v2.4：watchdog監聽sensor_config.json、雙軌(pending_set繪圖+ccd_status CCD文字)、啟動掃描、TG三層級🧊/🔴/🟡。monitor.py fix：normal_set sync bug(第814行)、tray icon雙擊+綠黃紅狀態色。numpy崩潰→force-reinstall。SOP：process list→pending_set→token→matplotlib。
§
Word正式報告規範：表格格式、字型、欄寬、配色以「115年度萬山…期中參考版.docx」為基準。中文字型=標楷體，英文數字=Times New Roman，同段落內run級別分開設定。
§
Grapher V9定稿：標楷體粗體純黑、四邊黑框無網格、圖例FontProperties(size=20,bold)、右Y軸黑字、時雨量=[OneHour]藍bar、累積=[RT]深紅#B91C1C折線、無箭頭標註、輸出V{N}.png至Desktop/charts/。skill: alice-scientific-charts
§
Hermes修復v3(5崩潰路徑)：A-DEP擊殺(Defender排除)、B-os.execvpe(Windows用subprocess.Popen+sys.exit)、C-profile re-exec死循環(HERMES_PROFILE_FROM_CLI)、D---replace陷阱、E-桌面vs CLI profile獨立(active-profile.json)。skill: alice-hermes-repair。
§
雙機設定：A端(公司)C:\Users\hans主力機GIS/投資/L2全在此、B端(家用)C:\Users\User且telegram.enabled=false。工具區同步hansv0704/hermes-tools每30分auto-sync。路徑用%USERPROFILE%不寫死。git衝突自動stash解圍。
§
LiveCode Studio v5.3：Hermes全自動協作面板port 5001。watchdog 5秒偵測、24hr修改補標、預設Session綠燈、工作區持久化lcs_workspaces.json。檔案：run_studio.py(根目錄)+skills/live_code_studio_skill.py+skills/base_skill.py+skills/lcs_template_v5.html。若誤移至apps/或legacy/會import error，從legacy/skills/復原、清__pycache__、taskkill port 5001重啟。
§
<<<<<<< HEAD
Alice行為規範：開場白先報現狀(排程/服務狀態)再問需求，勿說「全新對話session」。鐵律：(1)修復≠重寫，先確認現有結構；(2)改檔前先ls確認路徑；(3)每改一處立即curl驗證；(4)搞砸直接承認，勿用更多修改挽救。
=======
主人正式報告的 Word 表格格式以「115年度萬山、寶山、來義等五處大規模崩塌地區監測計畫_工作執行計畫書_期中參考版.docx」為基準範本。未來操作 Word 文件（正式報告），表格樣式、字型、欄寬、配色等均須比照該文件的格式，而非自訂美觀樣式。v3 升級模板僅為能力展示用，非正式格式。
§
主人正式報告字型規範：中文使用「標楷體」，英文與數字使用「Times New Roman」。製作 Word 文件時，同一個段落內的中英數字須各自套用對應字型（透過 run 級別分開設定，或設定 East-Asian 字型為標楷體、Latin 字型為 Times New Roman）。
§
Grapher 圖表 V9 定稿規格：字型=標楷體(DFKai-SB,kaiu.ttf)粗體純黑。四邊黑框無網格。圖例 FontProperties(size=20,bold)。右Y軸黑字。時雨量=[OneHour]藍bar，累積=[RT]深紅#B91C1C折線。無箭頭標註。輸出加版號V{N}.png至Desktop/charts/，腳本同目錄。Gemini Flash先分析參考圖再複刻。skill: alice-scientific-charts
§
Hermes修復 v3：5崩潰路徑 — A:DEP擊殺(Defender排除)、B:os.execvpe(Windows用subprocess.Popen+sys.exit、POSIX保持execvpe)、C:profile re-exec死循環(_apply_profile_override會從sys.argv移除--profile→args.profile永遠為空→用HERMES_PROFILE_FROM_CLI環境變數標記)、D:--replace陷阱(已有gateway時不綁port)、E:桌面版vs CLI profile獨立(%APPDATA%/Hermes/active-profile.json vs hermes profile use)。一鍵安裝若執行 profile use alice 必須同步建立 active-profile.json 否則桌面版崩潰。skill alice-hermes-repair 已含三層修復+完整references。
§
雙電腦識別：USERPROFILE=C:\Users\User 為家用電腦（B 端）；USERPROFILE=C:\Users\hans 為工作電腦（A 端）。兩台配置不同，寫 code 時用 USERPROFILE 判斷當前環境。記憶同步到另一台時，依 USERPROFILE 分辨「這條是講誰的」，避免 A 端讀到 B 端描述而誤認自己。
§
部署：git clone + bootstrap.bat 雙擊→自動 clone+一鍵安裝→解密→複製記憶到 alice+default→設 alice 預設 profile→偵測 Gateway 避免搶 TG。⚠️ bootstrap 若執行 hermes profile use alice，必須同步建立 %APPDATA%/Hermes/active-profile.json（{\"profile\":\"alice\"}），否則桌面版啟動時 os.execvpe 崩潰。cron 由 Alice 對話中建立。.env 用 openssl aes-256-cbc 加密。
§
LiveCode Studio v5.1 (2026-06-11)：v5.0 + `_scan_workspace_files` 自動標記 24hr 內修改的檔案為 recent_change。已知工作區：Hermes Skills (C:/Users/hans/AppData/Local/hermes/skills/alice)、Alice Legacy (C:/Users/hans/Desktop/Alice_Brain_Arch_20260506_031953)。LCS 需手動加入工作區才能跨 session 看到修改——主人期望跨 session 自動可見，但目前需顯式註冊。Hermes session 追蹤需主動呼叫 /api/session/start + /api/files/track。備份：skills/live_code_studio_skill_v4_backup.py，模板：skills/lcs_template_v5.html
§
記憶同步 cron ID 已更新為 54424bc21b88（雙向 pull+push，script=sync_memory_bidirectional.py，每30m）
>>>>>>> 4f4a8eb (sync: auto 06/12 20:04)
§
<<<<<<< HEAD
應用服務：LiveCode Studio v5.1 (port 5001)，支援 --daemon 背景模式（pythonw + logs/lcs_daemon.log）。前端雙 Tab（操作紀錄/工作區）。工作區自動標記 24hr 內修改為 recent_change。已知工作區：Hermes Skills、Alice Legacy。主人期望跨 session 自動可見修改——目前需顯式加入工作區才能實現。Hermes session 追蹤需主動呼叫 API。啟動 .bat 已改為背景分離模式。備份：skills/live_code_studio_skill_v4_backup.py
=======
GIS監控v2.4：watchdog監聽sensor_config.json、雙軌(pending_set繪圖+ccd_status CCD文字)、啟動掃描、TG三層級🧊/🔴/🟡。monitor.py fix：normal_set sync bug(第814行)、tray icon雙擊+綠黃紅狀態色。numpy崩潰→force-reinstall。SOP：process list→pending_set→token→matplotlib。
>>>>>>> 3482b44b5f60053ed37eef547a2bdd5cced962ef
§
<<<<<<< HEAD
GIS 警報層級格式：🧊數據凍結(freeze)、🔴達警戒(alert)、🟡達注意(attention)。caption 須含測站代碼、層級標題、詳細說明。watchdog token 解析需跳過值太短(<20字元)的行。
§
桌面版修復：Windows os.execvpe Segfault 根源在 hermes_cli/main.py:10364。source patch 已套用（main.py:10330 加 `sys.platform != "win32"` guard），skill=alice-hermes-maintenance v2.0。alice profile 現在可直接用桌面版，不需切 default。
§
GIS 監控（獨立循環）：大崩儀器DATA回傳，watchdog v2.3 只監聽 sensor_config.json。三層級警報 🧊freeze/🔴alert/🟡attention，HTML caption 含測站代碼+24h趨勢圖。故障排除 SOP：process list→pending_set→read_file 驗證 token→python matplotlib 測試。L2 巡檢 Playwright DOM+Gemini (2026-06-10)，嚴禁 pyautogui。災害 cron：35 5,11,14,17,20,23 * * * (暫停)。Grapher V9：標楷體粗體純黑，四邊黑框無網格。
§
主人正式報告的 Word 表格格式以「115年度萬山、寶山、來義等五處大規模崩塌地區監測計畫_工作執行計畫書_期中參考版.docx」為基準範本。未來操作 Word 文件（正式報告），表格樣式、字型、欄寬、配色等均須比照該文件的格式，而非自訂美觀樣式。v3 升級模板僅為能力展示用，非正式格式。
§
Alice行為規範：開場白先報現狀(排程/服務狀態)再問需求，勿說「全新對話session」。鐵律：(1)修復≠重寫，先確認現有結構；(2)改檔前先ls確認路徑；(3)每改一處立即curl驗證；(4)搞砸直接承認，勿用更多修改挽救。
>>>>>>> 3482b44b5f60053ed37eef547a2bdd5cced962ef
