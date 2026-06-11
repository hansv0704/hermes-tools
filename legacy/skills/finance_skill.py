from base_skill import BaseSkill
from config import logger

try:
    import yfinance as yf
except ImportError:
    yf = None

class FinanceSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "finance_skill"

    def get_tool_declarations(self) -> list:
        return [
            {
                "name": "get_stock_price",
                "description": "查詢真實股票的即時價格。支援台股(如 2330)與美股(如 NVDA)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代號 (例如: 2330, 2330.TW, NVDA, TSLA)"
                        }
                    },
                    "required": ["symbol"]
                }
            }
        ]

    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name == "get_stock_price":
            return self._get_real_stock_price(args.get("symbol"))
        return {"error": "Unknown function in FinanceSkill"}

    def _get_real_stock_price(self, symbol):
        if not yf:
            return {"error": "Missing Module", "message": "請主人安裝 yfinance 套件 (pip install yfinance) 以啟用真實股價查詢。"}

        try:
            symbol = str(symbol).strip().upper()
            target = f"{symbol}.TW" if symbol.isdigit() else symbol
            
            ticker = yf.Ticker(target)
            price = None
            if hasattr(ticker, 'fast_info') and hasattr(ticker.fast_info, 'last_price'):
                price = ticker.fast_info.last_price
            
            if price is None:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
            
            if price is None:
                return {"error": "Query Failed", "message": f"找不到 {target} 的股價資料。"}

            return {
                "symbol": target,
                "price": round(price, 2),
                "currency": "TWD" if ".TW" in target else "USD",
                "status": "Success"
            }
        except Exception as e:
            return {"error": "Exception", "message": str(e)}
