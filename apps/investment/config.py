"""
投資代理人 v3.0 — 全局配置
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data_store"
DATA_DIR.mkdir(exist_ok=True)

# ─── 路徑配置 ───
# 使用環境變數優先，否則自動偵測 USERPROFILE 下的 MEGA 目錄
_MEGA_BASE = (
    Path(os.environ.get("USERPROFILE", ""))
    / "Desktop" / "alice" / "ALICE BOT" / "Alice_Brain_Arch_20260506_031953" / "MEGA"
)
MEGA_DLL_DIR = Path(os.getenv(
    "MEGA_DLL_DIR",
    str(_MEGA_BASE / "SpeedyAPI_PY" / "megaapi" / "megaSpeedy")
))
MEGA_PFX_PATH = Path(os.getenv(
    "MEGA_PFX_PATH",
    str(_MEGA_BASE / "MEGARA" / "R124662445.pfx")
))
DB_PATH = DATA_DIR / "investment.db"
LOG_PATH = DATA_DIR / "agent_decision.log"

# ─── 交易參數 ───
MEGA_SERVER_IP = os.getenv("MEGA_SERVER_IP", "spapi.emega.com.tw")
MEGA_SERVER_PORT = int(os.getenv("MEGA_SERVER_PORT", "56789"))
MEGA_QUOTE_PORT = int(os.getenv("MEGA_QUOTE_PORT", "34567"))
MEGA_TIMEOUT_SEC = int(os.getenv("MEGA_TIMEOUT_SEC", "5"))

# ─── 自主循環參數 ───
LOOP_INTERVAL_MINUTES = int(os.getenv("INVEST_LOOP_MINUTES", "15"))  # 每15分鐘一循環
MAX_POSITIONS = int(os.getenv("INVEST_MAX_POSITIONS", "5"))          # 最大持股數
MAX_SINGLE_POSITION_PCT = float(os.getenv("INVEST_MAX_POSITION_PCT", "0.25"))  # 單股上限25%
DEFAULT_STOP_LOSS_PCT = float(os.getenv("INVEST_STOP_LOSS_PCT", "0.07"))       # 預設停損7%
DEFAULT_TAKE_PROFIT_PCT = float(os.getenv("INVEST_TAKE_PROFIT_PCT", "0.15"))   # 預設停利15%
MIN_CASH_RESERVE_PCT = float(os.getenv("INVEST_MIN_CASH_PCT", "0.05"))         # 保留5%現金

# ─── 市場時間 (台灣) ───
MARKET_OPEN = (9, 0)     # 09:00
MARKET_CLOSE = (13, 30)  # 13:30
MARKET_PRE_OPEN = (8, 30) # 08:30 盤前

# ─── 風險等級對應 ───
RISK_PROFILES = {
    "conservative": {"max_positions": 3, "max_single_pct": 0.15, "stop_loss": 0.03, "take_profit": 0.08},
    "moderate":     {"max_positions": 5, "max_single_pct": 0.20, "stop_loss": 0.05, "take_profit": 0.12},
    "aggressive":   {"max_positions": 8, "max_single_pct": 0.30, "stop_loss": 0.08, "take_profit": 0.20},
    "extreme":      {"max_positions": 10, "max_single_pct": 0.40, "stop_loss": 0.12, "take_profit": 0.30},
}

# ─── 伺服器配置 ───
SERVER_HOST = os.getenv("INVEST_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("INVEST_PORT", "5002"))
