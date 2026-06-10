
"""
DeepSeek Vision Bridge Skill
讓 DeepSeek 模型透過 Gemini Vision API 獲得視覺能力。
支援截圖分析、UI 元素定位、目標點擊。
模型：gemini-3-flash-preview（2026 年唯一存活主力）
"""

import io
import json
import os
import re
from base_skill import BaseSkill
from config import logger

try:
    import mss
except ImportError:
    mss = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from PIL import Image
except ImportError:
    Image = None


class DeepSeekVisionBridgeSkill(BaseSkill):
    """DeepSeek 視覺橋接：截圖 → Gemini Vision → 座標/描述"""

    @property
    def name(self) -> str:
        return "deepseek_vision_bridge_skill"

    # ── Gemini 客戶端（延遲初始化） ──
    _client_ready = False

    def _init_gemini(self) -> bool:
        """初始化 Gemini 客戶端，從 .env 讀取 API 金鑰"""
        if self._client_ready:
            return True
        if genai is None:
            logger.error("Vision Bridge: google-generativeai 未安裝")
            return False

        api_keys_str = os.getenv("GOOGLE_API_KEYS", "")
        if not api_keys_str:
            logger.error("Vision Bridge: .env 中無 GOOGLE_API_KEYS")
            return False

        keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
        if not keys:
            return False

        # 使用第一把金鑰
        genai.configure(api_key=keys[0])
        self._client_ready = True
        logger.info("Vision Bridge: Gemini 客戶端已初始化 (gemini-3-flash-preview)")
        return True

    def _capture_screen(self) -> bytes:
        """使用 mss 截取全螢幕，回傳 PNG bytes"""
        if mss is None:
            raise RuntimeError("mss 套件未安裝，請 pip install mss")
        if Image is None:
            raise RuntimeError("Pillow 套件未安裝，請 pip install Pillow")
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # 主螢幕
            screenshot = sct.grab(monitor)
            # mss 回傳 BGRA，轉為 PNG
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

    def _get_screen_size(self) -> tuple:
        """取得螢幕寬高"""
        if mss is None:
            return (1920, 1080)
        with mss.mss() as sct:
            m = sct.monitors[1]
            return (m["width"], m["height"])

    def _call_gemini_vision(self, image_bytes: bytes, prompt: str) -> str:
        """呼叫 Gemini Vision API，回傳文字回應。失敗時拋出例外。"""
        if not self._init_gemini():
            raise RuntimeError("Gemini 客戶端初始化失敗，請檢查 GOOGLE_API_KEYS 和 google-generativeai 套件")
        if Image is None:
            raise RuntimeError("Pillow 套件未安裝")

        model = genai.GenerativeModel("gemini-3-flash-preview")
        img = Image.open(io.BytesIO(image_bytes))

        response = model.generate_content([prompt, img])
        return response.text

    # ── 工具宣告 ──
    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "vision_analyze_screen",
                "description": "【視覺分析】截取目前螢幕畫面，交由 Gemini Vision 分析。可指定分析目標（找按鈕、讀文字、定位元素）。回傳 0~1000 比例座標與描述。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "要尋找或分析的目標描述。例如：'找到藍色的送出按鈕'、'讀取紅色錯誤訊息'、'找出所有可點擊的按鈕'"
                        },
                        "detail": {
                            "type": "string",
                            "enum": ["brief", "full"],
                            "description": "分析詳細度：brief=僅回傳目標座標，full=完整畫面描述+座標。預設 full"
                        }
                    },
                    "required": ["target"]
                }
            },
            {
                "name": "vision_click_target",
                "description": "【視覺點擊】描述你要點擊的目標，自動截圖 → Vision 定位 → 回傳 0~1000 座標（搭配 computer_control 使用）。僅回傳座標不執行點擊。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "要點擊的目標描述。例如：'點擊序號1右側的功能點擊回報按鈕'、'點擊畫面右上角的 X 關閉按鈕'"
                        }
                    },
                    "required": ["target"]
                }
            },
            {
                "name": "vision_describe_screen",
                "description": "【畫面描述】截取目前螢幕，由 Gemini Vision 用自然語言描述畫面內容。用於了解當前畫面狀態。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "focus": {
                            "type": "string",
                            "description": "描述重點（選填）。例如：'描述表格內容'、'描述彈出視窗'、'描述錯誤訊息'"
                        }
                    },
                    "required": []
                }
            }
        ]

    # ── 執行分派 ──
    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name == "vision_analyze_screen":
            return self._analyze_screen(args)
        elif function_name == "vision_click_target":
            return self._click_target(args)
        elif function_name == "vision_describe_screen":
            return self._describe_screen(args)
        return {"error": f"未知函式: {function_name}"}

    # ── 核心實作 ──

    def _clean_json_response(self, raw: str) -> str:
        """清理 Gemini 回傳的 JSON 字串：去除 markdown 程式碼區塊包裹（大小寫相容）"""
        cleaned = raw.strip()
        # 去除 ```json 或 ```JSON 前綴
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
        # 去除尾端 ```
        cleaned = re.sub(r'\s*```\s*$', '', cleaned)
        return cleaned.strip()
    def _analyze_screen(self, args: dict) -> dict:
        target = args.get("target", "")
        detail = args.get("detail", "full")

        try:
            image_bytes = self._capture_screen()
            w, h = self._get_screen_size()

            if detail == "brief":
                prompt = f"""你是一個 UI 定位系統。分析這張螢幕截圖（{w}x{h}）。

任務：{target}

請用 JSON 格式回覆，格式如下：
{{
  "found": true/false,
  "description": "簡短描述",
  "elements": [
    {{"label": "元素名稱", "x_1000": 0~1000整數, "y_1000": 0~1000整數, "confidence": "high/medium/low"}}
  ]
}}

座標使用 0~1000 比例：x_1000=0 是畫面最左，x_1000=1000 是畫面最右，y_1000=0 是畫面最上，y_1000=1000 是畫面最下。
精準定位到目標元素的中心點。只回覆 JSON，不要其他文字。"""
            else:
                prompt = f"""你是一個 UI 分析系統。分析這張螢幕截圖（{w}x{h}）。

任務：{target}

請用 JSON 格式詳細回覆：
{{
  "found": true/false,
  "overview": "畫面整體描述（繁體中文）",
  "elements": [
    {{"label": "元素名稱（繁體中文）", "x_1000": 0~1000整數, "y_1000": 0~1000整數, "confidence": "high/medium/low", "note": "補充說明"}}
  ],
  "suggestion": "建議的下一步操作（繁體中文）"
}}

座標使用 0~1000 比例系統。只回覆 JSON，不要其他文字。"""

            result_text = self._call_gemini_vision(image_bytes, prompt)
            try:
                parsed = json.loads(self._clean_json_response(result_text))
                return {"status": "success", "data": parsed, "screen": {"width": w, "height": h}}
            except json.JSONDecodeError:
                return {"status": "success", "data": {"found": False, "raw_response": result_text, "note": "JSON 解析失敗，請查看原始回應"}, "screen": {"width": w, "height": h}}

        except Exception as e:
            logger.error(f"Vision Bridge analyze 錯誤: {e}")
            return {"error": str(e)}

    def _click_target(self, args: dict) -> dict:
        target = args.get("target", "")

        try:
            image_bytes = self._capture_screen()
            w, h = self._get_screen_size()

            prompt = f"""你是一個 UI 點擊定位系統。分析這張螢幕截圖（{w}x{h}）。

請找到以下目標並回覆其座標：{target}

用 JSON 格式回覆：
{{
  "found": true/false,
  "x_1000": 0~1000整數,
  "y_1000": 0~1000整數,
  "label": "你認為這個元素是什麼（繁體中文）",
  "confidence": "high/medium/low"
}}

座標使用 0~1000 比例系統。x=0 最左，x=1000 最右，y=0 最上，y=1000 最下。
精準定位到目標元素的中心點。
只回覆 JSON，不要其他文字。"""

            result_text = self._call_gemini_vision(image_bytes, prompt)
            try:
                parsed = json.loads(self._clean_json_response(result_text))
                return {
                    "status": "success",
                    "data": parsed,
                    "screen": {"width": w, "height": h},
                    "instruction": f"請使用 computer_control (action='click', x_1000={parsed.get('x_1000')}, y_1000={parsed.get('y_1000')}) 來點擊目標"
                }
            except json.JSONDecodeError:
                return {"status": "success", "data": {"found": False, "raw_response": result_text}, "screen": {"width": w, "height": h}}

        except Exception as e:
            logger.error(f"Vision Bridge click_target 錯誤: {e}")
            return {"error": str(e)}

    def _describe_screen(self, args: dict) -> dict:
        focus = args.get("focus", "")

        try:
            image_bytes = self._capture_screen()
            w, h = self._get_screen_size()

            focus_text = f"\n請特別注意：{focus}" if focus else ""
            prompt = f"""你是一個螢幕畫面分析助手。請用繁體中文描述這張螢幕截圖（{w}x{h}）的內容。{focus_text}

回覆格式（JSON）：
{{
  "description": "畫面整體描述（繁體中文）",
  "active_window": "推測的當前視窗或應用程式名稱",
  "key_elements": ["元素1", "元素2", ...],
  "readable_text": "畫面上可讀取到的文字內容（繁體中文）",
  "suggestion": "根據畫面內容的建議操作"
}}

只回覆 JSON，不要其他文字。"""

            result_text = self._call_gemini_vision(image_bytes, prompt)
            try:
                parsed = json.loads(self._clean_json_response(result_text))
                return {"status": "success", "data": parsed, "screen": {"width": w, "height": h}}
            except json.JSONDecodeError:
                return {"status": "success", "data": {"description": result_text}, "screen": {"width": w, "height": h}}

        except Exception as e:
            logger.error(f"Vision Bridge describe 錯誤: {e}")
            return {"error": str(e)}
