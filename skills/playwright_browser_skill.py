
"""
Playwright Browser Skill — Chrome CDP 直連操控管道
================================================
全新獨立操控方式，不整合現有 gis_skill。
使用 Playwright connect_over_cdp 連接現有 Chrome，
100% DOM 精準定位，廢除 Vision 座標猜測。

依賴：pip install playwright
Chrome 需以 --remote-debugging-port=9222 啟動
"""

from base_skill import BaseSkill
from config import logger
from typing import Optional, Dict, Any, List
import json
import asyncio

HAS_PLAYWRIGHT = False
try:
    from playwright.async_api import async_playwright, Page, Browser
    HAS_PLAYWRIGHT = True
except ImportError:
    pass


class PlaywrightBrowserSkill(BaseSkill):
    """Chrome CDP 直連瀏覽器操控 Skill"""

    def __init__(self, agent=None):
        super().__init__(agent=agent)
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._playwright = None
        self._cdp_url = "http://localhost:9222"

    @property
    def name(self) -> str:
        return "playwright_browser_skill"

    # ═══════════════════════════════════════════
    #  連接管理
    # ═══════════════════════════════════════════

    async def _ensure_connected(self) -> Dict[str, Any]:
        """確保已連接到 Chrome CDP"""
        if not HAS_PLAYWRIGHT:
            return {
                "success": False,
                "error": "Playwright 未安裝。請執行：pip install playwright && playwright install chromium"
            }

        if self._page and self._is_page_alive():
            return {"success": True, "message": "已連接"}

        try:
            import urllib.request
            import urllib.error

            # 先檢查 CDP 是否可用
            try:
                resp = urllib.request.urlopen(f"{self._cdp_url}/json/version", timeout=3)
                data = json.loads(resp.read())
                ws_url = data.get("webSocketDebuggerUrl", "")
                if not ws_url:
                    return {
                        "success": False,
                        "error": (
                            "❌ Chrome CDP 已啟動但無法取得 WebSocket URL。\n"
                            "請確認 Chrome 以 --remote-debugging-port=9222 啟動。"
                        )
                    }
            except (urllib.error.URLError, ConnectionRefusedError):
                return {
                    "success": False,
                    "error": (
                        "❌ 無法連接到 Chrome CDP (port 9222)。\n"
                        "請先以 debug mode 啟動 Chrome：\n"
                        'chrome.exe --remote-debugging-port=9222'
                    )
                }

            # 使用 Playwright 連接
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)

            # 取得當前活動頁面
            contexts = self._browser.contexts
            if contexts and contexts[0].pages:
                self._page = contexts[0].pages[0]
            else:
                self._page = await (contexts[0].new_page() if contexts else self._browser.new_context().new_page())

            return {"success": True, "message": f"✅ 已連接到 Chrome: {self._page.url}"}

        except Exception as e:
            logger.error(f"Playwright 連接失敗: {e}")
            await self._cleanup()
            return {"success": False, "error": f"連接失敗: {str(e)}"}

    def _is_page_alive(self) -> bool:
        """檢查頁面是否仍然存活"""
        try:
            if self._page:
                self._page.url  # 嘗試存取屬性
                return True
        except Exception:
            pass
        return False

    async def _cleanup(self):
        """清理連接"""
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._page = None
        self._playwright = None

    # ═══════════════════════════════════════════
    #  核心操控方法
    # ═══════════════════════════════════════════

    async def navigate(self, url: str) -> Dict[str, Any]:
        """導航到指定 URL"""
        result = await self._ensure_connected()
        if not result["success"]:
            return result

        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            return {
                "success": True,
                "message": f"✅ 已導航到: {url}",
                "current_url": self._page.url,
                "title": await self._page.title()
            }
        except Exception as e:
            return {"success": False, "error": f"導航失敗: {str(e)}"}

    async def click(self, selector: str = None, text: str = None,
              x_1000: int = None, y_1000: int = None) -> Dict[str, Any]:
        """點擊元素。支援 CSS selector、文字內容、或座標"""
        result = await self._ensure_connected()
        if not result["success"]:
            return result

        try:
            if selector:
                await self._page.click(selector, timeout=5000)
                return {"success": True, "message": f"✅ 已點擊: {selector}"}
            elif text:
                await self._page.click(f"text={text}", timeout=5000)
                return {"success": True, "message": f"✅ 已點擊文字: {text}"}
            elif x_1000 is not None and y_1000 is not None:
                vw = self._page.viewport_size
                x = int(vw["width"] * x_1000 / 1000)
                y = int(vw["height"] * y_1000 / 1000)
                await self._page.mouse.click(x, y)
                return {"success": True, "message": f"✅ 已點擊座標: ({x}, {y})"}
            else:
                return {"success": False, "error": "請提供 selector、text 或座標"}
        except Exception as e:
            return {"success": False, "error": f"點擊失敗: {str(e)}"}

    async def check_radio(self, label_text: str) -> Dict[str, Any]:
        """勾選 radio button（透過 label 文字定位）"""
        result = await self._ensure_connected()
        if not result["success"]:
            return result

        try:
            # 策略1：透過 label 文字找到對應的 radio
            label = self._page.locator(f"label:has-text('{label_text}')")
            if await label.count() > 0:
                await label.first.click(timeout=3000)
                return {"success": True, "message": f"✅ 已勾選: {label_text}"}

            # 策略2：透過文字內容找到最近的 radio
            element = self._page.locator(f"text={label_text}")
            if await element.count() > 0:
                # 嘗試找到相鄰的 radio input
                parent = element.first.locator("..") 
                radio = parent.locator("input[type='radio']")
                if await radio.count() > 0:
                    await radio.first.check(timeout=3000)
                    return {"success": True, "message": f"✅ 已勾選 radio: {label_text}"}

            return {"success": False, "error": f"找不到 radio: {label_text}"}
        except Exception as e:
            return {"success": False, "error": f"勾選失敗: {str(e)}"}

    async def type_text(self, text: str, selector: str = None) -> Dict[str, Any]:
        """輸入文字"""
        result = await self._ensure_connected()
        if not result["success"]:
            return result

        try:
            if selector:
                await self._page.fill(selector, text, timeout=5000)
            else:
                await self._page.keyboard.type(text)
            return {"success": True, "message": f"✅ 已輸入文字"}
        except Exception as e:
            return {"success": False, "error": f"輸入失敗: {str(e)}"}

    async def screenshot(self) -> Dict[str, Any]:
        """截圖並回傳 base64"""
        import base64
        result = await self._ensure_connected()
        if not result["success"]:
            return result

        try:
            data = await self._page.screenshot(type="png", full_page=False)
            b64 = base64.b64encode(data).decode()
            return {
                "success": True,
                "message": "✅ 截圖完成",
                "screenshot_base64": b64[:200] + "...(truncated)",
                "url": self._page.url,
                "title": await self._page.title()
            }
        except Exception as e:
            return {"success": False, "error": f"截圖失敗: {str(e)}"}

    async def get_page_info(self) -> Dict[str, Any]:
        """獲取當前頁面資訊"""
        result = await self._ensure_connected()
        if not result["success"]:
            return result

        try:
            return {
                "success": True,
                "url": self._page.url,
                "title": await self._page.title(),
                "content_preview": (await self._page.content())[:500] + "..."
            }
        except Exception as e:
            return {"success": False, "error": f"獲取頁面資訊失敗: {str(e)}"}

    async def get_radio_buttons(self) -> Dict[str, Any]:
        """列出頁面上所有 radio button 的文字標籤"""
        result = await self._ensure_connected()
        if not result["success"]:
            return result

        try:
            radios = self._page.locator("input[type='radio']")
            count = await radios.count()
            items = []
            for i in range(min(count, 20)):
                try:
                    radio = radios.nth(i)
                    # 嘗試找關聯的 label
                    radio_id = await radio.get_attribute("id")
                    label_text = ""
                    if radio_id:
                        label = self._page.locator(f"label[for='{radio_id}']")
                        if await label.count() > 0:
                            label_text = await label.first.inner_text()
                    if not label_text:
                        # 嘗試找父元素文字
                        parent = radio.locator("..")
                        if await parent.count() > 0:
                            label_text = await parent.inner_text()[:100]
                    checked = await radio.is_checked()
                    items.append({
                        "index": i,
                        "id": radio_id or "",
                        "label": label_text.strip() if label_text else "",
                        "checked": checked,
                        "name": await radio.get_attribute("name") or ""
                    })
                except Exception:
                    pass
            return {"success": True, "radios": items, "count": count}
        except Exception as e:
            return {"success": False, "error": f"列舉 radio 失敗: {str(e)}"}

    # ═══════════════════════════════════════════
    #  BaseSkill 介面
    # ═══════════════════════════════════════════

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "playwright_navigate",
                "description": "【Playwright CDP】導航到指定 URL。使用 Chrome CDP 直連，保留現有登入狀態。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "目標 URL"
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "playwright_click",
                "description": "【Playwright CDP】點擊元素。支援 CSS selector、文字內容、或 0-1000 比例座標。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector (選填)"},
                        "text": {"type": "string", "description": "要點擊的文字 (選填)"},
                        "x_1000": {"type": "integer", "description": "X 座標比例 0-1000 (選填)"},
                        "y_1000": {"type": "integer", "description": "Y 座標比例 0-1000 (選填)"}
                    },
                    "required": []
                }
            },
            {
                "name": "playwright_check_radio",
                "description": "【Playwright CDP】勾選 radio button。透過 label 文字精準定位，無需座標猜測。★ GIS 巡檢專用",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "label_text": {
                            "type": "string",
                            "description": "radio button 的 label 文字，例如 '1.正常（監測值連續趨勢）'"
                        }
                    },
                    "required": ["label_text"]
                }
            },
            {
                "name": "playwright_type",
                "description": "【Playwright CDP】在指定元素中輸入文字。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "要輸入的文字"},
                        "selector": {"type": "string", "description": "目標元素的 CSS selector (選填，不填則輸入到焦點元素)"}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "playwright_screenshot",
                "description": "【Playwright CDP】擷取當前頁面截圖。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "playwright_get_page",
                "description": "【Playwright CDP】獲取當前頁面資訊 (URL、標題、內容預覽)。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "playwright_list_radios",
                "description": "【Playwright CDP】列舉頁面上所有 radio button，包含文字標籤、選中狀態。★ GIS 巡檢前先探查",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "playwright_disconnect",
                "description": "【Playwright CDP】中斷與 Chrome 的 CDP 連接。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]

    async def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if not HAS_PLAYWRIGHT:
            return {
                "error": "Missing Library",
                "message": (
                    "⚠️ Playwright 未安裝。請執行以下指令：\n"
                    "```bash\npip install playwright\nplaywright install chromium\n```\n"
                    "然後以 debug mode 啟動 Chrome：\n"
                    '```bash\nchrome.exe --remote-debugging-port=9222\n```'
                )
            }

        try:
            if function_name == "playwright_navigate":
                return await self.navigate(args.get("url", ""))
            elif function_name == "playwright_click":
                return await self.click(
                    selector=args.get("selector"),
                    text=args.get("text"),
                    x_1000=args.get("x_1000"),
                    y_1000=args.get("y_1000")
                )
            elif function_name == "playwright_check_radio":
                return await self.check_radio(args.get("label_text", ""))
            elif function_name == "playwright_type":
                return await self.type_text(
                    text=args.get("text", ""),
                    selector=args.get("selector")
                )
            elif function_name == "playwright_screenshot":
                return await self.screenshot()
            elif function_name == "playwright_get_page":
                return await self.get_page_info()
            elif function_name == "playwright_list_radios":
                return await self.get_radio_buttons()
            elif function_name == "playwright_disconnect":
                await self._cleanup()
                return {"success": True, "message": "✅ 已中斷 CDP 連接"}
            else:
                return {"error": f"未知功能: {function_name}"}
        except Exception as e:
            logger.error(f"Playwright Skill 執行失敗 [{function_name}]: {e}")
            await self._cleanup()
            return {"error": f"執行失敗: {str(e)}"}
