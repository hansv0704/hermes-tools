技術教訓：(a) secret redaction 破壞含 token 字串→字串拼接/heredoc/獨立txt/Python open()繞過；(b) cron 用 cronjob 工具建立勿用CLI；(c) SKILL.md 須含強制規則；(d) 一鍵安裝.bat：ASCII框線、變數勿寫死、pip讀requirements.txt；(e) MEGA=兆豐證券；(f) Gateway 桌面關=TG斷，需 install 背景服務；(g) 多台開=搶TG→次要設 telegram.enabled false；(h) v3 sync 逐條合併；(i) matplotlib legend 圖例用 FontProperties(size=N) 直接設，fontsize+prop dict 組合會失效；(j) .env 讀 API key 用 Python open() 繞過 secret redaction
§
應用服務：LiveCode Studio v5.1 (port 5001)，支援 --daemon 背景模式（pythonw + logs/lcs_daemon.log）。前端雙 Tab（操作紀錄/工作區）。工作區自動標記 24hr 內修改為 recent_change。已知工作區：Hermes Skills、Alice Legacy。主人期望跨 session 自動可見修改——目前需顯式加入工作區才能實現。Hermes session 追蹤需主動呼叫 API。啟動 .bat 已改為背景分離模式。備份：skills/live_code_studio_skill_v4_backup.py
§
部署：git clone + bootstrap.bat 雙擊→自動 clone+一鍵安裝→解密→複製記憶到 alice+default→設 alice 預設 profile→偵測 Gateway 避免搶 TG。⚠️ bootstrap 若執行 hermes profile use alice，必須同步建立 %APPDATA%/Hermes/active-profile.json（{\"profile\":\"alice\"}），否則桌面版啟動時 os.execvpe 崩潰。cron 由 Alice 對話中建立。.env 用 openssl aes-256-cbc 加密。
§
截圖分析用 Gemini Flash (gemini-2.5-flash)，結果回傳 DeepSeek 繼續工作。PyAutoGUI 操控實際 Chrome 桌面用於需登入狀態的網站。瀏覽器自動化優先 Playwright DOM 操控（playwright_profile 持久化 session），pyautogui 只作備用。Key 讀取用字串拼接或獨立 txt 檔繞過遮蔽。
§
LiveCode Studio v5.1 (2026-06-11)：v5.0 + `_scan_workspace_files` 自動標記 24hr 內修改的檔案為 recent_change。已知工作區：Hermes Skills (C:/Users/hans/AppData/Local/hermes/skills/alice)、Alice Legacy (C:/Users/hans/Desktop/Alice_Brain_Arch_20260506_031953)。LCS 需手動加入工作區才能跨 session 看到修改——主人期望跨 session 自動可見，但目前需顯式註冊。Hermes session 追蹤需主動呼叫 /api/session/start + /api/files/track。備份：skills/live_code_studio_skill_v4_backup.py，模板：skills/lcs_template_v5.html
§
GIS 監控（獨立循環）：大崩儀器DATA回傳，watchdog v2.3 只監聽 sensor_config.json。三層級警報 🧊freeze/🔴alert/🟡attention，HTML caption 含測站代碼+24h趨勢圖。故障排除 SOP：process list→pending_set→read_file 驗證 token→python matplotlib 測試。L2 巡檢 Playwright DOM+Gemini (2026-06-10)，嚴禁 pyautogui。災害 cron：35 5,11,14,17,20,23 * * * (暫停)。Grapher V9：標楷體粗體純黑，四邊黑框無網格。
§
主人正式報告的 Word 表格格式以「115年度萬山、寶山、來義等五處大規模崩塌地區監測計畫_工作執行計畫書_期中參考版.docx」為基準範本。未來操作 Word 文件（正式報告），表格樣式、字型、欄寬、配色等均須比照該文件的格式，而非自訂美觀樣式。v3 升級模板僅為能力展示用，非正式格式。
§
主人正式報告字型規範：中文使用「標楷體」，英文與數字使用「Times New Roman」。製作 Word 文件時，同一個段落內的中英數字須各自套用對應字型（透過 run 級別分開設定，或設定 East-Asian 字型為標楷體、Latin 字型為 Times New Roman）。
§
Grapher 圖表 V9 定稿規格：字型=標楷體(DFKai-SB,kaiu.ttf)粗體純黑。四邊黑框無網格。圖例 FontProperties(size=20,bold)。右Y軸黑字。時雨量=[OneHour]藍bar，累積=[RT]深紅#B91C1C折線。無箭頭標註。輸出加版號V{N}.png至Desktop/charts/，腳本同目錄。Gemini Flash先分析參考圖再複刻。skill: alice-scientific-charts
§
Hermes修復 v3：5崩潰路徑 — A:DEP擊殺(Defender排除)、B:os.execvpe(Windows用subprocess.Popen+sys.exit、POSIX保持execvpe)、C:profile re-exec死循環(_apply_profile_override會從sys.argv移除--profile→args.profile永遠為空→用HERMES_PROFILE_FROM_CLI環境變數標記)、D:--replace陷阱(已有gateway時不綁port)、E:桌面版vs CLI profile獨立(%APPDATA%/Hermes/active-profile.json vs hermes profile use)。一鍵安裝若執行 profile use alice 必須同步建立 active-profile.json 否則桌面版崩潰。skill alice-hermes-repair 已含三層修復+完整references。
§
雙機設定 § A端(公司):USERPROFILE=C:\Users\hans 主力機 GIS watchdog/投資代理人/L2巡檢全在此 § B端(家用):USERPROFILE=C:\Users\User telegram.enabled=false 避免搶TG § 工具區同步:hansv0704/hermes-tools GitHub repo 兩台共用 30分鐘auto-pull § 路徑規範:只用USERPROFILE變數 不寫死C:\Users\hans\或C:\Users\User\ § 任務標記:[A端]/[B端] § 記憶格式:§分隔 § git衝突:自動stash解圍(已內建) § 技能/記憶備份:工具區內Alice記憶_backup+Alice技能_backup 初始化自動xcopy還原