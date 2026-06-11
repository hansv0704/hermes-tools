import subprocess
import threading
import queue
import time
import json
import os
import re
import urllib.request
from skills.base_skill import BaseSkill

class CodeWhaleEngineSkill(BaseSkill):
    def __init__(self, agent=None):
        super().__init__(agent=agent)
        self._process = None
        self._output_queue = queue.Queue()
        self._is_running = False
        self._lock = threading.Lock()

    @property
    def name(self):
        return "codewhale_engine_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "repl_execute",
                "description": "【CodeWhale 戰鬥座艙】在長駐 Python 沙盒中執行代碼。變數與導入會保留在記憶體中。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "欲執行的 Python 代碼"},
                        "reset": {"type": "boolean", "description": "是否重置沙盒環境", "default": False}
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "repl_get_status",
                "description": "獲取當前 REPL 沙盒的運行狀態與變數清單。",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    def _ensure_process(self):
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                # 清理舊線程狀態，防止 race condition
                self._is_running = False
                time.sleep(0.1)
                # utf-8 編碼環境，防止 Windows cp950 崩潰
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                self._process = subprocess.Popen(
                    ["python", "-u", "-i"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    env=env,
                    bufsize=1
                )
                self._is_running = True
                threading.Thread(target=self._read_output, daemon=True).start()
                self._log_to_tui("CodeWhale Stateful REPL Engine Started.")

    def _log_to_tui(self, msg: str):
        """透過 HTTP POST 推送日誌至 Live Code Studio"""
        try:
            data = json.dumps({"msg": msg}).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:5001/api/repl_logs_push",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=2)
        except:
            pass

    def _read_output(self):
        while self._is_running and self._process:
            try:
                line = self._process.stdout.readline()
                if line:
                    self._output_queue.put(line)
                else:
                    break
            except (ValueError, OSError):
                break


    async def execute(self, tool_name, args, context=None):
        if tool_name == "repl_execute":
            code = args.get("code")
            reset = args.get("reset", False)
            
            if reset:
                if self._process:
                    self._is_running = False
                    self._process.terminate()
                    self._process = None
                return {"status": "success", "message": "REPL 沙盒已重置。"}

            self._ensure_process()
            
            # 清空之前的輸出佇列
            while not self._output_queue.empty():
                self._output_queue.get()

            # 注入代碼並添加結束哨兵
            sentinel = "___CODEWHALE_DONE___"
            full_code = f"{code}\nprint('{sentinel}')\n"
            
            try:
                self._process.stdin.write(full_code)
                self._process.stdin.flush()
                
                output = []
                start_time = time.time()
                while True:
                    try:
                        line = self._output_queue.get(timeout=1)
                        if sentinel in line:
                            break
                        output.append(line)
                    except queue.Empty:
                        if time.time() - start_time > 10:
                            output.append("Error: 執行超時 (10s)")
                            break
                
                res_msg = "".join(output).strip() or "(No Output)"
                
                # === Phase 1: Traceback 自動偵測 ===
                has_error = False
                error_type = None
                error_message = None
                
                tb_match = re.search(r'Traceback\s*\(most recent call last\):', res_msg)
                if tb_match:
                    lines = res_msg.split('\n')
                    last_line = lines[-1].strip() if lines else ""
                    err_match = re.match(r'^(\w+(?:Error|Exception|Warning|Interrupt|Exit))(.*)', last_line)
                    if err_match:
                        error_type = err_match.group(1)
                        error_message = err_match.group(2).lstrip(': ')
                    elif last_line:
                        error_type = "Unknown"
                        error_message = last_line
                    
                    has_error = True
                    self._log_to_tui(f">> EXECUTE CODE:\n{code}\n[ERROR DETECTED]\n  Type: {error_type}\n  Message: {error_message}\n[FULL OUTPUT]:\n{res_msg}")
                else:
                    self._log_to_tui(f">> EXECUTE CODE:\n{code}\n[RESULT]:\n{res_msg}")
                
                return {
                    "status": "error" if has_error else "success",
                    "has_error": has_error,
                    "error_type": error_type,
                    "error_message": error_message,
                    "output": res_msg,
                    "engine": "CodeWhale-REPL-v2.0-Phase1"
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif tool_name == "repl_get_status":
            status = "Running" if self._process and self._process.poll() is None else "Stopped"
            return {
                "status": "success",
                "repl_status": status,
                "features": ["Stateful", "Sub-agent Ready", "Checklist Integrated"]
            }
        return {"status": "error", "message": f"未知工具: {tool_name}"}
