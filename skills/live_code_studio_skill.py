#!/usr/bin/env python3
"""Live Code Studio v4.0 - 歷史版本比對版 (實裝多版本切換、優化基準點邏輯)"""

import os
import sys
import json
import difflib
import urllib.parse
import hashlib
import threading
import time
import socket
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Dict, List, Any

# ─── 基礎路徑 ───
# v4.2: 支援 LCS_WORKSPACE 環境變數，可監控任意專案目錄
_default_dir = Path(__file__).resolve().parent.parent
BASE_DIR = Path(os.getenv("LCS_WORKSPACE", str(_default_dir)))
PORT = int(os.getenv("LCS_PORT", "5001"))

# ═══ DeepSeek API 金鑰載入 (自我診斷用) ═══
# v4.1: 優先讀 Hermes 環境變數，向後相容舊 Alice .env
from openai import OpenAI
_deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")  # Hermes 環境變數優先
if not _deepseek_api_key:
    # fallback: 從 .env 檔案讀取（Hermes → 舊 Alice）
    for _ep in [
        Path(os.getenv("HERMES_HOME", os.path.expandvars(r"%LOCALAPPDATA%\hermes"))) / ".env",
        BASE_DIR / ".env",
    ]:
        if _ep.exists():
            try:
                for _line in _ep.read_text("utf-8").split("\n"):
                    if _line.startswith("DEEPSEEK_API_KEY="):
                        _deepseek_api_key = _line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
            except: pass
        if _deepseek_api_key: break
_client = OpenAI(api_key=_deepseek_api_key, base_url="https://api.deepseek.com") if _deepseek_api_key else None

# ─── 全域狀態 ───
_file_metadata: Dict[str, Dict[str, Any]] = {}  # 相對路徑 -> {mtime, size, hash}
_modified_files: Dict[str, str] = {}  # 相對路徑 -> "modified"
_history_versions: Dict[str, List[Dict[str, str]]] = {} 
_repl_logs: List[str] = [] # 新增：CodeWhale REPL 日誌
_lock = threading.RLock()
_server_instance = None
_server_thread = None

def add_repl_log(msg: str):
    """供外部技能呼叫，將 REPL 執行結果推送到前端"""
    with _lock:
        timestamp = datetime.now().strftime("%H:%M:%S")
        _repl_logs.append(f"[{timestamp}] {msg}")
        if len(_repl_logs) > 100:
            _repl_logs.pop(0)

def _compute_hash(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()

def _add_history(rel_path: str, content: str):
    """新增一個歷史版本，若內容與最後一個版本相同則跳過"""
    with _lock:
        if rel_path not in _history_versions:
            _history_versions[rel_path] = []
        
        history = _history_versions[rel_path]
        if history and history[-1]["content"] == content:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        # 限制每個檔案保留最近 10 個版本
        if len(history) >= 10:
            history.pop(0)
        history.append({"timestamp": timestamp, "content": content})

def _scan_files(full_scan=False) -> Dict[str, Dict[str, Any]]:
    metadata = {}
    extensions = {".py", ".txt", ".json", ".env", ".md", ".bat", ".yaml", ".yml", ".html", ".css", ".js", ".csv", ".xml", ".cfg", ".ini", ".toml"}
    for f in BASE_DIR.rglob("*"):
        try:
            if f.is_file() and f.suffix in extensions:
                rel_path = f.relative_to(BASE_DIR)
                parts = rel_path.parts
                if any(p in ("__pycache__", ".git", "node_modules", "backups", "data", "temp_sync_workplace", ".ipynb_checkpoints", "memory", "logs") for p in parts):
                    continue
                rel = str(rel_path.as_posix())
                stat = f.stat()
                mtime = stat.st_mtime
                size = stat.st_size
                
                # 效能優化：若 mtime 與 size 沒變，且不是 full_scan，則沿用舊的 hash
                with _lock:
                    old_meta = _file_metadata.get(rel)
                
                if not full_scan and old_meta and old_meta["mtime"] == mtime and old_meta["size"] == size:
                    metadata[rel] = old_meta
                else:
                    # 只有在變動時才讀取內容 (IO 耗時操作)
                    try:
                        content = f.read_text("utf-8", errors="ignore")
                        metadata[rel] = {
                            "mtime": mtime,
                            "size": size,
                            "hash": _compute_hash(content)
                        }
                        # 歷史紀錄寫入應在鎖外準備好資料，或使用 RLock
                        if rel not in _history_versions:
                            _add_history(rel, content)
                    except: continue
        except Exception:
            continue
    return metadata

def _detect_changes():
    global _file_metadata
    time.sleep(5)
    while True:
        time.sleep(5)
        try:
            current = _scan_files()
            changed_py_files = []  # Phase 2+3: 追蹤本次語法檢查通過的 .py 檔案
            # 將比對邏輯移出 _lock，僅在更新全域狀態時才加鎖
            for rel_path, meta in current.items():
                with _lock:
                    old_meta = _file_metadata.get(rel_path)
                
                if old_meta is None:
                    with _lock: _file_metadata[rel_path] = meta
                elif old_meta["hash"] != meta["hash"]:
                    # 偵測到變更，自動加入歷史紀錄 (如果是外部修改)
                    full_path = BASE_DIR / rel_path
                    try:
                        content = full_path.read_text("utf-8", errors="ignore")
                        _add_history(rel_path, content)
                        # 🆕 語法檢查：偵測到 .py 變更時自動 compile() 驗證
                        if rel_path.endswith('.py'):
                            try:
                                compile(content, rel_path, 'exec')
                                add_repl_log(f"✅ {rel_path} 語法檢查通過")
                                changed_py_files.append((rel_path, content))
                            except SyntaxError as e:
                                add_repl_log(f"❌ {rel_path} Line {e.lineno}: {e.msg}")
                                with _lock:
                                    _file_metadata[rel_path] = meta
                                    _modified_files[rel_path] = f"syntax_error: Line {e.lineno}"
                                continue
                        with _lock:
                            _file_metadata[rel_path] = meta
                            _modified_files[rel_path] = "modified"
                    except: continue
            
            # Phase 2: import 鏈檢查（對 compile 通過的 .py，檢查牽連檔案能否 compile）
            if changed_py_files:
                _check_import_chain(changed_py_files)
            
            # Phase 2.5: main.py ↔ handlers.py 同步檢查（防止 ImportError 崩潰）
            changed_rel_paths = {rp for rp, _ in changed_py_files}
            if "main.py" in changed_rel_paths or "handlers.py" in changed_rel_paths:
                _check_main_handlers_sync()
            
            # Phase 3: DeepSeek 語意審查（背景非同步，不阻塞主循環）
            if changed_py_files and _deepseek_api_key:
                threading.Thread(target=_semantic_review_async, 
                               args=(changed_py_files,), daemon=True).start()
            
            with _lock:
                deleted = [k for k in _file_metadata if k not in current]
                for k in deleted:
                    del _file_metadata[k]
                    _modified_files.pop(k, None)
        except Exception:
            pass

def _check_import_chain(changed_files):
    """Phase 2: 分析被變更檔案 import 鏈，檢查牽連檔案能否 compile"""
    import ast
    checked = set()
    for rel_path, content in changed_files:
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split('.')[0]
                        _check_module_import(module, rel_path, checked)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        _check_module_import(module, rel_path, checked)
        except Exception:
            pass

def _check_module_import(module, source_file, checked):
    """檢查單一 import 模組是否存在且能 compile"""
    if module in checked: return
    checked.add(module)
    candidates = [
        BASE_DIR / f"{module}.py",
        BASE_DIR / "skills" / f"{module}.py",
        BASE_DIR / "engines" / f"{module}.py",
        BASE_DIR / "core" / f"{module}.py",
        BASE_DIR / module / "__init__.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                content = candidate.read_text("utf-8", errors="ignore")
                compile(content, str(candidate.relative_to(BASE_DIR)), 'exec')
                return  # import 鏈正常
            except SyntaxError as e:
                add_repl_log(f"⚠️ {source_file} → {candidate.relative_to(BASE_DIR)} Line {e.lineno}: {e.msg}")
                return
            except Exception:
                pass

def _check_main_handlers_sync():
    """Phase 2.5: 檢查 main.py 從 handlers 導入的函式是否都存在於 handlers.py 中
    防止 handlers.py 刪除函式後 main.py 仍試圖 import 導致 ImportError 崩潰"""
    import ast
    main_path = BASE_DIR / "main.py"
    handlers_path = BASE_DIR / "handlers.py"
    
    if not main_path.exists() or not handlers_path.exists():
        return []
    
    # 解析 handlers.py 中定義的所有頂層函式名稱（僅頂層，避免嵌套函式 false negative）
    try:
        handlers_tree = ast.parse(handlers_path.read_text("utf-8", errors="ignore"))
        handlers_funcs = {
            node.name for node in ast.iter_child_nodes(handlers_tree) 
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    except Exception:
        return []
    
    # 解析 main.py 中 from handlers import (...) 的內容
    try:
        main_tree = ast.parse(main_path.read_text("utf-8", errors="ignore"))
        imported_from_handlers = set()
        handler_registrations = []  # 追蹤 add_handler(CommandHandler("xxx", yyy))
        for node in ast.walk(main_tree):
            # 僅匹配絕對導入 (level=0)，排除相對導入誤匹配
            if isinstance(node, ast.ImportFrom) and node.module == "handlers" and node.level == 0:
                for alias in node.names:
                    if alias.name != "*":  # 跳過萬用導入
                        imported_from_handlers.add(alias.name)
            # 擷取 add_handler(CommandHandler("cmd", func_name)) 註冊
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Attribute) and 
                    node.func.attr == "add_handler"):
                    # 找內層 CommandHandler("cmd", func_name)
                    for arg in node.args:
                        if isinstance(arg, ast.Call):
                            if (isinstance(arg.func, ast.Attribute) and 
                                arg.func.attr in ("CommandHandler", "MessageHandler", "CallbackQueryHandler")):
                                # 第二個參數是 handler 函式名稱
                                if len(arg.args) >= 2:
                                    handler_arg = arg.args[1]
                                    if isinstance(handler_arg, ast.Name):
                                        handler_registrations.append(handler_arg.id)
    except Exception:
        return
    
    # 彙整問題清單
    issues = []
    
    # 比對：import 但 handlers.py 中不存在的函式
    missing_imports = imported_from_handlers - handlers_funcs
    for func_name in sorted(missing_imports):
        msg = f"main.py 導入 handlers.{func_name} 但 handlers.py 中未定義！重啟將崩潰"
        issues.append({"severity": "high", "file": "main.py", "description": msg, "suggestion": f"從 handlers.py 恢復 {func_name} 函式，或從 main.py 移除該 import 與 add_handler 註冊"})
        add_repl_log(f"❌ {msg}")

    # 比對：add_handler 註冊但不在 handlers_funcs 中的（排除 MessageHandler / CallbackQueryHandler 內建）
    builtin_handlers = {"handle_message", "handle_document", "handle_photo", "handle_voice", "handle_callback_query"}
    missing_registrations = set(handler_registrations) - handlers_funcs - builtin_handlers
    for func_name in sorted(missing_registrations):
        msg = f"main.py add_handler 註冊 {func_name} 但未在 handlers.py 中找到對應函式"
        issues.append({"severity": "high", "file": "main.py", "description": msg, "suggestion": f"檢查 {func_name} 是否已從 handlers.py 刪除，若是請同步移除 main.py 中的 add_handler 註冊"})
        add_repl_log(f"⚠️ {msg}")
    
    return issues

def _semantic_review_async(changed_files):
    """Phase 3: DeepSeek V4 Flash 語意審查（背景執行，不阻塞）"""
    for rel_path, content in changed_files:
        try:
            review_prompt = f"""快速審查以下 Python 程式碼變更（1 個最重要問題或回 None）：
檔案: {rel_path}
```python
{content[:2000]}
```
一句中文簡述或 None："""
            resp = _client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[{"role": "user", "content": review_prompt}],
                max_tokens=80,
                temperature=0.2
            )
            result = (resp.choices[0].message.content or "").strip()
            if result and result != "None" and "無" not in result[:5]:
                add_repl_log(f"🤖 {rel_path}: {result[:150]}")
        except Exception:
            pass

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

class LiveCodeStudioHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: dict, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _send_text(self, text: str, status=200, content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(text.encode("utf-8"))
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _send_html(self, html: str):
        self._send_text(html, content_type="text/html; charset=utf-8")

    def _read_file_content(self, rel_path: str) -> Optional[str]:
        try:
            decoded_path = urllib.parse.unquote(rel_path)
            full = (BASE_DIR / decoded_path).resolve()
            if not str(full).startswith(str(BASE_DIR.resolve())):
                return None
            if not full.exists() or not full.is_file():
                return None
            return full.read_text("utf-8", errors="ignore")
        except Exception:
            return None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path == "/api/tree":
            with _lock:
                files = sorted(_file_metadata.keys())
                modified = dict(_modified_files)
            self._send_json({"files": files, "modified": modified})
        elif path.startswith("/api/read/"):
            rel = path[len("/api/read/"):]
            content = self._read_file_content(rel)
            if content is None:
                self._send_json({"error": f"File not found: {rel}"}, 404)
                return
            # 讀取時，確保有初始歷史
            if rel not in _history_versions:
                _add_history(rel, content)
            
            history = _history_versions.get(rel, [])
            self._send_json({
                "content": content, 
                "path": rel, 
                "history": history
            })
        elif path.startswith("/api/diff/"):
            rel = path[len("/api/diff/"):]
            disk_content = self._read_file_content(rel)
            if disk_content is None:
                self._send_json({"error": "File not found"}, 404)
                return
            history = _history_versions.get(rel, [])
            self._send_json({"disk_content": disk_content, "history": history})
        elif path.startswith("/api/clear_notify/"):
            rel = path[len("/api/clear_notify/"):]
            with _lock:
                if rel == "all":
                    _modified_files.clear()
                else:
                    _modified_files.pop(rel, None)
            self._send_json({"status": "ok"})
        elif path == "/api/repl_logs":
            with _lock:
                logs = list(_repl_logs)
            self._send_json({"logs": logs})
        elif path == "/" or path == "":
            self._send_html(HTML_TEMPLATE)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/api/repl_logs_push":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            msg = data.get("msg", "")
            add_repl_log(msg)
            self._send_json({"status": "ok"})
        elif self.path == "/api/save":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            rel_path = data.get("path", "")
            content = data.get("content", "")
            try:
                full = (BASE_DIR / rel_path).resolve()
                if not str(full).startswith(str(BASE_DIR.resolve())):
                    self._send_json({"error": "Access denied"}, 403)
                    return
                full.write_text(content, "utf-8")
                
                stat = full.stat()
                with _lock:
                    _file_metadata[rel_path] = {
                        "mtime": stat.st_mtime,
                        "size": stat.st_size,
                        "hash": _compute_hash(content)
                    }
                    # 手動存檔後，自動加入歷史紀錄
                    _add_history(rel_path, content)
                    _modified_files.pop(rel_path, None)
                self._send_json({"status": "ok"})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        elif self.path == "/api/self_review":
            self._handle_self_review()

    def _handle_self_review(self):
        """🩺 Alice 自我診斷：掃描核心程式碼，找出潛在問題（結構化 + AI 雙重審查）"""
        # ═══ Phase 0: 「讀資訊、看進度、懂需求」.alice/ 自檢 ═══
        alice_issues = []
        alice_summary = {}
        
        # 讀資訊：FACTS.md 邊界檢查
        facts_path = BASE_DIR / ".alice" / "FACTS.md"
        if facts_path.exists():
            facts_content = facts_path.read_text("utf-8", errors="ignore")
            alice_summary["facts_loaded"] = True
            boundary_checks = []
            if "投資代理人" in facts_content and "handlers.py" in facts_content:
                boundary_checks.append("✅ 投資代理人 ≠ Telegram 邊界已記錄")
            if "GIS 監控獨立" in facts_content:
                boundary_checks.append("✅ GIS 監控獨立邊界已記錄")
            alice_summary["boundary_checks"] = boundary_checks
        else:
            alice_summary["facts_loaded"] = False
            alice_issues.append({
                "severity": "medium", "file": ".alice/FACTS.md",
                "description": "FACTS.md 不存在，無法驗證架構邊界",
                "suggestion": "執行 .alice/ 初始化建立 FACTS.md"
            })
        
        # 看進度：TASK_BOARD.md 狀態檢查
        task_path = BASE_DIR / ".alice" / "TASK_BOARD.md"
        if task_path.exists():
            task_content = task_path.read_text("utf-8", errors="ignore")
            alice_summary["taskboard_loaded"] = True
            in_progress = task_content.count("| 🔧 進行中")
            pending = task_content.count("| ⬜ 待開發")
            alice_summary["tasks_in_progress"] = in_progress
            alice_summary["tasks_pending"] = pending
        else:
            alice_summary["taskboard_loaded"] = False
        
        # 懂需求：LOG.md 脈絡檢查
        log_path = BASE_DIR / ".alice" / "LOG.md"
        if log_path.exists():
            log_content = log_path.read_text("utf-8", errors="ignore")
            alice_summary["log_loaded"] = True
            recent_entries = []
            for line in log_content.split("\n"):
                if line.startswith("## 20"):
                    recent_entries.append(line.strip("## ").strip())
                    if len(recent_entries) >= 3:
                        break
            alice_summary["recent_log_entries"] = recent_entries
        else:
            alice_summary["log_loaded"] = False
        
        # ═══ Phase 4: 需求備忘錄（讀取 REQUIREMENTS.md）═══
        phase4_issues = []
        phase4_summary = {}
        
        req_path = BASE_DIR / ".alice" / "REQUIREMENTS.md"
        if req_path.exists():
            req_content = req_path.read_text("utf-8", errors="ignore")
            phase4_summary["requirements_loaded"] = True
            core_lines = []
            for line in req_content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- **"):
                    core_lines.append(stripped)
            phase4_summary["core_requirements"] = core_lines
        else:
            phase4_summary["requirements_loaded"] = False
            phase4_issues.append({
                "severity": "medium",
                "file": ".alice/REQUIREMENTS.md",
                "description": "需求備忘錄不存在",
                "suggestion": "建立 .alice/REQUIREMENTS.md 記錄核心需求"
            })
        
        # ═══ Phase 1: 結構化檢查（不依賴 API，零成本）═══
        structural_high = []
        structural_medium = []
        
        # 1.1 main.py ↔ handlers.py 同步檢查
        sync_issues = _check_main_handlers_sync() or []
        for issue in sync_issues:
            if issue["severity"] == "high":
                structural_high.append(issue)
            else:
                structural_medium.append(issue)
        
        # 若無 API key，僅回傳結構化檢查結果
        if not _deepseek_api_key:
            self._send_json({
                "status": "ok",
                "total": len(structural_high) + len(structural_medium),
                "high": structural_high,
                "medium": structural_medium,
                "low": [],
                "files_scanned": 2,
                "note": "⚠️ DeepSeek API key 未設定，僅執行結構化檢查",
                "phase0": {
                    "summary": alice_summary,
                    "issues": alice_issues
                },
                "phase4": {
                    "summary": phase4_summary,
                    "issues": phase4_issues
                }
            })
            return
        
        try:
            import glob as _glob
            target_dirs = ["skills/", "engines/"]
            target_ext = ".py"
            code_files = {}
            for d in target_dirs:
                dpath = BASE_DIR / d
                if dpath.exists():
                    for f in dpath.rglob(f"*{target_ext}"):
                        rel = str(f.relative_to(BASE_DIR).as_posix())
                        if "__pycache__" not in rel:
                            code_files[rel] = f.read_text("utf-8", errors="ignore")[:3000]
            
            core_files = ["agent.py", "handlers.py", "memory.py", "tools.py"]
            for cf in core_files:
                fpath = BASE_DIR / cf
                if fpath.exists():
                    code_files[cf] = fpath.read_text("utf-8", errors="ignore")[:3000]
            
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def _review_single_file(path, content):
                review_prompt = f"""分析以下 Python 程式碼，找出潛在問題（最多 3 個）：
檔案: {path}
```python
{content[:3000]}
```
請以 JSON 格式回覆：{{"issues": [{{"severity": "high|medium|low", "line_hint": "行號或區段描述", "description": "問題描述", "suggestion": "修復建議"}}]}}
若無問題回覆：{{"issues": []}}"""
                resp = _client.chat.completions.create(
                    model="deepseek-v4-flash",
                    messages=[{"role": "user", "content": review_prompt}],
                    max_tokens=600,
                    temperature=0.3
                )
                result_text = resp.choices[0].message.content if resp.choices else "{}"
                file_findings = []
                try:
                    result_json = json.loads(result_text)
                    for issue in result_json.get("issues", []):
                        issue["file"] = path
                        file_findings.append(issue)
                except json.JSONDecodeError:
                    pass
                return file_findings
            
            findings = []
            files_to_scan = list(code_files.items())[:8]
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(_review_single_file, path, content): path 
                          for path, content in files_to_scan}
                for future in as_completed(futures):
                    try:
                        findings.extend(future.result())
                    except Exception:
                        pass
            
            high = [f for f in findings if f.get("severity") == "high"]
            medium = [f for f in findings if f.get("severity") == "medium"]
            low = [f for f in findings if f.get("severity") == "low"]
            
            # 合併結構化檢查結果
            all_high = structural_high + high
            all_medium = structural_medium + medium
            
            self._send_json({
                "status": "ok",
                "total": len(all_high) + len(all_medium) + len(low),
                "high": all_high,
                "medium": all_medium,
                "low": low,
                "files_scanned": len(code_files) + 2,  # +2 for main.py & handlers.py structural
                "structural_checks": True,
                "phase0": {
                    "summary": alice_summary,
                    "issues": alice_issues
                },
                "phase4": {
                    "summary": phase4_summary,
                    "issues": phase4_issues
                }
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        pass

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<title>Live Code Studio v4.0</title>
<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js"></script>
<style>
:root {
    --lc-bg: #1e1e1e; --lc-bg-light: #252526; --lc-bg-lighter: #2d2d2d; --lc-bg-hover: #2a2d2e;
    --lc-border: #3c3c3c; --lc-border-light: #454545; --lc-text: #d4d4d4; --lc-text-dim: #888;
    --lc-accent: #0e639c; --lc-accent-hover: #1177bb; --lc-warn: #ff8c00; --lc-repl-bg: #000;
    --lc-repl-text: #00ff00; --lc-splitter: #3c3c3c; --lc-splitter-hover: #555;
    --lc-toolbar-height: 35px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--lc-bg); color: var(--lc-text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

#notification-bar { display: none; background: #8e2a00; color: #fff; padding: 0 16px; font-size: 13px; height: 35px; flex-shrink: 0; z-index: 100; border-bottom: 1px solid var(--lc-warn); align-items: center; justify-content: space-between; }
#notification-bar.show { display: flex; }
.notify-msg { font-weight: 500; }
.notify-actions { display: flex; gap: 10px; }
.notify-actions button { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.5); color: #fff; padding: 2px 8px; cursor: pointer; border-radius: 3px; font-size: 11px; }
.notify-actions button:hover { background: rgba(255,255,255,0.4); }

#main { display: flex; flex: 1; overflow: hidden; position: relative; }
#sidebar { width: 260px; min-width: 160px; max-width: 500px; background: var(--lc-bg-light); border-right: 1px solid var(--lc-border); display: flex; flex-direction: column; overflow-x: hidden; flex-shrink: 0; }
#sidebar.collapsed { display: none; }
.splitter-v { width: 5px; min-width: 5px; background: var(--lc-splitter); cursor: col-resize; flex-shrink: 0; transition: background 0.15s; position: relative; z-index: 10; }
.splitter-v:hover, .splitter-v.active { background: var(--lc-accent); }
.splitter-v::after { content: ''; position: absolute; top: 0; left: -2px; right: -2px; bottom: 0; }
.splitter-h { height: 5px; min-height: 5px; background: var(--lc-splitter); cursor: row-resize; flex-shrink: 0; transition: background 0.15s; }
.splitter-h:hover, .splitter-h.active { background: var(--lc-accent); }
#sidebar-toggle { width: 26px; background: var(--lc-bg-lighter); cursor: pointer; flex-shrink: 0; display: flex; align-items: center; justify-content: center; user-select: none; border-right: 1px solid var(--lc-border); color: var(--lc-text-dim); font-size: 12px; }
#sidebar-toggle:hover { background: var(--lc-splitter-hover); color: #fff; }
#sidebar-header { padding: 10px 15px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; background: var(--lc-bg-lighter); }
#sidebar-header span { font-weight: bold; font-size: 11px; color: #aaa; letter-spacing: 1px; text-transform: uppercase; }
#sidebar-header .actions { display: flex; gap: 8px; }
#sidebar-header button { background: none; border: none; color: #aaa; cursor: pointer; font-size: 14px; }
#sidebar-header button:hover { color: #fff; }

#file-tree { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 5px 0; }
.tree-item { display: flex; align-items: center; padding: 4px 8px; cursor: pointer; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-radius: 3px; margin: 1px 5px; }
.tree-item:hover { background: #2a2d2e; }
.tree-item.active { background: #37373d; color: #fff; }
.tree-item.folder::before { content: '📁'; margin-right: 6px; font-size: 12px; }
.tree-item.folder.open::before { content: '📂'; }
.tree-item.file::before { content: '📄'; margin-right: 6px; font-size: 12px; }
.exclamation { color: #ff8c00; margin-left: auto; font-weight: bold; font-size: 14px; }

#editor-container { flex: 1; display: flex; flex-direction: column; background: var(--lc-bg); position: relative; min-width: 200px; }

#repl-panel { width: 400px; min-width: 200px; max-width: 700px; background: var(--lc-repl-bg); border-left: 1px solid #333; display: flex; flex-direction: column; font-family: 'Consolas', monospace; flex-shrink: 0; }
#repl-panel.collapsed { display: none; }
#repl-header { background: #1a1a1a; padding: 5px 10px; font-size: 12px; color: var(--lc-repl-text); display: flex; justify-content: space-between; border-bottom: 1px solid #333; cursor: pointer; user-select: none; }
#repl-header:hover { background: #222; }
#repl-header .repl-actions { display: flex; gap: 8px; align-items: center; }
#repl-header .repl-actions button { background: none; border: none; color: var(--lc-repl-text); cursor: pointer; font-size: 12px; padding: 2px 6px; }
#repl-header .repl-actions button:hover { background: #333; border-radius: 2px; }
#repl-content { flex: 1; overflow-y: auto; padding: 10px; font-size: 12px; color: var(--lc-repl-text); white-space: pre-wrap; }

#editor-toolbar { height: 35px; background: var(--lc-bg-lighter); border-bottom: 1px solid var(--lc-border); display: flex; align-items: center; padding: 0 8px; gap: 6px; }
.tool-btn { background: #3e3e42; border: 1px solid var(--lc-border-light); color: #ccc; padding: 4px 10px; cursor: pointer; font-size: 11px; border-radius: 3px; display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.tool-btn:hover { background: #4e4e52; color: #fff; }
.tool-btn.primary { background: var(--lc-accent); border-color: var(--lc-accent-hover); color: #fff; }
.tool-btn.primary:hover { background: var(--lc-accent-hover); }
.tool-btn.icon-only { padding: 4px 6px; font-size: 14px; border: none; background: transparent; }
.tool-btn.icon-only:hover { background: #3e3e42; }

#bell-btn { position: relative; margin-left: auto; cursor: pointer; font-size: 18px; color: #aaa; padding: 5px; }
#bell-btn:hover { color: #fff; }
#bell-badge { position: absolute; top: 2px; right: 2px; background: #f44336; color: white; border-radius: 50%; padding: 2px 5px; font-size: 9px; display: none; }

#notification-panel { display: none; position: absolute; top: 40px; right: 10px; width: 300px; max-height: 400px; background: #252526; border: 1px solid #454545; box-shadow: 0 4px 15px rgba(0,0,0,0.5); z-index: 200; flex-direction: column; border-radius: 4px; }
#notification-panel.show { display: flex; }
#notification-panel-header { padding: 10px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: bold; }
#notification-panel-list { flex: 1; overflow-y: auto; padding: 5px 0; }
.notify-item { padding: 8px 12px; font-size: 12px; border-bottom: 1px solid #2d2d2d; display: flex; justify-content: space-between; align-items: center; }
.notify-item:hover { background: #2a2d2e; }
.notify-item .path { color: #ff8c00; cursor: pointer; text-decoration: underline; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px; }

#editor-area { flex: 1; }

#diff-panel { display: none; position: absolute; top: 35px; left: 0; right: 0; bottom: 0; background: var(--lc-bg); z-index: 150; flex-direction: column; }
#diff-panel.show { display: flex; }
#diff-header { padding: 8px 15px; background: #333; font-size: 12px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #444; flex-shrink: 0; }
#diff-editor { flex: 1; }

#status-bar { height: 22px; background: var(--lc-accent); color: #fff; font-size: 11px; display: flex; align-items: center; padding: 0 12px; justify-content: space-between; flex-shrink: 0; }
#status-bar span { white-space: nowrap; }

#history-selector { background: #3e3e42; color: #fff; border: 1px solid #555; font-size: 11px; padding: 2px 5px; border-radius: 2px; outline: none; }

</style>
</head>
<body>
<div id="notification-bar">
    <div class="notify-msg" id="notify-text">📢 偵測到外部變更</div>
    <div class="notify-actions">
        <button onclick="viewDiff()">📊 檢視差異</button>
        <button onclick="reloadFile()">🔄 重新載入</button>
        <button onclick="hideNotification()">✕ 關閉</button>
    </div>
</div>
<div id="main">
    <div id="sidebar">
        <div id="sidebar-header">
            <span>EXPLORER</span>
            <div class="actions">
                <button onclick="refreshTree()" title="重新整理">🔄</button>
            </div>
        </div>
        <div id="file-tree"></div>
    </div>
    <div id="sidebar-toggle" onclick="toggleSidebar()" title="切換側邊欄">◀</div>
    <div class="splitter-v" id="splitter-sidebar"></div>
    <div id="editor-container">
        <div id="editor-toolbar">
            <button class="tool-btn primary" onclick="saveFile()">💾 儲存</button>
            <button class="tool-btn" onclick="viewDiff()">🔍 比較</button>
            <button class="tool-btn" onclick="runSelfReview()" style="background:#2d5a27;border-color:#3a7a33;">🩺 自我診斷</button>
            <button class="tool-btn" onclick="toggleRepl()" id="repl-toolbar-btn" style="background:#1a3a5c;border-color:#2a5a8c;" title="切換 REPL 終端">📟 REPL</button>
            <span id="current-file-name" style="font-size:12px; color:var(--lc-text-dim); margin-left:6px;">尚未選擇檔案</span>
            <div id="bell-btn" onclick="toggleNotificationPanel()" title="異動通知" style="margin-left:auto;">
                🔔<span id="bell-badge">0</span>
            </div>
        </div>
        <div id="editor-area"></div>
        <div id="notification-panel">
            <div id="notification-panel-header">
                <span>🔔 異動通知中心</span>
                <button class="tool-btn" style="padding: 2px 6px;" onclick="clearAllNotifications()">全部清除</button>
            </div>
            <div id="notification-panel-list"></div>
        </div>
        <div id="diff-panel">
            <div id="diff-header">
                <div>
                    <span>📊 差異比對 (左: </span>
                    <select id="history-selector" onchange="changeHistoryVersion()"></select>
                    <span> | 右: 磁碟現狀 - <b style="color:#4caf50">可編輯</b>)</span>
                </div>
                <button style="background:none; border:none; color:#aaa; cursor:pointer; font-size:16px;" onclick="closeDiff()">✕</button>
            </div>
            <div id="diff-editor"></div>
        </div>
    </div>
    <div class="splitter-v" id="splitter-repl"></div>
    <div id="repl-panel">
        <div id="repl-header" onclick="toggleRepl()" title="點擊收合/展開">
            <span>📟 CODEWHALE REPL TERMINAL</span>
            <div class="repl-actions">
                <span id="repl-status" style="font-size:10px;">● ONLINE</span>
                <button onclick="event.stopPropagation(); toggleRepl()" title="收合面板">▼</button>
            </div>
        </div>
        <div id="repl-content"></div>
    </div>
</div>
<div id="status-bar">
    <span id="status-text">準備就緒</span>
    <span id="file-info">Live Code Studio v4.1</span>
</div>

<script>
let editor, diffEditor, currentFile = null, modifiedFiles = {}, fileHistory = [];
let treeData = {};
let splitterState = null;

function initSplitters() {
    const sidebar = document.getElementById('sidebar');
    const repl = document.getElementById('repl-panel');
    const splitterS = document.getElementById('splitter-sidebar');
    const splitterR = document.getElementById('splitter-repl');
    
    function makeDraggable(splitter, getEl, storageKey, minW, maxW) {
        splitter.addEventListener('mousedown', (e) => {
            e.preventDefault();
            const el = getEl();
            splitterState = { el, startX: e.clientX, startW: el.offsetWidth, minW, maxW, storageKey };
            splitter.classList.add('active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        });
    }
    
    makeDraggable(splitterS, () => sidebar, 'lc_sidebar_width', 160, 500);
    makeDraggable(splitterR, () => repl, 'lc_repl_width', 200, 700);
}

document.addEventListener('mousemove', (e) => {
    if (!splitterState) return;
    const { el, startX, startW, minW, maxW, storageKey } = splitterState;
    const newW = Math.max(minW, Math.min(maxW, startW + (e.clientX - startX)));
    el.style.width = newW + 'px';
    if (editor) editor.layout();
    if (diffEditor) diffEditor.layout();
});

document.addEventListener('mouseup', () => {
    if (!splitterState) return;
    localStorage.setItem(splitterState.storageKey, splitterState.el.offsetWidth);
    document.getElementById('splitter-sidebar').classList.remove('active');
    document.getElementById('splitter-repl').classList.remove('active');
    splitterState = null;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
});

function restoreLayout() {
    const sw = localStorage.getItem('lc_sidebar_width');
    const rw = localStorage.getItem('lc_repl_width');
    if (sw) document.getElementById('sidebar').style.width = sw + 'px';
    if (rw) document.getElementById('repl-panel').style.width = rw + 'px';
}

function toggleRepl() {
    const panel = document.getElementById('repl-panel');
    const splitter = document.getElementById('splitter-repl');
    const btn = document.getElementById('repl-toolbar-btn');
    if (panel.classList.contains('collapsed')) {
        panel.classList.remove('collapsed');
        panel.style.width = (localStorage.getItem('lc_repl_width') || '400') + 'px';
        splitter.style.display = '';
        if (btn) btn.style.background = '#1a3a5c';
    } else {
        localStorage.setItem('lc_repl_width', panel.offsetWidth);
        panel.classList.add('collapsed');
        splitter.style.display = 'none';
        if (btn) btn.style.background = '#3a1a1a';
    }
    setTimeout(() => { if (editor) editor.layout(); }, 300);
}

require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });
require(['vs/editor/editor.main'], function() {
    editor = monaco.editor.create(document.getElementById('editor-area'), {
        value: '', language: 'python', theme: 'vs-dark', automaticLayout: true,
        fontSize: 14, minimap: { enabled: true }, scrollBeyondLastLine: false
    });
    
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveFile);
    
    diffEditor = monaco.editor.createDiffEditor(document.getElementById('diff-editor'), {
        theme: 'vs-dark', automaticLayout: true, readOnly: false, renderSideBySide: true
    });
    
    diffEditor.getModifiedEditor().onDidChangeModelContent(() => {
        if (diffEditor.getModel()) {
            const val = diffEditor.getModifiedEditor().getValue();
            editor.setValue(val);
        }
    });

    refreshTree();
    setInterval(refreshTree, 5000);
    setInterval(refreshReplLogs, 2000);
    initSplitters();
    restoreLayout();
});

async function refreshReplLogs() {
    try {
        const res = await fetch('/api/repl_logs');
        const data = await res.json();
        const content = document.getElementById('repl-content');
        const isAtBottom = content.scrollHeight - content.scrollTop <= content.clientHeight + 50;
        if (data.logs.length > 0) {
            content.innerHTML = data.logs.join('<br>');
        }
        if (isAtBottom) content.scrollTop = content.scrollHeight;
    } catch (e) {}
}

let _retryCount = 0;
async function refreshTree() {
    try {
        const res = await fetch('/api/tree');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        modifiedFiles = data.modified;
        renderTree(data.files);
        updateNotificationUI();
        if (currentFile && modifiedFiles[currentFile]) showNotification(currentFile);
        _retryCount = 0;
        document.getElementById('status-text').textContent = '🟢 連線正常';
    } catch (e) {
        _retryCount++;
        if (_retryCount <= 5) {
            document.getElementById('status-text').textContent = '🔄 重連中 (' + _retryCount + '/5)...';
        } else {
            document.getElementById('status-text').textContent = '❌ 失去連線';
        }
    }
}

function updateNotificationUI() {
    const count = Object.keys(modifiedFiles).length;
    const badge = document.getElementById('bell-badge');
    badge.textContent = count;
    badge.style.display = count > 0 ? 'block' : 'none';

    const list = document.getElementById('notification-panel-list');
    if (count === 0) {
        list.innerHTML = '<div style="padding:20px; text-align:center; color:#666; font-size:12px;">暫無異動通知</div>';
        return;
    }
    list.innerHTML = Object.entries(modifiedFiles).map(([path]) => `
        <div class="notify-item">
            <span class="path" onclick="openAndDiff('${path}')" title="${path}">${path}</span>
            <button class="tool-btn" style="padding:2px 5px;" onclick="clearNotify('${path}')">忽略</button>
        </div>
    `).join('');
}

function toggleNotificationPanel() {
    document.getElementById('notification-panel').classList.toggle('show');
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebar-toggle');
    const splitter = document.getElementById('splitter-sidebar');
    if (sidebar.classList.contains('collapsed')) {
        sidebar.classList.remove('collapsed');
        sidebar.style.width = (localStorage.getItem('lc_sidebar_width') || '260') + 'px';
        splitter.style.display = '';
        toggle.innerHTML = '◀';
    } else {
        localStorage.setItem('lc_sidebar_width', sidebar.offsetWidth);
        sidebar.classList.add('collapsed');
        splitter.style.display = 'none';
        toggle.innerHTML = '▶';
    }
    setTimeout(() => { if (editor) editor.layout(); if (diffEditor) diffEditor.layout(); }, 300);
}

async function clearNotify(path) {
    await fetch('/api/clear_notify/' + encodeURIComponent(path));
    refreshTree();
}

async function clearAllNotifications() {
    await fetch('/api/clear_notify/all');
    refreshTree();
    document.getElementById('notification-panel').classList.remove('show');
}

function openAndDiff(path) {
    openFile(path).then(() => {
        viewDiff();
        document.getElementById('notification-panel').classList.remove('show');
    });
}

function renderTree(files) {
    const treeRoot = document.getElementById('file-tree');
    const oldScroll = treeRoot.scrollTop;
    const root = {};
    files.forEach(path => {
        const parts = path.split('/');
        let current = root;
        parts.forEach((part, i) => {
            if (i === parts.length - 1) current[part] = { __file: path };
            else { if (!current[part]) current[part] = {}; current = current[part]; }
        });
    });

    const buildHTML = (obj, level = 0) => {
        let html = '';
        const keys = Object.keys(obj).sort((a, b) => {
            const aIsFile = !!obj[a].__file;
            const bIsFile = !!obj[b].__file;
            if (aIsFile !== bIsFile) return aIsFile ? 1 : -1;
            return a.localeCompare(b);
        });
        keys.forEach(key => {
            const isFile = !!obj[key].__file;
            const fullPath = isFile ? obj[key].__file : '';
            const isModified = isFile && modifiedFiles[fullPath];
            const isActive = fullPath === currentFile;
            if (isFile) {
                html += `<div class="tree-item file ${isActive ? 'active' : ''}" style="padding-left: ${level * 15 + 10}px" onclick="openFile('${fullPath}')">
                    ${key} ${isModified ? '<span class="exclamation">❗</span>' : ''}
                </div>`;
            } else {
                const folderId = `folder-${level}-${key}`;
                const isOpen = treeData[folderId] === true;
                html += `<div class="tree-item folder ${isOpen ? 'open' : ''}" style="padding-left: ${level * 15 + 10}px" onclick="toggleFolder('${folderId}')">${key}</div>`;
                html += `<div id="${folderId}" style="display: ${isOpen ? 'block' : 'none'}">${buildHTML(obj[key], level + 1)}</div>`;
            }
        });
        return html;
    };
    treeRoot.innerHTML = buildHTML(root);
    treeRoot.scrollTop = oldScroll;
}

function toggleFolder(id) {
    const el = document.getElementById(id);
    const item = el.previousElementSibling;
    if (el.style.display === 'none') { el.style.display = 'block'; item.classList.add('open'); treeData[id] = true; }
    else { el.style.display = 'none'; item.classList.remove('open'); treeData[id] = false; }
}

async function openFile(path) {
    currentFile = path;
    document.getElementById('current-file-name').textContent = path;
    try {
        const res = await fetch('/api/read/' + encodeURIComponent(path));
        const data = await res.json();
        editor.setValue(data.content);
        fileHistory = data.history || [];

        const ext = path.split('.').pop();
        let lang = 'plaintext';
        if (ext === 'py') lang = 'python';
        else if (ext === 'json') lang = 'json';
        else if (ext === 'js') lang = 'javascript';
        else if (ext === 'html') lang = 'html';
        monaco.editor.setModelLanguage(editor.getModel(), lang);
        document.getElementById('status-text').textContent = '📄 ' + path;
        hideNotification();
        closeDiff();
        fetch('/api/clear_notify/' + encodeURIComponent(path));
        refreshTree();
    } catch (e) { document.getElementById('status-text').textContent = '❌ 讀取失敗'; }
}

async function saveFile() {
    if (!currentFile) return;
    const content = editor.getValue();
    try {
        const res = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: currentFile, content: content })
        });
        if (res.ok) {
            document.getElementById('status-text').textContent = '✅ 已儲存';
            hideNotification();
            refreshTree();
        }
    } catch (e) { alert('儲存失敗'); }
}

function showNotification(f) {
    document.getElementById('notify-text').textContent = `📢 檔案 "${f}" 在磁碟上已更新！`;
    document.getElementById('notification-bar').classList.add('show');
}
function hideNotification() { document.getElementById('notification-bar').classList.remove('show'); }

async function viewDiff() {
    const diffPanel = document.getElementById('diff-panel');
    if (diffPanel.classList.contains('show')) { closeDiff(); return; }
    if (!currentFile) return;
    try {
        const res = await fetch('/api/diff/' + encodeURIComponent(currentFile));
        const data = await res.json();
        fileHistory = data.history || [];
        
        const selector = document.getElementById('history-selector');
        selector.innerHTML = fileHistory.map((v, i) => 
            `<option value="${i}" ${i === 0 ? 'selected' : ''}>歷史版本 ${v.timestamp}${i === 0 ? ' (初始)' : ''}</option>`
        ).join('');
        
        updateDiffEditor(0, data.disk_content);
        
        diffPanel.classList.add('show');
        document.getElementById('status-text').textContent = '📊 正在檢視差異 (右側可編輯)';
        setTimeout(() => { diffEditor.layout(); }, 50);
    } catch (e) {
        console.error(e);
        alert('無法獲取差異數據');
    }
}

function changeHistoryVersion() {
    const index = document.getElementById('history-selector').value;
    const diskContent = editor.getValue(); // 這裡用當前編輯器的內容作為右側
    updateDiffEditor(index, diskContent);
}

function updateDiffEditor(historyIndex, diskContent) {
    const ext = currentFile.split('.').pop();
    let lang = 'python';
    if (ext === 'js') lang = 'javascript';
    else if (ext === 'json') lang = 'json';
    else if (ext === 'html') lang = 'html';

    const baseContent = fileHistory[historyIndex] ? fileHistory[historyIndex].content : diskContent;
    const originalModel = monaco.editor.createModel(baseContent, lang);
    const modifiedModel = monaco.editor.createModel(diskContent, lang);
    
    diffEditor.setModel({
        original: originalModel,
        modified: modifiedModel
    });
}

function closeDiff() { 
    document.getElementById('diff-panel').classList.remove('show'); 
    if (editor) editor.layout();
}
function reloadFile() { if(currentFile) openFile(currentFile); }

async function runSelfReview() {
    document.getElementById('status-text').textContent = '🩺 正在自我診斷...';
    try {
        const res = await fetch('/api/self_review', { method: 'POST' });
        const data = await res.json();
        if (data.error) {
            alert('診斷失敗: ' + data.error);
            document.getElementById('status-text').textContent = '❌ 診斷失敗';
            return;
        }
        const total = data.total || 0;
        const high = data.high || [];
        const medium = data.medium || [];
        const low = data.low || [];
        let report = '';
        // Phase 0: .alice/ 自檢摘要
        if (data.phase0) {
            const p0 = data.phase0;
            report += '📋 Phase 0：「讀資訊、看進度、懂需求」.alice/ 自檢\\n';
            report += '─'.repeat(50) + '\\n';
            report += '📌 讀資訊 (FACTS.md): ' + (p0.summary.facts_loaded ? '✅ 已載入' : '❌ 未找到') + '\\n';
            if (p0.summary.boundary_checks && p0.summary.boundary_checks.length > 0) {
                p0.summary.boundary_checks.forEach(c => report += '   ' + c + '\\n');
            }
            report += '📌 看進度 (TASK_BOARD.md): ' + (p0.summary.taskboard_loaded ? '✅ 已載入' : '❌ 未找到') + '\\n';
            if (p0.summary.tasks_in_progress !== undefined) {
                report += '   🔧 進行中: ' + p0.summary.tasks_in_progress + ' 項 | ⬜ 待開發: ' + p0.summary.tasks_pending + ' 項\\n';
            }
            report += '📌 懂需求 (LOG.md): ' + (p0.summary.log_loaded ? '✅ 已載入' : '❌ 未找到') + '\\n';
            if (p0.summary.recent_log_entries && p0.summary.recent_log_entries.length > 0) {
                report += '   近期變更:\\n';
                p0.summary.recent_log_entries.forEach(e => report += '   📝 ' + e + '\\n');
            }
            if (p0.issues && p0.issues.length > 0) {
                report += '\\n⚠️ .alice/ 問題:\\n';
                p0.issues.forEach(i => report += '   🟡 [' + i.file + '] ' + i.description + '\\n      → ' + i.suggestion + '\\n');
            }
            report += '\\n';
        }
        report += `🩺 自我診斷報告（掃描 ${data.files_scanned || '?'} 檔案，發現 ${total} 個問題）\\n\\n`;
        if (high.length > 0) {
            report += `🔴 高優先 (${high.length})\\n`;
            high.forEach((h, i) => report += `  ${i+1}. [${h.file}] ${h.description}\\n     → ${h.suggestion}\\n`);
            report += '\\n';
        }
        if (medium.length > 0) {
            report += `🟡 中優先 (${medium.length})\\n`;
            medium.forEach((m, i) => report += `  ${i+1}. [${m.file}] ${m.description}\\n     → ${m.suggestion}\\n`);
            report += '\\n';
        }
        if (low.length > 0) {
            report += `🟢 低優先 (${low.length})\\n`;
            low.forEach((l, i) => report += `  ${i+1}. [${l.file}] ${l.description}\\n     → ${l.suggestion}\\n`);
            report += '\\n';
        }
        // Phase 4: 需求備忘錄
        if (data.phase4) {
            const p4 = data.phase4;
            report += '\\n📋 Phase 4：需求備忘錄（REQUIREMENTS.md）\\n';
            report += '─'.repeat(50) + '\\n';
            if (p4.summary.requirements_loaded) {
                report += '📌 核心需求清單:\\n';
                if (p4.summary.core_requirements && p4.summary.core_requirements.length > 0) {
                    p4.summary.core_requirements.forEach(r => report += `   ${r}\\n`);
                } else {
                    report += '   (無核心需求條目)\\n';
                }
            } else {
                report += '⚠️ REQUIREMENTS.md 不存在，請建立需求備忘錄\\n';
            }
            if (p4.issues && p4.issues.length > 0) {
                report += '\\n⚠️ Phase 4 問題:\\n';
                p4.issues.forEach(i => report += `   🟡 [${i.file}] ${i.description}\\n      → ${i.suggestion}\\n`);
            }
            report += '\\n';
        }
        if (total === 0 && (!data.phase4 || !data.phase4.issues || data.phase4.issues.length === 0)) report += '✅ 未發現明顯問題，系統健康！';
        editor.setValue(report);
        monaco.editor.setModelLanguage(editor.getModel(), 'plaintext');
        document.getElementById('current-file-name').textContent = '🩺 自我診斷報告';
        const p4Count = (data.phase4 && data.phase4.issues) ? data.phase4.issues.length : 0;
        document.getElementById('status-text').textContent = `✅ 診斷完成：${total} 個問題（🔴${high.length} 🟡${medium.length} 🟢${low.length}）+ Phase4 ${p4Count} 項`;
    } catch (e) {
        alert('診斷請求失敗: ' + e.message);
        document.getElementById('status-text').textContent = '❌ 診斷請求失敗';
    }
}
</script>
</body>
</html>"""

def _start_server(force=False):
    global _server_instance, _server_thread
    if is_port_in_use(PORT):
        if not force: return False, f"Port {PORT} 已被佔用。"
        if _server_instance:
            try:
                _server_instance.shutdown()
                _server_instance.server_close()
            except: pass
            _server_instance = None
    if _server_instance: return True, f"http://localhost:{PORT}"
    global _file_metadata
    _file_metadata = _scan_files(full_scan=True)
    threading.Thread(target=_detect_changes, daemon=True).start()
    try:
        _server_instance = HTTPServer(("0.0.0.0", PORT), LiveCodeStudioHandler)
        _server_thread = threading.Thread(target=_server_instance.serve_forever, daemon=True)
        _server_thread.start()
        return True, f"http://localhost:{PORT}"
    except Exception as e:
        return False, str(e)

try:
    from skills.base_skill import BaseSkill
except ImportError:
    from base_skill import BaseSkill

class LiveCodeStudioSkill(BaseSkill):
    @property
    def name(self) -> str: return "live_code_studio_skill"
    def get_tool_declarations(self):
        return [{
            "name": "start_live_code_studio",
            "description": "啟動 Live Code Studio v4.0 (實裝多版本歷史比對功能)",
            "parameters": {
                "type": "object",
                "properties": {
                    "force": {"type": "boolean", "description": "是否強制重啟"}
                }
            }
        }]
    def execute(self, tool_name: str, parameters: dict, context: dict) -> dict:
        if tool_name == "start_live_code_studio":
            force = parameters.get("force", True)
            success, result = _start_server(force=force)
            if success:
                webbrowser.open(result)
                return {"status": "success", "message": f"Live Code Studio v4.0 已啟動：{result}", "url": result}
            else:
                return {"status": "error", "message": result}
        return {"status": "error", "message": f"未知工具: {tool_name}"}
