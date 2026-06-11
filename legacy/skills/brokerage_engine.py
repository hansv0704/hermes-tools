"""
三竹 SuperCat 券商自動化引擎 v1.0
支援台新證券、兆豐證券（共用三竹底層，切換設定檔）
使用 Playwright 進行網頁自動化
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

from .broker_abstract import IBroker, BrokerRegistry, broker_registry

logger = logging.getLogger(__name__)

# ============ 券商設定 ============
BROKERAGE_CONFIGS = {
    "taishin": {
        "name": "台新證券",
        "login_url": "https://www.twfhcsec.com.tw/",
        "account_env_key": "TAISHIN_ACCOUNT",
        "password_env_key": "TAISHIN_PASSWORD",
        "cookie_file": "broker_cookies_taishin.json",
    },
    "mega": {
        "name": "兆豐證券",
        "login_url": "https://globaltrade.emega.com.tw/MegaWeb/Login.aspx",
        "account_env_key": "MEGA_ACCOUNT",
        "password_env_key": "MEGA_PASSWORD",
        "cookie_file": "broker_cookies_mega.json",
    },
}

# 三竹系統 DOM 選擇器（可依實際頁面調整）
SANZHU_SELECTORS = {
    # 登入頁
    "login_account": 'input[placeholder*="帳號"], input[name*="account"], input[name*="uid"], #uid, #account',
    "login_password": 'input[type="password"], input[name*="password"], input[name*="pwd"], #pwd, #password',
    "login_captcha_img": 'img[src*="captcha"], img[src*="check"], img[id*="captcha"], img[src*="CAPTCHA"]',
    "login_captcha_input": 'input[name*="captcha"], input[name*="check"], input[id*="captcha"], input[name*="CAPTCHA"]',
    "login_button": 'button:has-text("登入"), button:has-text("Login"), input[value*="登入"], a:has-text("登入")',

    # 主頁選單
    "menu_order": 'a:has-text("下單"), a:has-text("委託下單"), a:has-text("交易")',
    "menu_position": 'a:has-text("庫存"), a:has-text("持股"), a:has-text("持有"), a:has-text("庫存查詢")',
    "menu_order_query": 'a:has-text("委託查詢"), a:has-text("委託單"), a:has-text("當日委託")',
    "menu_balance": 'a:has-text("餘額"), a:has-text("可用"), a:has-text("帳戶"), a:has-text("銀行餘額")',

    # 下單頁
    "order_symbol": 'input[name*="symbol"], input[name*="stock"], input[id*="symbol"], input[id*="stockCode"]',
    "order_side_buy": 'input[value="B"], input[value="買"], button:has-text("買進"), button:has-text("買")',
    "order_side_sell": 'input[value="S"], input[value="賣"], button:has-text("賣出"), button:has-text("賣")',
    "order_price": 'input[name*="price"], input[id*="price"], input[name*="orderPrice"]',
    "order_quantity": 'input[name*="qty"], input[name*="quantity"], input[id*="qty"], input[name*="orderQty"]',
    "order_submit": 'button:has-text("下單"), button:has-text("送出"), button:has-text("確認下單")',
    "order_confirm": 'button:has-text("確認"), button:has-text("是"), button:has-text("確定")',

    # 表格
    "order_table": 'table:has(tr), .order-table, #orderTable',
    "position_table": 'table:has(tr), .position-table, #positionTable',
}

COOKIE_DIR = Path(__file__).parent.parent / "data"


class BrokerageEngineManager:
    """管理多個券商引擎實例（全局 singleton）"""

    def __init__(self):
        self._engines: Dict[str, "SanZhuBrokerEngine"] = {}

    def get_engine(self, broker_id: str):
        """取得或建立券商引擎"""
        if broker_id not in BROKERAGE_CONFIGS:
            raise ValueError(f"不支援的券商: {broker_id}。可用: {list(BROKERAGE_CONFIGS.keys())}")

        if broker_id not in self._engines:
            config = BROKERAGE_CONFIGS[broker_id]

            # 讀取 .env 中的帳密
            from dotenv import load_dotenv
            load_dotenv()
            account = os.getenv(config["account_env_key"])
            password = os.getenv(config["password_env_key"])

            if not account or not password:
                raise ValueError(
                    f"請先在 .env 設定 {config['account_env_key']} 和 {config['password_env_key']}"
                )

            self._engines[broker_id] = SanZhuBrokerEngine(
                broker_id=broker_id,
                config=config,
                account=account,
                password=password,
            )
            broker_registry.register(broker_id, self._engines[broker_id], {
                "name": config["name"],
                "broker_id": broker_id,
            })

        return self._engines[broker_id]

    async def login(self, broker_id: str) -> dict:
        engine = self.get_engine(broker_id)
        return await engine.login()

    async def login_with_captcha(self, broker_id: str, captcha_code: str) -> dict:
        engine = self.get_engine(broker_id)
        return await engine.login_with_captcha(captcha_code)

    # === 1. 獲取持倉資料的非同步函式 ===
    async def get_positions(self, broker_id: str) -> dict:
        engine = self.get_engine(broker_id)
        # ✨ 修正：把原本掉在最底部的 return 移回這裡，組合完整
        return await engine.get_positions()

    # === 2. 啟動瀏覽器的非同步函式 ===
    async def launch_with_profile(self, broker_id: str) -> dict:
        """使用專屬 Profile 啟動瀏覽器（憑證繼承模式）"""
        engine = self.get_engine(broker_id)
        return await engine.launch_with_profile()

    # === 3. 獲取路徑的普通函式 ===
    def get_profile_path(self) -> str:
        """獲取 Alice 專屬投資 Profile 路徑"""
        return str(Path(os.environ['LOCALAPPDATA']) / "Google/Chrome/Alice_Invest_Profile")


    async def get_orders(self, broker_id: str) -> dict:
        engine = self.get_engine(broker_id)
        return await engine.get_orders()

    async def place_order(self, broker_id: str, symbol: str, side: str, price: float, quantity: int) -> dict:
        engine = self.get_engine(broker_id)
        return await engine.place_order(symbol, side, price, quantity)

    async def cancel_order(self, broker_id: str, order_id: str) -> dict:
        engine = self.get_engine(broker_id)
        return await engine.cancel_order(order_id)

    async def get_balance(self, broker_id: str) -> dict:
        engine = self.get_engine(broker_id)
        return await engine.get_balance()

    def list_brokers(self) -> list:
        return [
            {"id": k, "name": v["name"], "has_credentials": bool(os.getenv(v["account_env_key"]))}
            for k, v in BROKERAGE_CONFIGS.items()
        ]

    async def close_all(self):
        for engine in self._engines.values():
            await engine.close()
        for broker_id in list(self._engines.keys()):
            broker_registry.unregister(broker_id)
        self._engines.clear()


# 全局實例
engine_manager = BrokerageEngineManager()


class SanZhuBrokerEngine(IBroker):
    """三竹 SuperCat 通用券商引擎"""

    def __init__(self, broker_id: str, config: dict, account: str, password: str):
        self.broker_id = broker_id
        self.config = config
        self.account = account
        self.password = password
        self.cookie_path = COOKIE_DIR / config["cookie_file"]
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None
        self._logged_in = False

    # 預設使用普通模式
    async def _ensure_browser(self):
        if self.browser is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            # ✨ 修正：把原本掉在最底部的參數與右括號移回這裡組合完整
            self.browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--start-maximized"]
            )

    async def launch_with_profile(self) -> dict:
        """核心：啟動帶有持久化 Profile 的瀏覽器"""
        if self.browser or self.context:
            return {"status": "error", "message": "瀏覽器已在運行中，請先關閉"}
        
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        
        profile_path = Path(os.environ['LOCALAPPDATA']) / "Google/Chrome/Alice_Invest_Profile"
        profile_path.mkdir(parents=True, exist_ok=True)

        # 使用 launch_persistent_context 繼承憑證與 Session
        self.context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=False,
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.page.goto(self.config["login_url"])
        
        return {"status": "success", "message": f"已使用 Alice_Invest Profile 啟動 {self.config['name']}"}


    async def login(self) -> dict:
        """登入券商（支援 cookie 復用）"""
        await self._ensure_browser()

        # 嘗試從 cookie 恢復 session
        if self.cookie_path.exists():
            try:
                self.context = await self.browser.new_context()
                with open(self.cookie_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                self.page = await self.context.new_page()
                await self.page.goto(self.config["login_url"], wait_until="networkidle", timeout=30000)

                # 檢查是否已登入
                login_elem = await self.page.query_selector(SANZHU_SELECTORS["login_account"])
                if login_elem is None:
                    self._logged_in = True
                    return {"status": "success", "message": f"{self.config['name']} 已從 cookie 恢復登入"}
                else:
                    await self.context.close()
                    self.page = None
                    self.context = None
            except Exception as e:
                logger.warning(f"Cookie 恢復失敗: {e}")

        # 手動登入流程
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        await self.page.goto(self.config["login_url"], wait_until="networkidle", timeout=30000)

        # 填入帳密
        try:
            await self.page.wait_for_selector(SANZHU_SELECTORS["login_account"], timeout=10000)
            await self.page.fill(SANZHU_SELECTORS["login_account"], self.account)
            await self.page.fill(SANZHU_SELECTORS["login_password"], self.password)
        except Exception as e:
            return {"status": "error", "message": f"找不到登入表單: {e}"}

        # 驗證碼處理
        captcha_elem = await self.page.query_selector(SANZHU_SELECTORS["login_captcha_img"])
        captcha_input = await self.page.query_selector(SANZHU_SELECTORS["login_captcha_input"])

        if captcha_elem and captcha_input:
            COOKIE_DIR.mkdir(parents=True, exist_ok=True)
            captcha_path = COOKIE_DIR / f"captcha_{self.broker_id}.png"
            await captcha_elem.screenshot(path=str(captcha_path))
            return {
                "status": "captcha_required",
                "message": f"請查看驗證碼並輸入",
                "captcha_path": str(captcha_path),
                "broker_id": self.broker_id,
            }

        # 無驗證碼，直接登入
        await self.page.click(SANZHU_SELECTORS["login_button"])
        await self.page.wait_for_timeout(3000)
        await self._save_cookies()
        self._logged_in = True
        return {"status": "success", "message": f"{self.config['name']} 登入成功"}

    async def login_with_captcha(self, captcha_code: str) -> dict:
        if not self.page:
            return {"status": "error", "message": "請先呼叫 login"}
        await self.page.fill(SANZHU_SELECTORS["login_captcha_input"], captcha_code)
        await self.page.click(SANZHU_SELECTORS["login_button"])
        await self.page.wait_for_timeout(5000)
        await self._save_cookies()
        self._logged_in = True
        return {"status": "success", "message": f"{self.config['name']} 登入成功"}

    async def get_positions(self) -> dict:
        if not self._logged_in:
            result = await self.login()
            if result["status"] != "success":
                return result
        try:
            await self.page.click(SANZHU_SELECTORS["menu_position"])
            await self.page.wait_for_timeout(2000)
        except:
            return {"status": "error", "message": "找不到庫存選單，可能需要重新登入"}
        positions = await self._parse_table(SANZHU_SELECTORS["position_table"])
        return {"status": "success", "positions": positions, "broker": self.config["name"]}

    async def get_orders(self) -> dict:
        if not self._logged_in:
            result = await self.login()
            if result["status"] != "success":
                return result
        try:
            await self.page.click(SANZHU_SELECTORS["menu_order_query"])
            await self.page.wait_for_timeout(2000)
        except:
            return {"status": "error", "message": "找不到委託查詢選單"}
        orders = await self._parse_table(SANZHU_SELECTORS["order_table"])
        return {"status": "success", "orders": orders, "broker": self.config["name"]}

    async def place_order(self, symbol: str, side: str, price: float, quantity: int) -> dict:
        if not self._logged_in:
            result = await self.login()
            if result["status"] != "success":
                return result
        try:
            await self.page.click(SANZHU_SELECTORS["menu_order"])
            await self.page.wait_for_timeout(2000)
        except:
            return {"status": "error", "message": "找不到下單選單"}
        await self.page.fill(SANZHU_SELECTORS["order_symbol"], symbol)
        await self.page.wait_for_timeout(1000)
        if side.upper() == "BUY":
            await self.page.click(SANZHU_SELECTORS["order_side_buy"])
        else:
            await self.page.click(SANZHU_SELECTORS["order_side_sell"])
        await self.page.fill(SANZHU_SELECTORS["order_price"], str(price))
        await self.page.fill(SANZHU_SELECTORS["order_quantity"], str(quantity))
        await self.page.click(SANZHU_SELECTORS["order_submit"])
        await self.page.wait_for_timeout(2000)
        try:
            confirm_btn = await self.page.query_selector(SANZHU_SELECTORS["order_confirm"])
            if confirm_btn:
                await confirm_btn.click()
                await self.page.wait_for_timeout(2000)
        except:
            pass
        return {"status": "success", "message": f"已下單 {symbol} {side} {quantity}股 @${price:.2f}"}

    async def cancel_order(self, order_id: str) -> dict:
        if not self._logged_in:
            result = await self.login()
            if result["status"] != "success":
                return result
        try:
            cancel_btn = await self.page.query_selector(f"tr:has-text('{order_id}') button, button:has-text('取消')")
            if cancel_btn:
                await cancel_btn.click()
                await self.page.wait_for_timeout(1000)
                return {"status": "success", "message": f"已取消委託 {order_id}"}
            return {"status": "error", "message": f"找不到委託 {order_id}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_balance(self) -> dict:
        if not self._logged_in:
            result = await self.login()
            if result["status"] != "success":
                return result
        try:
            await self.page.click(SANZHU_SELECTORS["menu_balance"])
            # 深度掃描所有 iFrame
            all_frames = self.page.frames
            content_summary = []
            for i, frame in enumerate(all_frames):
                try:
                    text = await frame.inner_text("body")
                    content_summary.append(f"Frame {i} ({frame.name}): {text[:200]}...")
                    # 嘗試尋找餘額關鍵字
                    if "餘額" in text or "存款" in text or "可用" in text:
                        return {
                            "status": "success", 
                            "balance_raw": text, 
                            "frame_index": i,
                            "frame_name": frame.name,
                            "broker": self.config["name"]
                        }
                except:
                    continue
            
            return {"status": "partial", "message": "未在框架中找到明確餘額，回傳摘要", "summary": content_summary}
            await self.page.wait_for_timeout(2000)
        except:
            return {"status": "error", "message": "找不到餘額查詢選單"}
        try:
            body = await self.page.text_content("body")
            return {"status": "success", "balance_raw": body[:800], "broker": self.config["name"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _save_cookies(self):
        cookies = await self.context.cookies()
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False)

    async def _parse_table(self, selector: str) -> List[List[str]]:
        rows = []
        try:
            table = await self.page.query_selector(selector)
            if not table:
                return rows
            trs = await table.query_selector_all("tr")
            for tr in trs:
                tds = await tr.query_selector_all("td, th")
                cells = [((await td.text_content()) or "").strip() for td in tds]
                if cells:
                    rows.append(cells)
        except Exception as e:
            logger.error(f"解析表格失敗: {e}")
        return rows

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.browser = None
        self.page = None
        self.context = None
        self._playwright = None
        self._logged_in = False
