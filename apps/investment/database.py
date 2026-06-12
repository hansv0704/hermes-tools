"""
投資代理人 v3.0 — SQLite 資料層
使用 aiosqlite 支援非同步操作
"""
import aiosqlite
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from .config import DB_PATH
except ImportError:
    from config import DB_PATH

log = logging.getLogger("investment.db")

# ─── 同步初始化（啟動時呼叫） ───
def init_db():
    """初始化資料庫表格（同步）"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    log.info(f"資料庫初始化完成: {DB_PATH}")

# ─── 非同步 helper ───
async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db

# ═══════════════════════════════════════════════
#  SQL Schema
# ═══════════════════════════════════════════════
SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    budget REAL NOT NULL,              -- 起始資金
    target_amount REAL NOT NULL,       -- 目標金額
    current_balance REAL NOT NULL,     -- 目前可用資金
    total_asset REAL NOT NULL,         -- 總資產（現金+持倉市值）
    start_pnl REAL DEFAULT 0,          -- 累計損益
    start_pnl_pct REAL DEFAULT 0,      -- 損益%
    deadline TEXT NOT NULL,            -- ISO 日期
    risk_level TEXT DEFAULT 'moderate',
    mode TEXT DEFAULT 'paper',         -- paper / live
    config TEXT DEFAULT '{}',          -- JSON: 交易閾值設定
    status TEXT DEFAULT 'active',      -- active / paused / completed / failed
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT DEFAULT '',
    shares INTEGER NOT NULL DEFAULT 0,
    avg_cost REAL NOT NULL DEFAULT 0,
    current_price REAL DEFAULT 0,
    market_value REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    unrealized_pnl_pct REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE,
    UNIQUE(mission_id, symbol)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT DEFAULT '',
    side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
    shares INTEGER NOT NULL,
    price REAL NOT NULL,
    total_amount REAL NOT NULL,
    fee REAL DEFAULT 0,
    tax REAL DEFAULT 0,
    reason TEXT DEFAULT '',             -- AI 決策原因
    agent_role TEXT DEFAULT '',         -- 哪個 Agent 做的決策
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL,
    cycle_num INTEGER DEFAULT 0,
    role TEXT DEFAULT 'System',         -- Scout/Analyst/Risk/Executor/Reflector/System
    action TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    detail TEXT DEFAULT '',             -- JSON: 完整決策細節
    created_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_cache (
    symbol TEXT PRIMARY KEY,
    name TEXT DEFAULT '',
    price REAL,
    change_pct REAL,
    volume INTEGER,
    high REAL,
    low REAL,
    open REAL,
    prev_close REAL,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS agent_state (
    mission_id INTEGER PRIMARY KEY,
    loop_active INTEGER DEFAULT 0,
    loop_interval_minutes INTEGER DEFAULT 15,
    last_cycle_at TEXT,
    next_cycle_at TEXT,
    total_cycles INTEGER DEFAULT 0,
    successful_trades INTEGER DEFAULT 0,
    failed_trades INTEGER DEFAULT 0,
    FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE CASCADE
);
"""

# ═══════════════════════════════════════════════
#  Mission CRUD
# ═══════════════════════════════════════════════

async def create_mission(name: str, description: str, budget: float,
                         target_amount: float, deadline: str,
                         risk_level: str = "moderate",
                         mode: str = "paper",
                         config: Optional[Dict] = None) -> int:
    """建立新任務，回傳 mission_id"""
    db = await get_db()
    try:
        cur = await db.execute(
            """INSERT INTO missions (name, description, budget, target_amount,
               current_balance, total_asset, deadline, risk_level, mode, config)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, description, budget, target_amount, budget, budget,
             deadline, risk_level, mode, json.dumps(config or {}, ensure_ascii=False))
        )
        mission_id = cur.lastrowid
        await db.execute(
            "INSERT INTO agent_state (mission_id, loop_interval_minutes) VALUES (?, ?)",
            (mission_id, 15)
        )
        await db.commit()
        return mission_id
    finally:
        await db.close()

async def get_mission(mission_id: int) -> Optional[Dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM missions WHERE id=?", (mission_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()

async def get_active_mission() -> Optional[Dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM missions WHERE status='active' ORDER BY created_at DESC LIMIT 1"
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()

async def list_missions(limit: int = 20) -> List[Dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM missions ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()

async def update_mission_balance(mission_id: int, cash: float, total_asset: float,
                                  pnl: float, pnl_pct: float):
    db = await get_db()
    try:
        await db.execute(
            """UPDATE missions SET current_balance=?, total_asset=?,
               start_pnl=?, start_pnl_pct=?, updated_at=datetime('now','localtime')
               WHERE id=?""",
            (cash, total_asset, pnl, pnl_pct, mission_id)
        )
        await db.commit()
    finally:
        await db.close()

async def complete_mission(mission_id: int, status: str = "completed"):
    db = await get_db()
    try:
        await db.execute(
            """UPDATE missions SET status=?, completed_at=datetime('now','localtime')
               WHERE id=?""",
            (status, mission_id)
        )
        await db.execute(
            "UPDATE agent_state SET loop_active=0 WHERE mission_id=?", (mission_id,)
        )
        await db.commit()
    finally:
        await db.close()

# ═══════════════════════════════════════════════
#  Decision Log
# ═══════════════════════════════════════════════

async def log_decision(mission_id: int, role: str, action: str,
                       summary: str, detail: Dict = None, cycle_num: int = 0):
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO decision_log (mission_id, cycle_num, role, action, summary, detail)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mission_id, cycle_num, role, action, summary,
             json.dumps(detail, ensure_ascii=False) if detail else "{}")
        )
        await db.commit()
    finally:
        await db.close()

async def get_decision_log(mission_id: int, limit: int = 50) -> List[Dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT * FROM decision_log WHERE mission_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (mission_id, limit)
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()

# ═══════════════════════════════════════════════
#  Holdings
# ═══════════════════════════════════════════════

async def upsert_holding(mission_id: int, symbol: str, name: str,
                         shares: int, avg_cost: float):
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO holdings (mission_id, symbol, name, shares, avg_cost)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(mission_id, symbol) DO UPDATE SET
               shares=excluded.shares, avg_cost=excluded.avg_cost,
               updated_at=datetime('now','localtime')""",
            (mission_id, symbol, name, shares, avg_cost)
        )
        await db.commit()
    finally:
        await db.close()

async def get_holdings(mission_id: int) -> List[Dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM holdings WHERE mission_id=? AND shares > 0", (mission_id,)
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()

async def add_transaction(mission_id: int, symbol: str, name: str,
                          side: str, shares: int, price: float,
                          total_amount: float, reason: str = "",
                          agent_role: str = "", fee: float = 0, tax: float = 0):
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO transactions
               (mission_id, symbol, name, side, shares, price, total_amount, fee, tax, reason, agent_role)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mission_id, symbol, name, side, shares, price, total_amount, fee, tax, reason, agent_role)
        )
        await db.commit()
    finally:
        await db.close()

async def get_transactions(mission_id: int, limit: int = 50) -> List[Dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT * FROM transactions WHERE mission_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (mission_id, limit)
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()

# ═══════════════════════════════════════════════
#  Agent State
# ═══════════════════════════════════════════════

async def get_agent_state(mission_id: int) -> Optional[Dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM agent_state WHERE mission_id=?", (mission_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()

async def set_loop_active(mission_id: int, active: bool):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE agent_state SET loop_active=? WHERE mission_id=?",
            (1 if active else 0, mission_id)
        )
        await db.commit()
    finally:
        await db.close()
