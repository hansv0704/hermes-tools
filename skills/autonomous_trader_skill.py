import os
import time
import threading
import duckdb
import yfinance as yf
from skills.base_skill import BaseSkill

class AutonomousTraderSkill(BaseSkill):
    @property
    def name(self):
        return "autonomous_trader_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "start_autonomous_trader",
                "description": "啟動 24/7 投資代理人背景掃描任務。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "interval_minutes": {"type": "integer", "description": "掃描間隔 (分鐘)", "default": 15}
                    }
                }
            },
            {
                "name": "sync_bank_balance",
                "description": "手動同步指定銀行的餘額至資料庫。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string", "description": "帳戶 ID (如 TS_001)"},
                        "balance": {"type": "number", "description": "目前的餘額"}
                    },
                    "required": ["account_id", "balance"]
                }
            }
        ]

    def execute(self, tool_name, tool_args):
        conn = duckdb.connect('alice_core.db')
        
        if tool_name == "start_autonomous_trader":
            interval = tool_args.get("interval_minutes", 15)
            # 這裡僅啟動一個背景 Thread 模擬監控
            def monitor_loop():
                while True:
                    try:
                        # 模擬掃描邏輯：獲取熱門標的
                        # 這裡可以擴充為讀取 active_trades 並更新價格
                        conn_inner = duckdb.connect('alice_core.db')
                        trades = conn_inner.execute("SELECT symbol FROM active_trades WHERE status='OPEN'").fetchall()
                        for (symbol,) in trades:
                            ticker = yf.Ticker(symbol)
                            price = ticker.fast_info['last_price']
                            conn_inner.execute("UPDATE active_trades SET current_price = ? WHERE symbol = ?", [price, symbol])
                        conn_inner.close()
                    except Exception as e:
                        print(f"Trader Loop Error: {e}")
                    time.sleep(interval * 60)

            thread = threading.Thread(target=monitor_loop, daemon=True)
            thread.start()
            return {"status": "success", "message": f"24/7 代理人已啟動，間隔 {interval} 分鐘。"}

        elif tool_name == "sync_bank_balance":
            account_id = tool_args["account_id"]
            balance = tool_args["balance"]
            conn.execute("UPDATE asset_accounts SET balance = ?, last_sync = CURRENT_TIMESTAMP WHERE account_id = ?", [balance, account_id])
            
            # 同時更新資產歷史總額
            total = conn.execute("SELECT SUM(balance) FROM asset_accounts").fetchone()[0]
            conn.execute("INSERT INTO asset_history (total_value_twd) VALUES (?)", [total])
            
            conn.close()
            return {"status": "success", "message": f"帳戶 {account_id} 餘額已更新為 {balance}。"}

        conn.close()
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
