import logging
import threading
import subprocess
import time
import os
import sys
import asyncio
import tempfile
import base64
import importlib.util
import inspect
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Google GenAI SDK
from google import genai
from google.genai import types

try:
    import pyautogui
    pyautogui.FAILSAFE = True 
    from pynput import keyboard
    from PIL import ImageGrab
except ImportError:
    pyautogui = keyboard = ImageGrab = None

try:
    import edge_tts
except ImportError:
    edge_tts = None

from config import logger
# 這裡保留原始導入以維持相容性
try:
    from skills.base_skill import BaseSkill
except ImportError:
    try:
        from base_skill import BaseSkill
    except ImportError:
        BaseSkill = object # Fallback

class TTSManager:
    def __init__(self):
        self.enabled = False
        self.voices = {
            "tw_female": {"engine": "edge", "id": "zh-TW-HsiaoChenNeural"},
            "tw_male":   {"engine": "edge", "id": "zh-TW-YunJheNeural"},
            "cn_female": {"engine": "edge", "id": "zh-CN-XiaoxiaoNeural"},
            "gemini_puck":   {"engine": "gemini", "id": "Puck",   "desc": "活潑 (Puck)"},
            "gemini_zephyr": {"engine": "gemini", "id": "Zephyr", "desc": "溫柔 (Zephyr)"},
            "gemini_fenrir": {"engine": "gemini", "id": "Fenrir", "desc": "低沉 (Fenrir)"}
        }
        self.current_voice = "gemini_puck"
        self.client = None
        self._init_google_client()

    def _init_google_client(self):
        try:
            keys_str = os.getenv("GOOGLE_API_KEYS", "")
            key = keys_str.split(",")[0].strip() if keys_str else os.getenv("API_KEY")
            if key:
                self.client = genai.Client(api_key=key)
        except Exception as e:
            logger.error(f"TTS Client Init Failed: {e}")

    async def generate_audio(self, text, voice_key=None):
        if not text: return None
        voice_key = voice_key or self.current_voice
        voice_config = self.voices.get(voice_key, self.voices["gemini_puck"])
        
        engine = voice_config.get("engine")
        voice_id = voice_config.get("id")

        if engine == "gemini":
            return await self._generate_gemini_audio(text, voice_id)
        else:
            return await self._generate_edge_audio(text, voice_id)

    async def _generate_edge_audio(self, text, voice_id):
        if not edge_tts: return None
        output_file = tempfile.mktemp(suffix=".mp3")
        try:
            communicate = edge_tts.Communicate(text, voice_id, rate="+5%")
            await communicate.save(output_file)
            return output_file
        except Exception as e:
            logger.error(f"EdgeTTS Error: {e}")
            return None

    async def _generate_gemini_audio(self, text, voice_name):
        if not self.client:
            self._init_google_client()
            if not self.client: return None

        output_file = tempfile.mktemp(suffix=".wav")
        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-3.1-flash-tts-preview",
                contents=types.Content(parts=[types.Part(text=text)]),
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                        )
                    )
                )
            )

            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        audio_bytes = part.inline_data.data
                        audio_data = base64.b64decode(audio_bytes) if isinstance(audio_bytes, str) else audio_bytes
                        with open(output_file, "wb") as f:
                            f.write(audio_data)
                        return output_file
            return None
        except Exception as e:
            logger.error(f"GeminiTTS Error: {e}")
            return await self._generate_edge_audio(text, "zh-TW-HsiaoChenNeural")

class ToolManager:
    def __init__(self, agent=None):
        self.agent = agent  # 反向註冊 Agent 實體，在 _load_dynamic_skills 之前設定
        self.safety_lock = True
        self.tts = TTSManager()
        
        self.screen_width = 1920
        self.screen_height = 1080
        self.scale_x = 1.0
        self.scale_y = 1.0
        self._init_screen_metrics()
        
        # Skill Extension Architecture
        self.skills = {}
        self.tool_to_skill_map = {}
        self._load_dynamic_skills()
        
        if keyboard:
            self.listener = keyboard.Listener(on_release=self.on_key_release)
            self.listener.start()
            logger.info("⌨️ F12 緊急開關監聽已啟動")

    def _init_screen_metrics(self):
        if pyautogui and ImageGrab:
            try:
                gui_w, gui_h = pyautogui.size()
                img = ImageGrab.grab() 
                img_w, img_h = img.size
                
                self.screen_width = img_w
                self.screen_height = img_h
                self.scale_x = gui_w / img_w
                self.scale_y = gui_h / img_h
                
                logger.info(f"🖥️ 螢幕校正: 截圖 {img_w}x{img_h} | 系統 {gui_w}x{gui_h}")
            except Exception as e:
                logger.error(f"螢幕偵測失敗: {e}")

    def reload_skills(self):
        """原子化熱重載：先載入到暫存字典，再進行切換，防止載入期間工具遺失"""
        logger.info("🔄 開始原子化熱重載所有擴充技能...")
        new_skills = {}
        new_tool_map = {}
        self._load_dynamic_skills(target_skills=new_skills, target_map=new_tool_map)
        
        # 原子化切換
        self.skills = new_skills
        self.tool_to_skill_map = new_tool_map
        logger.info(f"✅ 熱重載完成！目前可用工具數: {len(self.tool_to_skill_map)}")

    def _load_dynamic_skills(self, target_skills=None, target_map=None):
        # 如果未指定目標，則使用實體屬性（相容舊版呼叫）
        if target_skills is None: target_skills = self.skills
        if target_map is None: target_map = self.tool_to_skill_map

        skills_dir = Path("skills").absolute()
        if not skills_dir.exists():
            return
            
        if str(skills_dir) not in sys.path:
            sys.path.append(str(skills_dir))

        for filepath in skills_dir.rglob("*.py"):
            if filepath.name == "base_skill.py" or filepath.name.startswith("__"):
                continue
            if filepath.name == "github_mcp_skill.py":
                continue
                
            try:
                rel_path = filepath.relative_to(skills_dir)
                module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
                
                spec = importlib.util.spec_from_file_location(module_name, str(filepath))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    module.__package__ = "skills"
                    spec.loader.exec_module(module)
                    
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and obj.__name__ != "BaseSkill":
                            if any(cls.__name__ == "BaseSkill" for cls in inspect.getmro(obj)):
                                try:
                                    skill_instance = obj(agent=self.agent)
                                    target_skills[skill_instance.name] = skill_instance
                                    
                                    for tool_decl in skill_instance.get_tool_declarations():
                                        tool_name = tool_decl.get("name")
                                        if tool_name:
                                            target_map[tool_name] = skill_instance
                                except TypeError as te:
                                    logger.error(f"❌ 無法實例化 Skill {filepath.name}: {te}")
            except Exception as e:
                logger.error(f"❌ 載入 Skill {filepath.name} 失敗: {e}")

    def on_key_release(self, key):
        if key == keyboard.Key.f12:
            if not self.safety_lock:
                self.safety_lock = True
                logger.critical("\n\n🚨 [緊急停止] 偵測到 F12！已強制鎖定！\n")
        elif key == keyboard.Key.f10: # 新增：F10 快捷鍵中斷
            if self.agent:
                self.agent.set_stop_flag()
                logger.critical("\n\n🛑 [中斷指令] 偵測到 F10！已設定中斷旗標！\n")

    def set_safety_lock(self, locked: bool):
        self.safety_lock = locked
        state = "🔒 鎖定 (安全模式)" if locked else "🔓 解鎖 (自由模式)"
        logger.warning(f"安全開關已切換: {state}")
        return state

    # ===== 內建工具：get_precise_file_stats =====
    def _get_precise_file_stats(self, file_path):
        """精準讀取檔案的物理與視覺統計數據，解決換行符號導致的字元數誤報問題。"""
        try:
            resolved_path = Path(file_path)
            if not resolved_path.exists():
                return {
                    "status": "error",
                    "message": f"找不到檔案: {file_path}"
                }
            
            # 讀取原始 bytes
            raw_bytes = resolved_path.read_bytes()
            file_size_bytes = len(raw_bytes)
            
            # 以 utf-8 解碼（保留原始換行）
            content = raw_bytes.decode("utf-8")
            physical_char_count = len(content)
            
            # 將 CRLF 轉換為 LF 後的長度
            normalized = content.replace("\r\n", "\n")
            normalized_char_count = len(normalized)
            
            # 偵測換行類型
            crlf_count = content.count("\r\n")
            lf_only_count = content.count("\n") - crlf_count
            if crlf_count > 0 and lf_only_count == 0:
                line_ending = "CRLF"
            elif crlf_count == 0 and lf_only_count > 0:
                line_ending = "LF"
            elif crlf_count > 0 and lf_only_count > 0:
                line_ending = "MIXED"
            else:
                line_ending = "NONE"  # 空檔案或無換行
            
            # 行數
            line_count = content.count("\n")
            if content and not content.endswith("\n"):
                line_count += 1
            
            return {
                "status": "success",
                "file_path": str(resolved_path.resolve()),
                "physical_char_count": physical_char_count,
                "normalized_char_count": normalized_char_count,
                "line_ending": line_ending,
                "line_count": line_count,
                "file_size_bytes": file_size_bytes
            }
        except UnicodeDecodeError:
            return {
                "status": "error",
                "message": f"無法以 utf-8 解碼檔案: {file_path}（可能為二進位檔案）"
            }
        except PermissionError:
            return {
                "status": "error",
                "message": f"權限不足，無法讀取檔案: {file_path}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"讀取檔案時發生錯誤: {str(e)}"
            }

    # ===== 內建工具：get_precise_time =====
    def _get_precise_time(self, include_weekday=False):
        """獲取作業系統底層的精準時間，用於杜絕 AI 的時間幻覺。"""
        try:
            tz = timezone(timedelta(hours=8))
            now = datetime.now(tz)
            
            weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            result = {
                "status": "success",
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": "UTC+8",
            }
            if include_weekday:
                result["weekday"] = weekdays[now.weekday()]
            
            return result
        except Exception as e:
            return {
                "status": "error",
                "message": f"獲取時間時發生錯誤: {str(e)}"
            }

    def get_tool_definitions(self):
        all_declarations = []
        for skill in self.skills.values():
            all_declarations.extend(skill.get_tool_declarations())
            
        # 新增內建工具宣告
        built_in_tools = [
            {
                "name": "get_precise_file_stats",
                "description": "【核心核實】獲取檔案的精準物理與視覺統計數據。解決換行符號導致的字元數誤報問題。在提交 ADSP 報告前必須呼叫。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "檔案的完整路徑 or 相對路徑。"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "get_precise_time",
                "description": "【核心校準】獲取作業系統底層的精準時間，用於杜絕 AI 的時間幻覺。在回報任何時間敏感資訊前必須呼叫。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_weekday": {"type": "boolean", "description": "是否包含星期資訊。"}
                    }
                }
            }
        ]
        all_declarations.extend(built_in_tools)
        
        return [{"function_declarations": all_declarations}]

    async def execute_tool(self, function_name, args, memory=None):
        logger.info(f"🔧 Alice 嘗試使用工具: {function_name} | 參數: {args}")
        
        # ===== 內建工具優先處理 =====
        if function_name == "get_precise_file_stats":
            file_path = args.get("file_path", "")
            return self._get_precise_file_stats(file_path)
        
        if function_name == "get_precise_time":
            include_weekday = args.get("include_weekday", False)
            return self._get_precise_time(include_weekday)
        
        # ===== 安全鎖檢查（內建工具不受鎖定影響） =====
        if function_name == "computer_control" and self.safety_lock:
            return {
                "error": "SAFETY_LOCK_ACTIVE", 
                "message": "❌ 安全鎖定中 (Safety Mode)。電腦操作已被系統攔截。"
            }

        skill = self.tool_to_skill_map.get(function_name)
        if skill:
            # ===== 建立技能執行上下文 =====
            context = {
                "scale_x": self.scale_x,
                "scale_y": self.scale_y,
                "screen_width": self.screen_width,
                "screen_height": self.screen_height,
                "memory": memory,
                "tools": self, # 核心修復：傳遞 ToolManager 實體，讓技能間可以互叫
                # 【路由引擎支援】傳遞可用工具清單與完整宣告，供 orchestrator 動態比對任務
                "available_tools": list(self.tool_to_skill_map.keys()),
                "tool_definitions": self.get_tool_definitions(),
                "tool_to_skill_map": self.tool_to_skill_map,
            }
            try:
                # 關鍵修復：技能執行通常是 async 的
                if inspect.iscoroutinefunction(skill.execute):
                    return await skill.execute(function_name, args, context)
                else:
                    return skill.execute(function_name, args, context)
            except Exception as e:
                logger.error(f"Skill Execution Error ({function_name}): {e}")
                return {"error": "Execution Exception", "message": str(e)}
                
        return {"error": "Unknown function", "message": f"找不到 {function_name} 的模組實作。"}
