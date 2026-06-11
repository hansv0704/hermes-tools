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
_repl_logs: List[str] = []

# ═══ v5.0: Hermes 協作追蹤 ═══
_tracked_files: Dict[str, Dict[str, Any]] = {}  # Hermes 註冊的追蹤檔案: rel_path -> {content, workdir, tracked_at}
_workspaces: Dict[str, Dict[str, Any]] = {}     # 工作區: abs_path -> {name, added_at}
_session_workdir: Optional[str] = None          # 當前 session 工作目錄
_session_active: bool = False
_session_started_at: Optional[str] = None

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

# ═══ v5.0: 工作區與追蹤檔案輔助函式 ═══

# v5.3: 持久化工作區設定
WORKSPACE_CONFIG = Path(__file__).parent / "lcs_workspaces.json"

def _load_workspaces() -> dict:
    """從磁碟載入持久化的工作區清單"""
    if WORKSPACE_CONFIG.exists():
        try:
            return json.loads(WORKSPACE_CONFIG.read_text("utf-8"))
        except Exception:
            pass
    return {}

def _save_workspaces():
    """將當前工作區清單寫入磁碟"""
    try:
        with _lock:
            data = dict(_workspaces)
        WORKSPACE_CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    except Exception:
        pass

def _add_workspace(abs_path: str, name: str = None) -> dict:
    """新增監控工作區"""
    p = Path(abs_path).resolve()
    if not p.exists() or not p.is_dir():
        return {"status": "error", "message": f"目錄不存在: {abs_path}"}
    ws_path = str(p)
    with _lock:
        if ws_path in _workspaces:
            return {"status": "ok", "message": "工作區已存在", "path": ws_path}
        _workspaces[ws_path] = {
            "name": name or p.name,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_count": 0
        }
        _workspaces[ws_path]["file_count"] = _scan_workspace_files(ws_path)
    _save_workspaces()
    add_repl_log(f"📂 工作區已新增: {_workspaces[ws_path]['name']} ({ws_path})")
    return {"status": "ok", "path": ws_path, "name": _workspaces[ws_path]["name"]}

def _remove_workspace(abs_path: str) -> dict:
    """移除監控工作區"""
    p = str(Path(abs_path).resolve())
    with _lock:
        if p in _workspaces:
            name = _workspaces[p]["name"]
            del _workspaces[p]
            _save_workspaces()
            add_repl_log(f"📂 工作區已移除: {name}")
            return {"status": "ok", "message": f"已移除: {name}"}
    return {"status": "error", "message": "工作區不存在"}

def _scan_workspace_files(abs_path: str) -> int:
    """掃描工作區檔案並加入 _file_metadata，自動標記近期修改的檔案"""
    extensions = {".py", ".txt", ".json", ".env", ".md", ".bat", ".yaml", ".yml", ".html", ".css", ".js", ".csv", ".xml", ".cfg", ".ini", ".toml"}
    count = 0
    now = time.time()
    recent_threshold = now - 86400  # 24 小時內修改視為「近期變更」
    ws = Path(abs_path)
    for f in ws.rglob("*"):
        try:
            if f.is_file() and f.suffix in extensions:
                parts = f.parts
                if any(p in ("__pycache__", ".git", "node_modules", "backups", "data", ".ipynb_checkpoints", "memory", "logs") for p in parts):
                    continue
                rel = str(f.relative_to(ws).as_posix())
                stat = f.stat()
                content = f.read_text("utf-8", errors="ignore")
                with _lock:
                    _file_metadata[rel] = {
                        "mtime": stat.st_mtime,
                        "size": stat.st_size,
                        "hash": _compute_hash(content),
                        "workspace": abs_path,
                        "workspace_rel": rel
                    }
                    # v5.1: 自動標記近期修改的檔案
                    if stat.st_mtime >= recent_threshold:
                        _modified_files[rel] = "recent_change"
                count += 1
        except Exception:
            continue
    return count

def _track_file(rel_path: str, content: str, workdir: str = None) -> dict:
    """Hermes 註冊追蹤檔案（含內容快照）"""
    with _lock:
        # 保存舊內容作為歷史版本（如果有）
        if rel_path in _tracked_files:
            old_content = _tracked_files[rel_path].get("content", "")
            if old_content != content:
                _add_history(rel_path, old_content)
        
        _tracked_files[rel_path] = {
            "content": content,
            "workdir": workdir or _session_workdir or str(BASE_DIR),
            "tracked_at": datetime.now().strftime("%H:%M:%S"),
            "hash": _compute_hash(content)
        }
        # 加入歷史
        _add_history(rel_path, content)
        # 標記為已修改（觸發前端通知）
        _modified_files[rel_path] = "tracked"
    
    add_repl_log(f"📝 已追蹤: {rel_path}")
    return {"status": "ok", "path": rel_path}

def _untrack_file(rel_path: str) -> dict:
    """取消追蹤檔案"""
    with _lock:
        if rel_path in _tracked_files:
            del _tracked_files[rel_path]
            _modified_files.pop(rel_path, None)
            add_repl_log(f"📝 已取消追蹤: {rel_path}")
            return {"status": "ok", "path": rel_path}
    return {"status": "error", "message": "檔案未被追蹤"}

def _scan_files(full_scan=False) -> Dict[str, Dict[str, Any]]:
    metadata = {}
    extensions = {".py", ".txt", ".json", ".env", ".md", ".bat", ".yaml", ".yml", ".html", ".css", ".js", ".csv", ".xml", ".cfg", ".ini", ".toml"}
    
    # v5.0: 掃描所有工作區 + BASE_DIR
    scan_roots = [(str(BASE_DIR), BASE_DIR)]
    with _lock:
        for ws_path in _workspaces:
            p = Path(ws_path)
            if p.exists():
                scan_roots.append((ws_path, p))
    
    for ws_name, root_path in scan_roots:
        for f in root_path.rglob("*"):
            try:
                if f.is_file() and f.suffix in extensions:
                    rel_path = f.relative_to(root_path)
                    parts = rel_path.parts
                    if any(p in ("__pycache__", ".git", "node_modules", "backups", "data", "temp_sync_workplace", ".ipynb_checkpoints", "memory", "logs") for p in parts):
                        continue
                    rel = str(rel_path.as_posix())
                    stat = f.stat()
                    mtime = stat.st_mtime
                    size = stat.st_size
                    
                    with _lock:
                        old_meta = _file_metadata.get(rel)
                    
                    if not full_scan and old_meta and old_meta["mtime"] == mtime and old_meta["size"] == size:
                        metadata[rel] = old_meta
                    else:
                        try:
                            content = f.read_text("utf-8", errors="ignore")
                            metadata[rel] = {
                                "mtime": mtime,
                                "size": size,
                                "hash": _compute_hash(content)
                            }
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
                    # v5.2: 新檔案也標記為 modified
                    with _lock:
                        _file_metadata[rel_path] = meta
                        _modified_files[rel_path] = "new_file"
                    # 新 .py 檔案也做語法檢查
                    if rel_path.endswith('.py'):
                        full_path = BASE_DIR / rel_path
                        try:
                            content = full_path.read_text("utf-8", errors="ignore")
                            compile(content, rel_path, 'exec')
                            changed_py_files.append((rel_path, content))
                        except SyntaxError as e:
                            with _lock:
                                _modified_files[rel_path] = f"syntax_error: Line {e.lineno}"
                        except Exception:
                            pass
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
            # v5.0: 優先檢查追蹤檔案（記憶體內）
            with _lock:
                if rel_path in _tracked_files:
                    return _tracked_files[rel_path]["content"]
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
                # v5.0: 雙來源 — 追蹤檔案 + 工作區檔案
                tracked = sorted(_tracked_files.keys())
                workspace_files = sorted([
                    k for k in _file_metadata.keys()
                    if k not in _tracked_files
                ])
                modified = dict(_modified_files)
                workspaces = dict(_workspaces)
                session_info = {
                    "active": _session_active,
                    "workdir": _session_workdir,
                    "started_at": _session_started_at
                }
            self._send_json({
                "files": workspace_files,
                "tracked": tracked,
                "modified": modified,
                "workspaces": workspaces,
                "session": session_info
            })
        elif path == "/api/tracked":
            # v5.0: 只回傳追蹤檔案清單
            with _lock:
                tracked = {k: {"workdir": v["workdir"], "tracked_at": v["tracked_at"]} 
                          for k, v in _tracked_files.items()}
            self._send_json({"tracked": tracked})
        elif path == "/api/session/info":
            # v5.0: session 資訊
            with _lock:
                info = {
                    "active": _session_active,
                    "workdir": _session_workdir,
                    "started_at": _session_started_at,
                    "tracked_count": len(_tracked_files),
                    "workspace_count": len(_workspaces)
                }
            self._send_json(info)
        elif path == "/api/workspace/list":
            # v5.0: 工作區列表
            with _lock:
                ws_list = dict(_workspaces)
            self._send_json({"workspaces": ws_list})
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
        # ═══ v5.0: Hermes 協作 API ═══
        if self.path == "/api/session/start":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            workdir = body.get("workdir", str(BASE_DIR))
            global _session_workdir, _session_active, _session_started_at
            _session_workdir = str(Path(workdir).resolve())
            _session_active = True
            _session_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # v5.2: 自動將工作目錄加入監控（全面追蹤）
            # 安全防護：只對 < 5000 檔案的目錄自動掃描
            try:
                file_count = sum(1 for _ in Path(_session_workdir).rglob("*") if _.is_file())
            except Exception:
                file_count = 99999
            if file_count < 5000:
                ws_result = _add_workspace(_session_workdir, name="_hermes_session")
            else:
                ws_result = {"status": "skipped", "message": f"目錄過大 ({file_count} 檔案)，跳過自動掃描"}
            add_repl_log(f"🚀 Session 啟動: {_session_workdir} ({file_count} 檔案)")
            self._send_json({
                "status": "ok",
                "workdir": _session_workdir,
                "started_at": _session_started_at,
                "auto_workspace": ws_result
            })
        elif self.path == "/api/session/stop":
            _session_active = False
            add_repl_log("🛑 Session 結束")
            self._send_json({"status": "ok", "message": "Session 已結束"})
        elif self.path == "/api/files/track":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            rel_path = body.get("path", "")
            content = body.get("content", "")
            workdir = body.get("workdir", None)
            result = _track_file(rel_path, content, workdir)
            self._send_json(result)
        elif self.path == "/api/files/untrack":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            rel_path = body.get("path", "")
            result = _untrack_file(rel_path)
            self._send_json(result)
        elif self.path == "/api/workspace/add":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            result = _add_workspace(body.get("path", ""), body.get("name"))
            self._send_json(result)
        elif self.path == "/api/workspace/remove":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            result = _remove_workspace(body.get("path", ""))
            self._send_json(result)
        # ═══ v4.0 原有 API ═══
        elif self.path == "/api/repl_logs_push":
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
            # v5.0: 優先掃描追蹤檔案 + 工作區 Python 檔案
            code_files = {}
            
            # 1. 追蹤檔案（優先）
            with _lock:
                for rel_path, info in _tracked_files.items():
                    if rel_path.endswith('.py'):
                        code_files[rel_path] = info["content"][:3000]
            
            # 2. 工作區 Python 檔案
            for ws_path in _workspaces:
                ws = Path(ws_path)
                if ws.exists():
                    for f in ws.rglob("*.py"):
                        try:
                            if "__pycache__" not in str(f):
                                rel = str(f.relative_to(ws).as_posix())
                                if rel not in code_files:
                                    code_files[rel] = f.read_text("utf-8", errors="ignore")[:3000]
                        except Exception:
                            pass
            
            # 3. 向後相容：舊 BASE_DIR 的核心檔案
            legacy_dirs = ["skills/", "engines/"]
            for d in legacy_dirs:
                dpath = BASE_DIR / d
                if dpath.exists():
                    for f in dpath.rglob("*.py"):
                        rel = str(f.relative_to(BASE_DIR).as_posix())
                        if "__pycache__" not in rel and rel not in code_files:
                            try:
                                code_files[rel] = f.read_text("utf-8", errors="ignore")[:3000]
                            except Exception:
                                pass
            
            core_files = ["agent.py", "handlers.py", "memory.py", "tools.py"]
            for cf in core_files:
                fpath = BASE_DIR / cf
                if fpath.exists() and cf not in code_files:
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

HTML_TEMPLATE_PATH = Path(__file__).parent / "lcs_template_v5.html"
if HTML_TEMPLATE_PATH.exists():
    HTML_TEMPLATE = HTML_TEMPLATE_PATH.read_text("utf-8")
else:
    HTML_TEMPLATE = """<!DOCTYPE html><html><body><h1>LCS v5.0 — 模板遺失，請建立 lcs_template_v5.html</h1></body></html>"""

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
    
    # v5.3: 啟動時自動載入持久化工作區 + 預設涵蓋 Hermes 常用目錄
    saved = _load_workspaces()
    if saved:
        for ws_path, ws_info in saved.items():
            if Path(ws_path).exists():
                _workspaces[ws_path] = ws_info
                _scan_workspace_files(ws_path)
        add_repl_log(f"📂 已載入 {len(_workspaces)} 個持久化工作區")
    
    # 預設目錄（永久涵蓋，不受 session 影響）
    default_dirs = [
        (str(BASE_DIR), "Alice Legacy"),
        (os.path.expandvars(r"%LOCALAPPDATA%\hermes\skills\alice"), "Hermes Skills"),
    ]
    for d, name in default_dirs:
        if Path(d).exists() and d not in _workspaces:
            _add_workspace(d, name=name)
    
    threading.Thread(target=_detect_changes, daemon=True).start()
    
    # v5.3: 啟動時自動建立預設 Session（不再顯示「未連線」）
    global _session_workdir, _session_active, _session_started_at
    _session_workdir = str(BASE_DIR)
    _session_active = True
    _session_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
