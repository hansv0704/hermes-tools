"""
n8n Server Skill — 完全對標 Live Code Studio 的獨立伺服器架構
- 獨立埠號 5678
- 獨立 Web UI（n8n 原生編輯器）
- 一行啟動（npx n8n start）
- Alice 透過工具操控生命週期
"""

import os
import sys
import time
import socket
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any, List

# ─── BaseSkill 雙重匯入（相容 tools.py 的 sys.path）───
try:
    from skills.base_skill import BaseSkill
except ImportError:
    from base_skill import BaseSkill


BASE_DIR = Path(__file__).resolve().parent.parent
PORT = 5678
N8N_PROCESS: Optional[subprocess.Popen] = None


# ─── 工具函式 ─────────────────────────────────────────────

def is_port_in_use(port: int) -> bool:
    """檢查埠號是否已被佔用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def _check_npx_available() -> bool:
    """檢查 npx 是否可用"""
    return shutil.which('npx') is not None


def _check_node_available() -> bool:
    """檢查 Node.js 是否可用"""
    return shutil.which('node') is not None


def _get_n8n_data_dir() -> Path:
    """取得 n8n 資料目錄（存放工作流、認證等）"""
    data_dir = BASE_DIR / '.n8n'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _start_n8n(force: bool = False) -> Dict[str, Any]:
    """啟動 n8n 伺服器"""
    global N8N_PROCESS

    if not _check_node_available():
        return {
            "status": "error",
            "message": "❌ 未偵測到 Node.js。請先安裝 Node.js：https://nodejs.org/",
            "port": PORT,
            "url": None
        }

    if is_port_in_use(PORT):
        if force:
            _stop_n8n()
            time.sleep(2)
        else:
            return {
                "status": "running",
                "message": f"✅ n8n 已在運行中 → http://localhost:{PORT}",
                "port": PORT,
                "url": f"http://localhost:{PORT}"
            }

    env = os.environ.copy()
    data_dir = _get_n8n_data_dir()
    env['N8N_USER_FOLDER'] = str(data_dir)
    env['N8N_PORT'] = str(PORT)
    env['N8N_HOST'] = 'localhost'
    env['N8N_PROTOCOL'] = 'http'
    env['N8N_DIAGNOSTICS_ENABLED'] = 'false'
    env['N8N_VERSION_NOTIFICATIONS_ENABLED'] = 'false'
    env['N8N_SECURE_COOKIE'] = 'false'

    try:
        N8N_PROCESS = subprocess.Popen(
            ['npx', 'n8n', 'start'],
            env=env,
            cwd=str(data_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ 無法啟動 n8n：{str(e)}",
            "port": PORT,
            "url": None
        }

    url = f"http://localhost:{PORT}"
    for i in range(60):
        time.sleep(1)
        if is_port_in_use(PORT):
            webbrowser.open(url)
            return {
                "status": "started",
                "message": f"✅ n8n 已成功啟動！\n📊 編輯器：{url}\n⏱️ 啟動耗時：{i + 1} 秒",
                "port": PORT,
                "url": url
            }

    return {
        "status": "timeout",
        "message": f"⚠️ n8n 啟動逾時（60 秒）。進程可能仍在背景初始化中，請稍後手動檢查 {url}",
        "port": PORT,
        "url": url
    }


def _stop_n8n() -> Dict[str, Any]:
    """停止 n8n 伺服器"""
    global N8N_PROCESS

    if N8N_PROCESS and N8N_PROCESS.poll() is None:
        N8N_PROCESS.terminate()
        try:
            N8N_PROCESS.wait(timeout=10)
        except subprocess.TimeoutExpired:
            N8N_PROCESS.kill()
            N8N_PROCESS.wait()
        N8N_PROCESS = None

    if sys.platform == 'win32' and is_port_in_use(PORT):
        try:
            result = subprocess.run(
                f'netstat -ano | findstr :{PORT}',
                shell=True, capture_output=True, text=True
            )
            for line in result.stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    subprocess.run(
                        f'taskkill /F /PID {pid}', shell=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
        except Exception:
            pass

    return {
        "status": "stopped",
        "message": f"🛑 n8n 伺服器已停止（Port {PORT} 已釋放）",
        "port": PORT,
        "url": None
    }


def _check_n8n_health() -> Dict[str, Any]:
    """檢查 n8n 運行狀態"""
    global N8N_PROCESS

    port_in_use = is_port_in_use(PORT)
    process_alive = N8N_PROCESS is not None and N8N_PROCESS.poll() is None
    npx_ok = _check_npx_available()
    node_ok = _check_node_available()

    status = "stopped"
    message_parts = []

    if port_in_use and process_alive:
        status = "running"
        message_parts.append(f"✅ n8n 運行中 → http://localhost:{PORT}")
    elif port_in_use and not process_alive:
        status = "orphan"
        message_parts.append(f"⚠️ Port {PORT} 被佔用但非 Alice 啟動的進程")
    elif not port_in_use and process_alive:
        status = "zombie"
        message_parts.append(f"⚠️ n8n 進程存在但 Port {PORT} 未響應")
    else:
        message_parts.append("⭕ n8n 未運行")

    message_parts.append(f"\n🔧 Node.js: {'✅' if node_ok else '❌ 未安裝'}")
    message_parts.append(f"🔧 npx: {'✅' if npx_ok else '❌ 未安裝'}")

    return {
        "status": status,
        "message": "".join(message_parts),
        "port": PORT,
        "port_in_use": port_in_use,
        "process_alive": process_alive,
        "npx_available": npx_ok,
        "node_available": node_ok,
        "url": f"http://localhost:{PORT}" if port_in_use else None
    }


# ─── Skill 類別 ─────────────────────────────────────────────

class N8nServerSkill(BaseSkill):
    """n8n 伺服器生命週期管理 Skill — 對標 LiveCodeStudioSkill"""

    def __init__(self, agent=None):
        super().__init__(agent)

    @property
    def name(self) -> str:
        return "n8n_server_skill"

    def get_tool_declarations(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "start_n8n_server",
                "description": "【一鍵啟動 n8n】啟動 n8n 自動化伺服器，開啟瀏覽器導向編輯器 http://localhost:5678。若已運行則直接回報狀態。支援 force 參數強制重啟。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "force": {
                            "type": "boolean",
                            "description": "是否強制重啟（即使已在運行中）",
                            "default": False
                        }
                    }
                }
            },
            {
                "name": "stop_n8n_server",
                "description": "【停止 n8n】終止 n8n 伺服器進程，釋放 Port 5678。",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "check_n8n_status",
                "description": "【檢查 n8n 狀態】檢查 n8n 伺服器是否運行中、埠號佔用狀態、Node.js / npx 可用性。",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def execute(self, function_name: str, args: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if function_name == "start_n8n_server":
            force = args.get("force", False)
            return _start_n8n(force=force)
        elif function_name == "stop_n8n_server":
            return _stop_n8n()
        elif function_name == "check_n8n_status":
            return _check_n8n_health()
        else:
            return {"status": "error", "message": f"未知的 n8n 操作：{function_name}"}
