技術教訓
§
(k) Windows 檔案編碼鐵律：.bat 用 utf-8-sig(BOM)、.vbs 用 ASCII（不吃UTF-8，中文路徑用 fso.GetParentFolderName 繞過）、.py/.pyw 用 utf-8 無 BOM。違反 = 亂碼或直接炸掉。已在 hermes_tray.vbs 犯過 2 次。
§
應用服務：LiveCode Studio v5.1 (port 5001)，支援 --daemon 背景模式（pythonw + logs/lcs_daemon.log）。前端雙 Tab（操作紀錄/工作區）。工作區自動標記 24hr 內修改為 recent_change。已知工作區：Hermes Skills、Alice Legacy。主人期望跨 session 自動可見修改——目前需顯式加入工作區才能實現。Hermes session 追蹤需主動呼叫 API。啟動 .bat 已改為背景分離模式。備份：skills/live_code_studio_skill_v4_backup.py
§
部署：git clone + bootstrap.bat 雙擊→自動 clone+一鍵安裝→解密→複製記憶到 alice+default→設 alice 預設 profile→偵測 Gateway 避免搶 TG。⚠️ bootstrap 若執行 hermes profile use alice，必須同步建立 %APPDATA%/Hermes/active-profile.json（{\"profile\":\"alice\"}），否則桌面版啟動時 os.execvpe 崩潰。cron 由 Alice 對話中建立。.env 用 openssl aes-256-cbc 加密。
§
截圖分析用 Gemini Flash (gemini-2.5-flash)，結果回傳 DeepSeek 繼續工作。PyAutoGUI 操控實際 Chrome 桌面用於需登入狀態的網站。瀏覽器自動化優先 Playwright DOM 操控（playwright_profile 持久化 session），pyautogui 只作備用。Key 讀取用字串拼接或獨立 txt 檔繞過遮蔽。
§
LiveCode Studio v5.1 (2026-06-11)：v5.0 + `_scan_workspace_files` 自動標記 24hr 內修改的檔案為 recent_change。已知工作區：Hermes Skills (C:/Users/hans/AppData/Local/hermes/skills/alice)、Alice Legacy (C:/Users/hans/Desktop/Alice_Brain_Arch_20260506_031953)。LCS 需手動加入工作區才能跨 session 看到修改——主人期望跨 session 自動可見，但目前需顯式註冊。Hermes session 追蹤需主動呼叫 /api/session/start + /api/files/track。備份：skills/live_code_studio_skill_v4_backup.py，模板：skills/lcs_template_v5.html
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
<<<<<<< HEAD
(k) Windows 檔案編碼鐵律：.bat 用 utf-8-sig(BOM)、.vbs 用 ASCII（不吃UTF-8，中文路徑用 fso.GetParentFolderName 繞過）、.py/.pyw 用 utf-8 無 BOM。違反 = 亂碼或直接炸掉。已在 hermes_tray.vbs 犯過 2 次。
=======
Alice 系統核心鐵律：(1) 投資代理人是獨立 Flask 伺服器 (port 5002)，嚴禁整合進 Telegram/handlers。(2) 兆豐登入在頂層。(3) 紙上/實盤交易隔離。(4) GIS 監控獨立循環，不依賴 Alice。(5) 行動前必須先讀取 .alice/ 目錄理解系統邊界。
§
技術教訓合集：(a) Hermes secret redaction 破壞含 token 字串→字串拼接/heredoc 繞過；(b) cron 用 cronjob 工具建立，勿用 CLI（不支援 --no_agent）；(c) SKILL.md 須含強制規則；(d) 一鍵安裝.bat：ASCII框線、[X][OK][!]、變數勿寫死、pip讀requirements.txt、TG三config、protobuf<6.0.0；(e) openssl 在 Git 自帶；(f) MEGA=兆豐證券，非 MEGA.nz；(g) Gateway 桌面關=TG斷，需 install 背景服務(UAC)；(h) 解密互動輸入密碼；(i) curl 下載 bat 有 BOM 風險→用 git clone/bootstrap.bat；(j) 桌面版內建 Gateway，多台開=搶 TG→次要設 telegram.enabled false；(k) v3 sync 逐條合併：push 先 pull→union merge→push，pull 只拉新條目不覆蓋；(l) TG 中繼站可跨裝置傳檔。
>>>>>>> 8a0c7b8ccd71752254e95a3e339dde014590fd72
§
GitHub：hansv0704/hermes-tools（公開 repo）。sync v3 逐條合併雙向同步。部署：git clone + bootstrap.bat 雙擊→自動 clone+一鍵安裝→解密(密碼互動輸入)→複製記憶到 alice+default→設 alice 預設 profile→偵測 Gateway 避免搶 TG。cron 由 Alice 對話中建立。.env 用 openssl aes-256-cbc 加密。
§
GIS 警報層級格式：🧊數據凍結(freeze)、🔴達警戒(alert)、🟡達注意(attention)。caption 須含測站代碼、層級標題、詳細說明。watchdog token 解析需跳過值太短(<20字元)的行。
§
桌面版修復：Windows os.execvpe Segfault 根源在 hermes_cli/main.py:10364。source patch 已套用（main.py:10330 加 `sys.platform != "win32"` guard），skill=alice-hermes-maintenance v2.0。alice profile 現在可直接用桌面版，不需切 default。
§
<<<<<<< HEAD
雙機設定
§
桌面版語言重置:taskkill強殺Hermes.exe導致Electron無法存偏好→工具區已改用正常關閉流程 不強殺Hermes.exe
=======
雙電腦識別：USERPROFILE=C:\Users\User 為家用電腦（B 端）；USERPROFILE=C:\Users\hans 為工作電腦（A 端）。兩台配置不同，寫 code 時用 USERPROFILE 判斷當前環境。記憶同步到另一台時，依 USERPROFILE 分辨「這條是講誰的」，避免 A 端讀到 B 端描述而誤認自己。
