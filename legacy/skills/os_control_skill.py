import time
import subprocess
from base_skill import BaseSkill
from config import logger

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

class OSControlSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "os_control_skill"

    def get_tool_declarations(self) -> list:
        # 動態提供解析度資訊幫助 AI
        w, h = 1920, 1080 
        if pyautogui: 
            w, h = pyautogui.size()
            
        return [
            {
                "name": "os_management",
                "description": "電腦視窗管理與進階系統分析。用於獲取視窗情報與控制，使後續的點擊精準無比。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "動作類型: 'get_active_window' (取得現在正在看哪個視窗), 'list_windows' (列出所有正在運行的程式), 'focus_window' (將某個程式拉到最上層)"
                        },
                        "window_title": {
                            "type": "string",
                            "description": "當 action='focus_window' 時，填寫視窗標題名稱或關鍵字"
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "computer_control",
                "description": "操控滑鼠與鍵盤。⚠️【極致精準指南】必須使用『相對座標 0~1000』！例如畫面最左上為(0,0)，正中央(500,500)，最右下為(1000,1000)。Gemini能極精準定位0~1000的區間。⚠️若需開啟網頁或程式，請優先使用 action='open_app', text='chrome https://youtube.com'，或 action='hotkey', key_name='win,r' 再輸入，這是大腦操控系統最穩定的方式！",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "動作: 'click', 'double_click', 'type', 'key_press', 'hotkey', 'scroll', 'open_app'"
                        },
                        "text": {
                            "type": "string",
                            "description": "當 action='type' 欲輸入之文字。當 action='open_app' 時可填入指令(如 'chrome https://youtube.com')"
                        },
                        "key_name": {
                            "type": "string",
                            "description": "當 action='key_press'或'hotkey'時。例如 'enter', 'esc'，或複合鍵如 'win,r', 'ctrl,v'"
                        },
                        "x_1000": {
                            "type": "integer",
                            "description": "X 座標比例 (0~1000)。由左至右。"
                        },
                        "y_1000": {
                            "type": "integer",
                            "description": "Y 座標比例 (0~1000)。由上至下。"
                        }
                    },
                    "required": ["action"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name == "os_management":
            return self._execute_os_management(args)
        elif function_name == "computer_control":
            return self._execute_control(args, context)
        return {"error": "Unknown function"}

    def _set_clipboard(self, text: str) -> bool:
        """使用 ctypes 直接操作 Windows 剪貼簿，繞過 IME 問題。"""
        try:
            import ctypes
            CF_UNICODETEXT = 13
            # 打開剪貼簿
            if not ctypes.windll.user32.OpenClipboard(None):
                return False
            # 清空剪貼簿
            ctypes.windll.user32.EmptyClipboard()
            # 編碼為 UTF-16 (Windows 預設)
            data = text.encode('utf-16le') + b'\x00\x00'
            # 分配全局記憶體 (GHND = 0x0042)
            h_global_mem = ctypes.windll.kernel32.GlobalAlloc(0x0042, len(data))
            # 鎖定記憶體並寫入
            lp_global_mem = ctypes.windll.kernel32.GlobalLock(h_global_mem)
            ctypes.memmove(lp_global_mem, data, len(data))
            ctypes.windll.kernel32.GlobalUnlock(h_global_mem)
            # 設定剪貼簿數據
            ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, h_global_mem)
            # 關閉剪貼簿
            ctypes.windll.user32.CloseClipboard()
            return True
        except Exception as e:
            logger.error(f"Clipboard Error: {e}")
            return False

    def _execute_os_management(self, args: dict) -> dict:
        action = args.get("action", "").lower()
        
        if not gw:
            return {"error": "Missing Module", "message": "高級視窗功能需要安裝 pygetwindow 套件。請使用者 pip install pygetwindow"}
            
        if action == "get_active_window":
            try:
                win = gw.getActiveWindow()
                if win:
                    return {
                        "status": "success", 
                        "window": {"title": win.title, "left": win.left, "top": win.top, "width": win.width, "height": win.height}
                    }
                return {"status": "success", "message": "查無活躍視窗，可能在桌面上。"}
            except Exception as e:
                return {"error": str(e)}

        elif action == "list_windows":
            try:
                titles = [w for w in gw.getAllTitles() if w.strip()]
                return {"status": "success", "windows": titles[:20]}
            except Exception as e:
                return {"error": str(e)}
                
        elif action == "focus_window":
            target = args.get("window_title", "").lower()
            try:
                windows = gw.getWindowsWithTitle(target)
                if len(windows) > 0:
                    win = windows[0]
                    win.activate()
                    time.sleep(0.5)
                    return {"status": "success", "message": f"已經聚焦到: {win.title}"}
                return {"error": "Not Found", "message": f"找不到包含 '{target}' 的視窗"}
            except Exception as e:
                return {"error": str(e)}

        return {"error": "Unknown Action", "message": f"不支援: {action}"}

    def _execute_control(self, args: dict, context: dict) -> dict:
        if not pyautogui:
            return {"error": "Missing Module", "message": "請主人安裝 pyautogui 套件。"}

        try:
            action = args.get("action", "").lower().strip()
            
            # 1. 點擊邏輯
            if action in ["click", "double_click"]:
                # 優先使用相對座標，這是 Gemini 視覺模型最精準的方式
                x_1k = args.get("x_1000")
                y_1k = args.get("y_1000")
                
                # 若還有舊版的 x, y 參數，也嘗試支援
                raw_x = args.get("x")
                raw_y = args.get("y")
                
                sys_w, sys_h = pyautogui.size()
                
                target_x, target_y = None, None
                
                if x_1k is not None and y_1k is not None:
                    target_x = int((x_1k / 1000.0) * sys_w)
                    target_y = int((y_1k / 1000.0) * sys_h)
                    logger.info(f"🎯 絕對比例轉換 0~1000: Gemini[ {x_1k}, {y_1k} ] -> 系統坐標({target_x}, {target_y})")
                    
                elif raw_x is not None and raw_y is not None:
                    scale_x = context.get("scale_x", 1.0)
                    scale_y = context.get("scale_y", 1.0)
                    target_x = int(raw_x * scale_x)
                    target_y = int(raw_y * scale_y)
                    logger.info(f"🎯 像素座標轉換: 原圖({raw_x}, {raw_y}) -> 視窗({target_x}, {target_y})")

                if target_x is not None and target_y is not None:
                    target_x = max(0, min(target_x, sys_w - 1))
                    target_y = max(0, min(target_y, sys_h - 1))
                    pyautogui.moveTo(target_x, target_y, duration=0.4)
                
                if action == "double_click":
                    pyautogui.doubleClick()
                else:
                    pyautogui.click()
                return {"status": "success", "message": "已成功點擊目標！"}

            # 2. 文字輸入 (優化版：使用剪貼簿繞過 IME)
            elif action == "type":
                text = args.get("text", "")
                if not text: return {"error": "Missing Text"}
                
                # 嘗試使用剪貼簿貼上
                if self._set_clipboard(text):
                    pyautogui.hotkey('ctrl', 'v')
                    logger.info(f"📋 已透過剪貼簿貼上文字 (繞過 IME): {text[:20]}...")
                    return {"status": "success", "message": f"已透過貼上輸入: {text}"}
                else:
                    # 備援方案：原始打字
                    pyautogui.write(text, interval=0.05)
                    return {"status": "success", "message": f"剪貼簿失敗，改用原始輸入: {text}"}

            # 3. 組合鍵或單一按鍵
            elif action == "hotkey":
                key_name = args.get("key_name", "")
                if not key_name: return {"error": "Missing Key"}
                keys = [k.strip() for k in key_name.split(',')]
                pyautogui.hotkey(*keys)
                return {"status": "success", "message": f"已觸發組合鍵: {key_name}"}

            elif action == "key_press":
                key_name = args.get("key_name", "")
                if not key_name: return {"error": "Missing Key"}
                if key_name.lower() in ["return", "enter"]: key_name = "enter"
                pyautogui.press(key_name)
                return {"status": "success", "message": f"已按下: {key_name}"}

            # 4. 滾動操作
            elif action == "scroll":
                amount = args.get("y", -500)
                if abs(amount) < 10: amount = -500
                pyautogui.scroll(amount)
                return {"status": "success", "message": f"已捲動 ({amount})"}

            # 5. 開啟程式或網頁
            elif action == "open_app":
                app_name = args.get("app_name", "") or args.get("text", "")
                if "chrome " in app_name.lower():
                    subprocess.Popen(f"start {app_name}", shell=True)
                elif "chrome" in app_name.lower():
                    subprocess.Popen("start chrome", shell=True)
                elif "notepad" in app_name.lower() or "記事本" in app_name:
                    subprocess.Popen("notepad", shell=True)
                elif "calc" in app_name.lower() or "小算盤" in app_name:
                    subprocess.Popen("calc", shell=True)
                else:
                    subprocess.Popen(f"start {app_name}", shell=True)
                time.sleep(2.0)
                return {"status": "success", "message": f"已嘗試開啟: {app_name}"}

            else:
                return {"error": "Unknown Action"}

        except Exception as e:
            logger.error(f"Control Error: {e}")
            return {"error": "Execution Failed", "message": str(e)}
