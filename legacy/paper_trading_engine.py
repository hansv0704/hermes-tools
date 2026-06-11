"""
紙上交易引擎 Paper Trading Engine
- 虛擬帳戶管理
- 持倉追蹤
- 委託歷史
- 績效指標 (Sharpe, 勝率, 最大回撤)
- 風控 (停損停利、部位上限)
"""
import duckdb
import logging
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)

# ─── 手續費設定 ───
COMMISSION_RATE = 0.001425  # 0.1425% 買賣各收
TAX_RATE = 0.003            # 0.3% 賣出證交稅（台股）
MIN_COMMISSION = 20         # 最低手續費


class PaperTradingEngine:
    """紙上交易引擎 — 單例模式"""

    _instance = None

    def __new__(cls, db_path: str = "alice_core.db"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = "alice_core.db"):
        if self._initialized:
            return
        self.db_path = db_path
        self._init_db()
        self._ensure_account()
        self._initialized = True

    # ─── 資料庫初始化 ───
    def _init_db(self):
        conn = duckdb.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_account (
                id INTEGER PRIMARY KEY DEFAULT 1,
                balance DOUBLE DEFAULT 1000000,
                initial_balance DOUBLE DEFAULT 1000000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_positions (
                id INTEGER PRIMARY KEY,
                symbol VARCHAR NOT NULL,
                name VARCHAR DEFAULT '',
                shares INTEGER NOT NULL,
                avg_cost DOUBLE NOT NULL,
                market VARCHAR DEFAULT 'TW',
                strategy VARCHAR DEFAULT 'manual',
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS paper_positions_seq START 1
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_orders (
                id INTEGER PRIMARY KEY,
                symbol VARCHAR NOT NULL,
                name VARCHAR DEFAULT '',
                side VARCHAR NOT NULL CHECK(side IN ('BUY','SELL')),
                shares INTEGER NOT NULL,
                price DOUBLE NOT NULL,
                total DOUBLE NOT NULL,
                commission DOUBLE DEFAULT 0,
                tax DOUBLE DEFAULT 0,
                status VARCHAR DEFAULT 'FILLED',
                strategy VARCHAR DEFAULT 'manual',
                note VARCHAR DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS paper_orders_seq START 1
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_strategy_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                strategy_name VARCHAR DEFAULT 'ma_crossover',
                is_running BOOLEAN DEFAULT FALSE,
                interval_minutes INTEGER DEFAULT 15,
                max_position_pct DOUBLE DEFAULT 0.20,
                stop_loss_pct DOUBLE DEFAULT 0.05,
                take_profit_pct DOUBLE DEFAULT 0.15,
                symbols TEXT DEFAULT '',
                params TEXT DEFAULT '{}',
                started_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_missions (
                id INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                risk_level VARCHAR DEFAULT 'medium',
                timeframe_days INTEGER DEFAULT 90,
                target_return_pct DOUBLE DEFAULT 10.0,
                max_positions INTEGER DEFAULT 5,
                max_position_pct DOUBLE DEFAULT 0.20,
                stop_loss_pct DOUBLE DEFAULT 0.05,
                take_profit_pct DOUBLE DEFAULT 0.15,
                allow_margin BOOLEAN DEFAULT FALSE,
                preferred_market VARCHAR DEFAULT 'TW',
                scan_frequency VARCHAR DEFAULT 'daily',
                status VARCHAR DEFAULT 'active' CHECK(status IN ('active','paused','completed','failed')),
                start_balance DOUBLE DEFAULT 0,
                current_balance DOUBLE DEFAULT 0,
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deadline TIMESTAMP,
                completed_at TIMESTAMP,
                note TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS paper_missions_seq START 1
        """)
        conn.close()

    def _ensure_account(self):
        conn = duckdb.connect(self.db_path)
        row = conn.execute("SELECT COUNT(*) FROM paper_account").fetchone()
        if row[0] == 0:
            conn.execute("INSERT INTO paper_account (balance, initial_balance) VALUES (1000000, 1000000)")
        conn.close()

    # ─── 帳戶查詢 ───
    def get_account(self) -> dict:
        conn = duckdb.connect(self.db_path)
        acc = conn.execute("SELECT balance, initial_balance, created_at FROM paper_account WHERE id=1").fetchone()
        if not acc:
            conn.close()
            return {"balance": 0, "initial_balance": 0, "total_return": 0, "total_return_pct": 0}

        balance = float(acc[0])
        initial = float(acc[1])

        # 計算持倉市值
        positions = conn.execute("SELECT symbol, shares, avg_cost FROM paper_positions").fetchall()
        stock_value = 0.0
        for p in positions:
            symbol, shares, cost = p
            price = self._get_current_price(symbol)
            stock_value += shares * (price if price else cost)

        total_assets = balance + stock_value
        total_return = total_assets - initial
        total_return_pct = (total_return / initial * 100) if initial > 0 else 0

        conn.close()
        return {
            "balance": round(balance, 2),
            "initial_balance": round(initial, 2),
            "stock_value": round(stock_value, 2),
            "total_assets": round(total_assets, 2),
            "total_return": round(total_return, 2),
            "total_return_pct": round(total_return_pct, 2),
        }

    # ─── 持倉查詢 ───
    def get_positions(self) -> list:
        conn = duckdb.connect(self.db_path)
        rows = conn.execute("""
            SELECT id, symbol, name, shares, avg_cost, market, strategy, opened_at, updated_at
            FROM paper_positions ORDER BY symbol
        """).fetchall()
        conn.close()

        positions = []
        for r in rows:
            symbol = r[1]
            shares = r[3]
            cost = float(r[4])
            price = self._get_current_price(symbol)
            current_value = shares * price if price else shares * cost
            pnl = current_value - shares * cost if price else 0
            pnl_pct = (pnl / (shares * cost) * 100) if cost > 0 and shares > 0 else 0

            positions.append({
                "id": r[0], "symbol": symbol, "name": r[2],
                "shares": shares, "avg_cost": round(cost, 2),
                "market": r[5], "strategy": r[6],
                "price": round(price, 2) if price else None,
                "current_value": round(current_value, 2),
                "cost_basis": round(shares * cost, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "opened_at": str(r[7]), "updated_at": str(r[8]),
            })
        return positions

    # ─── 下單 ───
    def buy(self, symbol: str, shares: int, price: float,
            name: str = "", strategy: str = "manual") -> dict:
        """紙上買入"""
        symbol = symbol.strip().upper()
        if not symbol or shares <= 0 or price <= 0:
            return {"status": "error", "message": "參數不完整"}

        total = shares * price
        commission = max(total * COMMISSION_RATE, MIN_COMMISSION)
        total_cost = total + commission

        conn = duckdb.connect(self.db_path)
        balance = float(conn.execute("SELECT balance FROM paper_account WHERE id=1").fetchone()[0])

        if total_cost > balance:
            conn.close()
            return {"status": "error", "message": f"資金不足！需要 ${total_cost:,.0f}，可用 ${balance:,.0f}"}

        # 扣款
        new_balance = balance - total_cost
        conn.execute("UPDATE paper_account SET balance = ? WHERE id=1", [new_balance])

        # 更新持倉
        existing = conn.execute(
            "SELECT id, shares, avg_cost FROM paper_positions WHERE symbol=?", [symbol]
        ).fetchone()
        if existing:
            old_shares = existing[1]
            old_cost = float(existing[2])
            new_shares = old_shares + shares
            new_cost = (old_shares * old_cost + total) / new_shares
            conn.execute(
                "UPDATE paper_positions SET shares=?, avg_cost=?, updated_at=CURRENT_TIMESTAMP WHERE symbol=?",
                [new_shares, round(new_cost, 4), symbol]
            )
        else:
            next_id = conn.execute("SELECT nextval('paper_positions_seq')").fetchone()[0]
            conn.execute(
                "INSERT INTO paper_positions (id, symbol, name, shares, avg_cost, market, strategy) VALUES (?,?,?,?,?,?,?)",
                [next_id, symbol, name or symbol, shares, price, 'TW', strategy]
            )

        # 紀錄委託
        order_id = conn.execute("SELECT nextval('paper_orders_seq')").fetchone()[0]
        conn.execute(
            "INSERT INTO paper_orders (id, symbol, name, side, shares, price, total, commission, status, strategy) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            [order_id, symbol, name or symbol, 'BUY', shares, price, round(total, 2), round(commission, 2), 'FILLED', strategy]
        )
        conn.close()

        return {
            "status": "success",
            "message": f"📈 買入 {name or symbol} ({symbol}) {shales}股 @${price:.2f}",
            "order_id": order_id,
            "total_cost": round(total_cost, 2),
            "commission": round(commission, 2),
            "new_balance": round(new_balance, 2),
        }

    def sell(self, symbol: str, shares: int, price: float,
             strategy: str = "manual", note: str = "") -> dict:
        """紙上賣出"""
        symbol = symbol.strip().upper()
        if not symbol or shares <= 0 or price <= 0:
            return {"status": "error", "message": "參數不完整"}

        conn = duckdb.connect(self.db_path)
        pos = conn.execute(
            "SELECT id, name, shares, avg_cost FROM paper_positions WHERE symbol=?", [symbol]
        ).fetchone()
        if not pos:
            conn.close()
            return {"status": "error", "message": f"未持有 {symbol}"}

        pos_id, name, cur_shares, avg_cost = pos[0], pos[1], pos[2], float(pos[3])
        if shares > cur_shares:
            conn.close()
            return {"status": "error", "message": f"賣出股數 ({shares}) 超過持有 ({cur_shares})"}

        total = shares * price
        commission = max(total * COMMISSION_RATE, MIN_COMMISSION)
        tax = total * TAX_RATE
        net_proceeds = total - commission - tax
        realized_pnl = (price - avg_cost) * shares - commission - tax

        # 加回現金
        balance = float(conn.execute("SELECT balance FROM paper_account WHERE id=1").fetchone()[0])
        new_balance = balance + net_proceeds
        conn.execute("UPDATE paper_account SET balance = ? WHERE id=1", [new_balance])

        # 更新持倉
        remaining = cur_shares - shares
        if remaining == 0:
            conn.execute("DELETE FROM paper_positions WHERE symbol=?", [symbol])
        else:
            conn.execute(
                "UPDATE paper_positions SET shares=?, updated_at=CURRENT_TIMESTAMP WHERE symbol=?",
                [remaining, symbol]
            )

        # 紀錄委託
        order_id = conn.execute("SELECT nextval('paper_orders_seq')").fetchone()[0]
        conn.execute(
            "INSERT INTO paper_orders (id, symbol, name, side, shares, price, total, commission, tax, status, strategy, note) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [order_id, symbol, name, 'SELL', shares, price, round(total, 2),
             round(commission, 2), round(tax, 2), 'FILLED', strategy, note]
        )
        conn.close()

        return {
            "status": "success",
            "message": f"📉 賣出 {name} ({symbol}) {shares}股 @${price:.2f}",
            "order_id": order_id,
            "net_proceeds": round(net_proceeds, 2),
            "realized_pnl": round(realized_pnl, 2),
            "commission": round(commission, 2),
            "tax": round(tax, 2),
            "new_balance": round(new_balance, 2),
            "remaining_shares": remaining,
        }

    # ─── 委託歷史 ───
    def get_orders(self, limit: int = 50) -> list:
        conn = duckdb.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, symbol, name, side, shares, price, total, commission, tax, status, strategy, note, created_at "
            "FROM paper_orders ORDER BY created_at DESC LIMIT ?", [limit]
        ).fetchall()
        conn.close()
        return [
            {
                "id": r[0], "symbol": r[1], "name": r[2], "side": r[3],
                "shares": r[4], "price": round(float(r[5]), 2),
                "total": round(float(r[6]), 2), "commission": round(float(r[7]), 2),
                "tax": round(float(r[8]), 2), "status": r[9], "strategy": r[10],
                "note": r[11], "created_at": str(r[12])
            }
            for r in rows
        ]

    # ─── 績效指標 ───
    def get_performance(self) -> dict:
        conn = duckdb.connect(self.db_path)
        acc = self.get_account()

        orders = conn.execute(
            "SELECT side, shares, price, total, created_at FROM paper_orders WHERE status='FILLED' ORDER BY created_at"
        ).fetchall()
        conn.close()

        # 交易統計
        trades = []
        pending_buy = None
        for o in orders:
            side, shares, price, total, ts = o
            if side == 'BUY':
                pending_buy = {"shares": shares, "price": float(price), "cost": float(total), "ts": str(ts)}
            elif side == 'SELL' and pending_buy:
                buy_price = pending_buy["price"]
                sell_price = float(price)
                pnl_pct = (sell_price - buy_price) / buy_price * 100
                trades.append({
                    "buy_ts": pending_buy["ts"],
                    "sell_ts": str(ts),
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "win": pnl_pct > 0
                })
                pending_buy = None

        wins = sum(1 for t in trades if t["win"])
        total_trades = len(trades)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        avg_win = sum(t["pnl_pct"] for t in trades if t["win"]) / wins if wins > 0 else 0
        avg_loss = sum(t["pnl_pct"] for t in trades if not t["win"]) / (total_trades - wins) if total_trades > wins else 0

        # 最大回撤（簡化版 — 從帳戶總值歷史推算）
        # 這裡用已實現損益的累計
        cum_pnl = 0
        max_cum = 0
        max_drawdown = 0
        for t in trades:
            cum_pnl += t["pnl_pct"]
            max_cum = max(max_cum, cum_pnl)
            drawdown = max_cum - cum_pnl
            max_drawdown = max(max_drawdown, drawdown)

        return {
            "initial_balance": acc["initial_balance"],
            "total_assets": acc["total_assets"],
            "total_return": acc["total_return"],
            "total_return_pct": acc["total_return_pct"],
            "total_trades": total_trades,
            "wins": wins,
            "losses": total_trades - wins,
            "win_rate": round(win_rate, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "profit_factor": round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
        }

    # ─── 策略設定 ───
    def get_strategy_config(self) -> dict:
        conn = duckdb.connect(self.db_path)
        row = conn.execute("""
            SELECT strategy_name, is_running, interval_minutes, max_position_pct,
                   stop_loss_pct, take_profit_pct, symbols, params, started_at, updated_at
            FROM paper_strategy_config WHERE id=1
        """).fetchone()
        if not row:
            conn.execute("INSERT INTO paper_strategy_config DEFAULT VALUES")
            row = conn.execute("""SELECT strategy_name, is_running, interval_minutes, max_position_pct,
                   stop_loss_pct, take_profit_pct, symbols, params, started_at, updated_at
            FROM paper_strategy_config WHERE id=1""").fetchone()
        conn.close()

        import json
        return {
            "strategy_name": row[0],
            "is_running": bool(row[1]),  # 轉 Python bool
            "interval_minutes": row[2],
            "max_position_pct": float(row[3]),
            "stop_loss_pct": float(row[4]),
            "take_profit_pct": float(row[5]),
            "symbols": row[6] or "",
            "params": json.loads(row[7]) if row[7] else {},
            "started_at": str(row[8]) if row[8] else None,
            "updated_at": str(row[9]),
        }

    def update_strategy_config(self, **kwargs) -> dict:
        conn = duckdb.connect(self.db_path)
        row = conn.execute("SELECT COUNT(*) FROM paper_strategy_config WHERE id=1").fetchone()
        if row[0] == 0:
            conn.execute("INSERT INTO paper_strategy_config DEFAULT VALUES")

        allowed = ["strategy_name", "is_running", "interval_minutes",
                   "max_position_pct", "stop_loss_pct", "take_profit_pct", "symbols", "params"]
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k in allowed:
                if k == "params":
                    import json
                    v = json.dumps(v)
                if k == "is_running" and v:
                    sets.append("started_at = CURRENT_TIMESTAMP")
                elif k == "is_running" and not v:
                    sets.append("started_at = NULL")
                sets.append(f"{k} = ?")
                vals.append(v)

        if sets:
            sets.append("updated_at = CURRENT_TIMESTAMP")
            conn.execute(f"UPDATE paper_strategy_config SET {', '.join(sets)} WHERE id=1", vals)
        conn.close()
        return self.get_strategy_config()

    # ─── 重置帳戶 ───
    def reset(self, initial_balance: float = 1000000) -> dict:
        conn = duckdb.connect(self.db_path)
        conn.execute("DELETE FROM paper_positions")
        conn.execute("DELETE FROM paper_orders")
        conn.execute("UPDATE paper_account SET balance=?, initial_balance=?", [initial_balance, initial_balance])
        conn.close()
        return {"status": "success", "message": f"帳戶已重置，初始資金 ${initial_balance:,.0f}", "balance": initial_balance}

    # ─── 任務目標系統 ───
    def create_mission(self, description: str,
                       risk_level: str = "medium",
                       timeframe_days: int = 90,
                       target_return_pct: float = 10.0,
                       max_positions: int = 5,
                       max_position_pct: float = 0.20,
                       stop_loss_pct: float = 0.05,
                       take_profit_pct: float = 0.15,
                       allow_margin: bool = False,
                       preferred_market: str = "TW",
                       scan_frequency: str = "daily") -> dict:
        """建立投資任務目標"""
        conn = duckdb.connect(self.db_path)
        mission_id = conn.execute("SELECT nextval('paper_missions_seq')").fetchone()[0]

        acc = self.get_account()
        balance = acc["total_assets"]
        deadline = datetime.now() + timedelta(days=timeframe_days)

        conn.execute("""
            INSERT INTO paper_missions (id, description, risk_level, timeframe_days,
                target_return_pct, max_positions, max_position_pct, stop_loss_pct,
                take_profit_pct, allow_margin, preferred_market, scan_frequency,
                start_balance, current_balance, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [mission_id, description, risk_level, timeframe_days,
              target_return_pct, max_positions, max_position_pct,
              stop_loss_pct, take_profit_pct, allow_margin,
              preferred_market, scan_frequency, balance, balance, deadline])
        conn.close()

        return {
            "status": "success",
            "mission_id": mission_id,
            "description": description,
            "risk_level": risk_level,
            "timeframe_days": timeframe_days,
            "target_return_pct": target_return_pct,
            "start_balance": round(balance, 2),
            "deadline": deadline.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_mission_progress(self, mission_id: int = None) -> dict:
        """查詢任務進度。若不指定 mission_id，回傳最新活躍任務"""
        conn = duckdb.connect(self.db_path)

        if mission_id:
            row = conn.execute(
                "SELECT * FROM paper_missions WHERE id=?", [mission_id]
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM paper_missions WHERE status='active' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()

        if not row:
            conn.close()
            return {"status": "error", "message": "找不到活躍的任務"}

        # 更新 current_balance
        acc = self.get_account()
        current_balance = acc["total_assets"]
        conn.execute("UPDATE paper_missions SET current_balance=? WHERE id=?", [current_balance, row[0]])

        mission = {
            "id": row[0], "description": row[1], "risk_level": row[2],
            "timeframe_days": row[3], "target_return_pct": float(row[4]),
            "max_positions": row[5], "max_position_pct": float(row[6]),
            "stop_loss_pct": float(row[7]), "take_profit_pct": float(row[8]),
            "allow_margin": bool(row[9]), "preferred_market": row[10],
            "scan_frequency": row[11], "status": row[12],
            "start_balance": float(row[13]), "current_balance": current_balance,
            "start_date": str(row[15]), "deadline": str(row[16]),
            "completed_at": str(row[17]) if row[17] else None,
            "note": row[18] or "",
        }

        # 計算進度
        start = mission["start_balance"]
        target = start * (1 + mission["target_return_pct"] / 100)
        current = mission["current_balance"]
        progress_pct = ((current - start) / (target - start) * 100) if target != start else 0
        elapsed = (datetime.now() - datetime.strptime(mission["start_date"][:19], "%Y-%m-%d %H:%M:%S")).days
        remaining_days = max(0, mission["timeframe_days"] - elapsed)
        current_return_pct = ((current - start) / start * 100) if start > 0 else 0

        mission["progress_pct"] = round(max(0, min(100, progress_pct)), 1)
        mission["elapsed_days"] = elapsed
        mission["remaining_days"] = remaining_days
        mission["current_return_pct"] = round(current_return_pct, 2)
        mission["on_track"] = progress_pct >= (elapsed / mission["timeframe_days"] * 100) if mission["timeframe_days"] > 0 else True

        conn.close()
        return {"status": "success", "mission": mission}

    # ─── 調整帳戶資金（保留持倉不變）───
    def adjust_balance(self, new_balance: float) -> dict:
        """調整帳戶現金餘額，同步更新 initial_balance"""
        conn = duckdb.connect(self.db_path)
        old = conn.execute("SELECT balance, initial_balance FROM paper_account WHERE id=1").fetchone()
        if not old:
            conn.close()
            return {"status": "error", "message": "帳戶不存在"}
        old_balance = float(old[0])
        old_initial = float(old[1])
        adjustment = new_balance - old_balance
        new_initial = old_initial + adjustment
        conn.execute("UPDATE paper_account SET balance=?, initial_balance=?", [new_balance, new_initial])
        conn.close()
        return {
            "status": "success",
            "old_balance": old_balance,
            "new_balance": new_balance,
            "adjustment": adjustment,
        }

    # ─── Phase 2 輔助方法 ───

    def get_open_positions(self) -> list:
        """取得當前所有持倉（別名，與 get_positions 相同）"""
        return self.get_positions()

    def get_cash_balance(self) -> float:
        """取得可用現金餘額"""
        acc = self.get_account()
        return acc.get("balance", 0.0)

    def get_total_equity(self) -> float:
        """取得總權益（現金 + 持倉市值）"""
        acc = self.get_account()
        return acc.get("total_assets", 0.0)

    def get_position_symbols(self) -> list:
        """取得目前持有的所有股票代碼清單"""
        positions = self.get_positions()
        return [p["symbol"] for p in positions]

    def get_position_count(self) -> int:
        """取得目前持股數量"""
        conn = duckdb.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM paper_positions").fetchone()[0]
        conn.close()
        return count

    # ─── 內部：即時價格 ───
    @staticmethod
    def _get_current_price(symbol: str) -> Optional[float]:
        """取得個股即時價格（含上市上櫃判斷）"""
        try:
            import yfinance as yf
            if symbol.isdigit():
                # 台股：先試 TWSE，再試 TPEX
                for suffix in ['.TW', '.TWO']:
                    try:
                        t = yf.Ticker(f"{symbol}{suffix}")
                        p = t.fast_info.get('last_price')
                        if p:
                            return float(p)
                    except:
                        continue
                # fallback: info
                for suffix in ['.TW', '.TWO']:
                    try:
                        t = yf.Ticker(f"{symbol}{suffix}")
                        p = t.info.get('currentPrice') or t.info.get('regularMarketPreviousClose')
                        if p:
                            return float(p)
                    except:
                        continue
            else:
                # 美股
                t = yf.Ticker(symbol)
                p = t.fast_info.get('last_price') or t.info.get('currentPrice')
                if p:
                    return float(p)
        except:
            pass
        return None


# ─── 任務追蹤器 ───
class MissionTracker:
    """任務進度追蹤器 — 定期評估任務進度並提供調整建議"""

    def __init__(self, engine: PaperTradingEngine = None):
        self.engine = engine or paper_engine

    def evaluate(self, mission_id: int = None) -> dict:
        """評估任務進度，回傳狀態與建議"""
        result = self.engine.get_mission_progress(mission_id)
        if result.get("status") != "success":
            return result

        mission = result["mission"]

        # 計算風險指標
        perf = self.engine.get_performance()
        positions = self.engine.get_positions()

        evaluation = {
            "mission_id": mission["id"],
            "on_track": mission["on_track"],
            "progress_pct": mission["progress_pct"],
            "current_return_pct": mission["current_return_pct"],
            "target_return_pct": mission["target_return_pct"],
            "elapsed_days": mission["elapsed_days"],
            "remaining_days": mission["remaining_days"],
            "suggestions": [],
            "alerts": [],
        }

        # 進度評估
        if mission["progress_pct"] >= 100:
            evaluation["status"] = "completed"
            evaluation["alerts"].append("🎉 已達成目標！建議考慮止盈或提高目標。")
        elif mission["progress_pct"] < 0:
            evaluation["status"] = "behind"
            evaluation["alerts"].append("⚠️ 目前虧損中，需重新評估策略。")
        elif mission["progress_pct"] < (mission["elapsed_days"] / mission["timeframe_days"] * 100 * 0.5):
            evaluation["status"] = "lagging"
            evaluation["alerts"].append("📉 進度落後，建議增加掃描頻率或放寬選股條件。")
        elif not mission["on_track"]:
            evaluation["status"] = "slightly_behind"
            evaluation["alerts"].append("⏳ 略低於進度線，持續觀察。")
        else:
            evaluation["status"] = "on_track"

        # 持股集中度檢查
        if len(positions) >= mission["max_positions"]:
            evaluation["suggestions"].append(
                f"📦 持股已達上限 ({mission['max_positions']} 檔)，若要換股需先賣出。"
            )

        # 時間壓力檢查
        if mission["remaining_days"] <= 7 and not mission["on_track"]:
            evaluation["suggestions"].append(
                "⏰ 時間緊迫且進度落後，可考慮提高風險容忍度或接受未達標。"
            )

        # 最大回撤檢查
        if perf.get("max_drawdown_pct", 0) > 15:
            evaluation["suggestions"].append(
                f"📉 最大回撤已達 {perf['max_drawdown_pct']}%，建議檢視風控參數。"
            )

        return {"status": "success", "evaluation": evaluation}

    def format_evaluation(self, eval_data: dict) -> str:
        """格式化評估結果"""
        if eval_data.get("status") != "success":
            return f"❌ {eval_data.get('message', '無法評估')}"

        e = eval_data["evaluation"]
        status_emoji = {
            "completed": "🎉", "on_track": "✅", "slightly_behind": "⏳",
            "lagging": "📉", "behind": "⚠️",
        }

        lines = [
            f"📊 **任務進度評估**",
            f"──────────────────────",
            f"{status_emoji.get(e['status'], '📊')} 狀態: **{e['status'].upper()}**",
            f"📈 進度: {e['progress_pct']:.1f}%",
            f"💰 目前報酬: {e['current_return_pct']:+.2f}% / 目標 {e['target_return_pct']:+.2f}%",
            f"📅 已過 {e['elapsed_days']} 天 / 剩餘 {e['remaining_days']} 天",
        ]

        if e["alerts"]:
            lines.append(f"\n🚨 **警報**")
            for a in e["alerts"]:
                lines.append(f"• {a}")

        if e["suggestions"]:
            lines.append(f"\n💡 **建議**")
            for s in e["suggestions"]:
                lines.append(f"• {s}")

        return "\n".join(lines)


# 全域單例
paper_engine = PaperTradingEngine()
mission_tracker = MissionTracker(paper_engine)

