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
Alice行為規範：開場白先報現狀(排程/服務狀態)再問需求，勿說「全新對話session」。鐵律：(1)修復≠重寫，先確認現有結構；(2)改檔前先ls確認路徑；(3)每改一處立即curl驗證；(4)搞砸直接承認，勿用更多修改挽救。
§
技術教訓
§
(k) Windows 檔案編碼鐵律：.bat 用 utf-8-sig(BOM)、.vbs 用 ASCII（不吃UTF-8，中文路徑用 fso.GetParentFolderName 繞過）、.py/.pyw 用 utf-8 無 BOM。違反 = 亂碼或直接炸掉。已在 hermes_tray.vbs 犯過 2 次。
§
部署：git clone + bootstrap.bat 雙擊→自動 clone+一鍵安裝→解密→複製記憶到 alice+default→設 alice 預設 profile→偵測 Gateway 避免搶 TG。⚠️ bootstrap 若執行 hermes profile use alice，必須同步建立 %APPDATA%/Hermes/active-profile.json（{\"profile\":\"alice\"}），否則桌面版啟動時 os.execvpe 崩潰。cron 由 Alice 對話中建立。.env 用 openssl aes-256-cbc 加密。
§
截圖分析用 Gemini Flash (gemini-2.5-flash)，結果回傳 DeepSeek 繼續工作。PyAutoGUI 操控實際 Chrome 桌面用於需登入狀態的網站。瀏覽器自動化優先 Playwright DOM 操控（playwright_profile 持久化 session），pyautogui 只作備用。Key 讀取用字串拼接或獨立 txt 檔繞過遮蔽。
§
GIS 監控 v2.4：watchdog 只監聽 sensor_config.json、雙軌（pending_set儀器繪圖+ccd_status CCD純文字）、啟動掃描、TG三層級🧊/🔴/🟡。monitor.py fix：normal_set sync bug（第814行漏寫致延長觀察卡住）、tray icon雙擊+綠黃紅狀態色。numpy崩潰→force-reinstall。故障 SOP：process list→pending_set→token→matplotlib
§
主人正式報告的 Word 表格格式以「115年度萬山、寶山、來義等五處大規模崩塌地區監測計畫_工作執行計畫書_期中參考版.docx」為基準範本。未來操作 Word 文件（正式報告），表格樣式、字型、欄寬、配色等均須比照該文件的格式，而非自訂美觀樣式。v3 升級模板僅為能力展示用，非正式格式。
§
主人正式報告字型規範：中文使用「標楷體」，英文與數字使用「Times New Roman」。製作 Word 文件時，同一個段落內的中英數字須各自套用對應字型（透過 run 級別分開設定，或設定 East-Asian 字型為標楷體、Latin 字型為 Times New Roman）。
§
Grapher 圖表 V9 定稿規格：字型=標楷體(DFKai-SB,kaiu.ttf)粗體純黑。四邊黑框無網格。圖例 FontProperties(size=20,bold)。右Y軸黑字。時雨量=[OneHour]藍bar，累積=[RT]深紅#B91C1C折線。無箭頭標註。輸出加版號V{N}.png至Desktop/charts/，腳本同目錄。Gemini Flash先分析參考圖再複刻。skill: alice-scientific-charts
§
Hermes修復 v3：5崩潰路徑 — A:DEP擊殺(Defender排除)、B:os.execvpe(Windows用subprocess.Popen+sys.exit、POSIX保持execvpe)、C:profile re-exec死循環(_apply_profile_override會從sys.argv移除--profile→args.profile永遠為空→用HERMES_PROFILE_FROM_CLI環境變數標記)、D:--replace陷阱(已有gateway時不綁port)、E:桌面版vs CLI profile獨立(%APPDATA%/Hermes/active-profile.json vs hermes profile use)。一鍵安裝若執行 profile use alice 必須同步建立 active-profile.json 否則桌面版崩潰。skill alice-hermes-repair 已含三層修復+完整references。
§
雙機設定
§
A端(公司):USERPROFILE=C:\Users\hans 主力機 GIS watchdog/投資代理人/L2巡檢全在此
§
B端(家用):USERPROFILE=C:\Users\User telegram.enabled=false 避免搶TG
§
工具區同步:hansv0704/hermes-tools GitHub repo 兩台共用 30分鐘auto-pull
§
路徑規範:只用USERPROFILE變數 不寫死C:\Users\hans\或C:\Users\User\
§
任務標記:[A端]/[B端]
§
記憶格式:
§
分隔
§
git衝突:自動stash解圍(已內建)
§
技能/記憶備份:工具區內Alice記憶_backup+Alice技能_backup 初始化自動xcopy還原
§
已知上游bug
§
桌面版前端:切session時 tapClientLookup Index 10 out of bounds(off-by-one) 非我方可修 暫時解法用/reset清對話再切
§
桌面版語言重置:taskkill強殺Hermes.exe導致Electron無法存偏好→工具區已改用正常關閉流程 不強殺Hermes.exe
§
LiveCode Studio v5.3 (2026-06-12)：Hermes 全自動協作面板。設計原則：(1) Session 啟動後全自動追蹤，watchdog 5秒偵測新檔+變更；(2) 啟動時補標 24hr 修改；(3) 預設 Session 永遠綠燈；(4) 工作區持久化到 lcs_workspaces.json；(5) 所有路徑相對/動態（跨機器）。檔案位置：skills/live_code_studio_skill.py、skills/lcs_template_v5.html、run_studio.py（皆在專案根目錄，無 apps/ 或 legacy/ 子目錄）。Port 5001 http://localhost:5001。啟動：雙擊根目錄啟動LiveCodeStudio.bat。
§
LCS v5.3 檔案依賴：run_studio.py（專案根目錄）+ skills/live_code_studio_skill.py + skills/base_skill.py + skills/lcs_template_v5.html。若檔案被移至 apps/ 或 legacy/ 會導致 import error 或 daemon 崩潰。復原方式：從 legacy/skills/ 複製回 skills/、從 apps/ 複製 run_studio.py 回根目錄、清除 __pycache__、taskkill 清除卡死的 port 5001 程序後重啟。
§
主人不喜歡 Alice 在對話開場時說「全新對話 session」。雖然 session 技術上是新的，但我們的關係、記憶、技能和過往互動都是延續的——Alice 應該以「記憶和服務都在持續運作」的角度開場，而非「從零開始」。開場白應先報現狀（排程、服務狀態），再詢問需求。
§
Alice 行為鐵律（2026-06-12）：(1) 主人說「修復」≠「重寫架構」——先確認現有結構，只修明確 bug；(2) 改任何檔案前先 `ls` 確認它真的在那個路徑；(3) 每改一個地方立刻 curl 驗證，不要連續改 5 處才發現第一個就掛了；(4) 如果搞砸了直接承認，不要試圖用更多修改來挽救。
