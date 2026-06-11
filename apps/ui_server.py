import os
import sys
import logging
import threading
import sqlite3
import time
import duckdb
import yfinance as yf
import asyncio
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from skills.brokerage_engine import engine_manager
from skills.mega_speedy_skill import get_session as get_speedy_session, get_quote_session
from paper_trading_engine import paper_engine
from strategy_engine import get_strategy, STRATEGY_MAP, analyze_symbol, STRATEGY_INFO, MarketScanner, AdaptiveStrategy, _fetch_twse_all_stocks
from autonomous_investment_agent import AutonomousInvestmentAgent, get_agent, reset_agent, THEME_CONCEPT_MAP, _DYNAMIC_CONCEPT_MAP, match_themes_from_text, add_concept_mapping, get_all_themes
from autonomous_loop import get_autonomous_loop, AutonomousLoop

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) # 隱藏 flask request 日誌

# === v4.1: Hermes 整合 — 優先載入 Hermes .env ===
from dotenv import load_dotenv
_hermes_env = os.path.join(os.getenv("HERMES_HOME", os.path.expandvars(r"%LOCALAPPDATA%\hermes")), ".env")
if os.path.exists(_hermes_env):
    load_dotenv(_hermes_env, override=False)  # Hermes .env base
load_dotenv(override=True)  # 本地 .env 覆蓋（向後相容）

app = Flask(__name__)

# 獲取 DuckDB 連線
def get_db_connection():
    return duckdb.connect('alice_core.db')

# ---- 投資分析資料表初始化 ----
def _init_investment_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investment_analysis (
            id INTEGER PRIMARY KEY,
            symbol VARCHAR,
            price DOUBLE,
            change_pct VARCHAR,
            recommendation VARCHAR,
            full_report JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_holdings (
            id INTEGER PRIMARY KEY,
            symbol VARCHAR UNIQUE,
            name VARCHAR,
            shares INTEGER,
            avg_cost DOUBLE,
            market VARCHAR DEFAULT 'US',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            symbol VARCHAR,
            name VARCHAR,
            side VARCHAR CHECK(side IN ('BUY','SELL')),
            shares INTEGER,
            price DOUBLE,
            total DOUBLE,
            market VARCHAR DEFAULT 'US',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS asset_accounts (
            id INTEGER PRIMARY KEY,
            account_name VARCHAR,
            provider VARCHAR,
            balance DOUBLE DEFAULT 0,
            currency VARCHAR DEFAULT 'TWD',
            last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_balance (
            id INTEGER PRIMARY KEY DEFAULT 1,
            balance DOUBLE DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()

# ---- CORS 標頭 ----
@app.after_request
def _add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# 模擬的技能資料庫
SKILLS_DATA = [
  {
    "id": "os_control_skill",
    "name": "OS Control & Desktop Automation",
    "description": "賦予 Alice 操作本機電腦的能力，支援滑鼠點擊、輸入、快捷鍵控制。",
    "icon": "fa-solid fa-desktop",
    "status": "installed",
  },
  {
    "id": "finance_skill",
    "name": "Market & Finance",
    "description": "即時加密貨幣報價與美股台股數據分析。",
    "icon": "fa-solid fa-chart-line",
    "status": "installed",
  },
  {
    "id": "autonomous_trader",
    "name": "24/7 Autonomous Trader",
    "description": "24小時自主投資代理人，具備帳戶連動、策略執行與資產監控能力。",
    "icon": "fa-solid fa-robot",
    "status": "installed",
  },
  {
    "id": "cloud_sync_skill",
    "name": "Google Drive Cloud Sync",
    "description": "自動打包並上傳大腦架構與記憶至 Google 雲端硬碟。",
    "icon": "fa-solid fa-cloud-arrow-up",
    "status": "installed",
  },
  {
    "id": "mcp_skill",
    "name": "MCP Gateway",
    "description": "支援外接 Server (例如 PostgreSQL, Filesystem 等) 讓 Alice 能像插隨身碟一樣讀取外部資源。",
    "icon": "fa-solid fa-database",
    "status": "installed",
  },
  {
    "id": "system_skill",
    "name": "System Utility",
    "description": "系統核心操作：鬧鐘排程、遠端更新、檢視檔案樹狀圖。",
    "icon": "fa-solid fa-microchip",
    "status": "installed",
  },
  {
    "id": "speech_skill",
    "name": "Edge TTS Synthesizer",
    "description": "使用微軟 Edge 語音引擎將 Alice 的文字轉為自然的人聲。",
    "icon": "fa-solid fa-comment-dots",
    "status": "available",
  },
  {
    "id": "learning_skill",
    "name": "Neural Learning Core",
    "description": "賦予 Alice 自我修正與深層記憶能力。可透過使用者指令學習新規則，永遠寫入系統鐵律不遺忘。",
    "icon": "fa-solid fa-brain",
    "status": "installed",
  },
  {
    "id": "token_optimizer_skill",
    "name": "Auto Token Optimizer v3",
    "description": "動態監控並壓縮對話歷史，減少 Token 消費、防止上下文溢出，增強長期對話時的推論效率。",
    "icon": "fa-solid fa-compress",
    "status": "installed",
  },
  {
    "id": "skill_builder_skill",
    "name": "Skill Auto-Creator",
    "description": "當成功解決了複雜的問題，或發現了一套可重複使用的任務流程時，自動將其封裝成一個全新的 Skill。",
    "icon": "fa-solid fa-code",
    "status": "installed",
  },
  {
    "id": "memory_search_skill",
    "name": "FTS5 Persistent Memory",
    "description": "SQLite FTS5 powered full-text search. Allows Alice to retrieve context across sessions effortlessly.",
    "icon": "fa-solid fa-database",
    "status": "installed",
  },
  {
    "id": "self_awareness_skill",
    "name": "Source Code Awareness",
    "description": "賦予自我檢查程式碼的能力。讓 Alice 在系統更新後，能查閱自己的源碼以了解新功能。",
    "icon": "fa-solid fa-code-compare",
    "status": "installed",
  },
  {
    "id": "github_integration_skill",
    "name": "GitHub Search & Learn",
    "description": "Alice 現在可以直接在 GitHub 上搜尋有趣的開源專案、MCP 伺服器，並閱讀原始碼自我學習。",
    "icon": "fa-brands fa-github",
    "status": "installed",
  },
  {
    "id": "codex_integration",
    "name": "Codex UI System",
    "description": "未來的視覺化進階操作介面，支援拖拉式與畫布編輯。",
    "icon": "fa-solid fa-pen-ruler",
    "status": "available",
  }
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/skills', methods=['GET'])
def get_skills():
    return jsonify(SKILLS_DATA)

@app.route('/api/dashboard_data', methods=['GET'])
def dashboard_data():
    try:
        conn = get_db_connection()
        accounts = conn.execute("SELECT account_name, provider, balance, currency, last_sync FROM asset_accounts").fetchall()
        history = conn.execute("SELECT timestamp, total_value_twd FROM asset_history ORDER BY timestamp DESC LIMIT 30").fetchall()
        trades = conn.execute("SELECT symbol, side, entry_price, quantity, status FROM active_trades LIMIT 5").fetchall()
        conn.close()
        
        return jsonify({
            "accounts": [dict(zip(['name', 'provider', 'balance', 'currency', 'last_sync'], row)) for row in accounts],
            "history": [dict(zip(['timestamp', 'value'], row)) for row in history],
            "trades": [dict(zip(['symbol', 'side', 'price', 'quantity', 'status'], row)) for row in trades]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================================================================
#  投資分析 API（整合自 IAS）
# ================================================================

@app.route('/api/investment/health', methods=['GET'])
def investment_health():
    return jsonify({
        "status": "ok",
        "server": "Investment Analyst (Integrated)",
        "version": "1.0.0",
        "port": 5000,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/investment/quote/<symbol>', methods=['GET'])
def investment_quote(symbol):
    """即時報價"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        fast = ticker.fast_info

        price = (
            fast.get('last_price')
            or fast.get('regular_market_previous_close')
            or info.get('currentPrice')
            or info.get('regularMarketPreviousClose')
        )

        if price is None:
            return jsonify({"status": "error", "message": f"無法取得 {symbol} 報價"}), 404

        prev = info.get('previousClose') or info.get('regularMarketPreviousClose')
        change_pct = None
        if prev and prev > 0:
            change_pct = round((price - prev) / prev * 100, 2)

        return jsonify({
            "status": "success",
            "symbol": symbol.upper(),
            "price": price,
            "currency": info.get('currency', 'USD'),
            "change_pct": f"{change_pct:+.2f}%" if change_pct is not None else "N/A",
            "name": info.get('longName') or info.get('shortName', symbol),
            "market": info.get('market', 'N/A'),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  持倉管理 API
# ================================================================

@app.route('/api/portfolio', methods=['GET'])
def api_portfolio():
    """取得所有持倉"""
    try:
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT id, symbol, name, shares, avg_cost, market, added_at, updated_at
            FROM portfolio_holdings ORDER BY symbol
        """).fetchall()
        conn.close()
        holdings = []
        for r in rows:
            holdings.append({
                "id": r[0], "symbol": r[1], "name": r[2],
                "shares": r[3], "avg_cost": float(r[4]),
                "market": r[5], "added_at": str(r[6]), "updated_at": str(r[7])
            })
        return jsonify({"status": "success", "holdings": holdings})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/portfolio/pnl', methods=['GET'])
def api_portfolio_pnl():
    """取得所有持倉含即時損益"""
    try:
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT symbol, name, shares, avg_cost, market FROM portfolio_holdings ORDER BY symbol
        """).fetchall()
        conn.close()

        holdings = []
        total_cost = 0.0
        total_value = 0.0

        # === 1. 持倉數據計算的 For 迴圈 ===
        for r in rows:
            symbol, name, shares, cost, market = r
            cost_basis = shares * cost
            total_cost += cost_basis
            price = None
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                fast = ticker.fast_info
                price = fast.get('last_price') or info.get('currentPrice')
            except:
                pass

            current_value = shares * price if price else cost_basis
            pnl = current_value - cost_basis if price else 0
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 and price else 0
            total_value += current_value

            holdings.append({
                "symbol": symbol, "name": name, "shares": shares,
                "avg_cost": float(cost), "market": market,
                "price": float(price) if price else None,
                "current_value": round(current_value, 2),
                "cost_basis": round(cost_basis, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2)
            })

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        return jsonify({
            "status": "success",
            "holdings": holdings,
            "summary": {
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2)
            }
        })

    # ✨ 修正：這個 except 必須留在第一個函式的最後面（與上面的 return 縮排對齊）
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# === 2. 獨立的 API 路由（徹底與上方的 except 隔開，最左邊不能有空白） ===
@app.route('/api/brokerage/<broker_id>/launch', methods=['POST'])
def brokerage_launch(broker_id):
    """使用憑證 Profile 啟動瀏覽器"""
    try:
        result = _run_async(engine_manager.launch_with_profile(broker_id))
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/portfolio/buy', methods=['POST'])
def api_portfolio_buy():
    """買入股票"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper()
        shares = int(data.get('shares', 0))
        price = float(data.get('price', 0))
        name = data.get('name', symbol)

        if not symbol or shares <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "參數不完整"}), 400

        market = "TW" if (symbol.isdigit() or symbol.endswith(".TW") or symbol.endswith(".TWO")) else "US"
        total = round(shares * price, 2)

        conn = get_db_connection()
        # 記錄交易
        conn.execute("""
            INSERT INTO transactions (symbol, name, side, shares, price, total, market)
            VALUES (?, ?, 'BUY', ?, ?, ?, ?)
        """, [symbol, name, shares, price, total, market])

        # 更新持倉
        existing = conn.execute("SELECT id, shares, avg_cost FROM portfolio_holdings WHERE symbol = ?", [symbol]).fetchone()
        if existing:
            old_shares, old_cost = existing[1], float(existing[2])
            new_shares = old_shares + shares
            new_cost = round((old_shares * old_cost + shares * price) / new_shares, 4)
            conn.execute("UPDATE portfolio_holdings SET shares = ?, avg_cost = ?, name = ?, updated_at = CURRENT_TIMESTAMP WHERE symbol = ?",
                         [new_shares, new_cost, name, symbol])
        else:
            conn.execute("INSERT INTO portfolio_holdings (symbol, name, shares, avg_cost, market) VALUES (?, ?, ?, ?, ?)",
                         [symbol, name, shares, price, market])
        conn.close()

        return jsonify({"status": "success", "message": f"已買入 {name} ({symbol}) {shares}股 @${price:.2f}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/portfolio/sell', methods=['POST'])
def api_portfolio_sell():
    """賣出股票"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper()
        shares = int(data.get('shares', 0))
        price = float(data.get('price', 0))

        if not symbol or shares <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "參數不完整"}), 400

        conn = get_db_connection()
        existing = conn.execute("SELECT name, shares, avg_cost FROM portfolio_holdings WHERE symbol = ?", [symbol]).fetchone()
        if not existing:
            conn.close()
            return jsonify({"status": "error", "message": f"找不到 {symbol} 的持倉"}), 404

        name, cur_shares, avg_cost = existing[0], existing[1], float(existing[2])
        if shares > cur_shares:
            conn.close()
            return jsonify({"status": "error", "message": f"賣出股數 ({shares}) 超過持有 ({cur_shares})"}), 400

        total = round(shares * price, 2)
        conn.execute("""
            INSERT INTO transactions (symbol, name, side, shares, price, total, market)
            VALUES (?, ?, 'SELL', ?, ?, ?, ?)
        """, [symbol, name, shares, price, total, "TW" if symbol.isdigit() else "US"])

        remaining = cur_shares - shares
        if remaining == 0:
            conn.execute("DELETE FROM portfolio_holdings WHERE symbol = ?", [symbol])
        else:
            conn.execute("UPDATE portfolio_holdings SET shares = ?, updated_at = CURRENT_TIMESTAMP WHERE symbol = ?",
                         [remaining, symbol])
        conn.close()

        realized_pnl = round((price - avg_cost) * shares, 2)
        return jsonify({
            "status": "success",
            "message": f"已賣出 {name} ({symbol}) {shares}股 @${price:.2f}",
            "realized_pnl": realized_pnl,
            "remaining_shares": remaining
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  券商自動化 API（台新 / 兆豐 — 三竹 SuperCat）
# ================================================================

def _run_async(coro):
    """在同步 Flask 路由中執行 async 協程"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route('/api/brokerage/accounts', methods=['GET'])
def brokerage_accounts():
    """列出可用券商"""
    try:
        brokers = engine_manager.list_brokers()
        return jsonify({"status": "success", "brokers": brokers})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/brokerage/<broker_id>/login', methods=['POST'])
def brokerage_login(broker_id):
    """登入券商"""
    try:
        result = _run_async(engine_manager.login(broker_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/brokerage/<broker_id>/login_captcha', methods=['POST'])
def brokerage_login_captcha(broker_id):
    """輸入驗證碼完成登入"""
    try:
        data = request.get_json() or {}
        captcha = data.get('captcha', '').strip()
        if not captcha:
            return jsonify({"status": "error", "message": "請提供驗證碼"}), 400
        result = _run_async(engine_manager.login_with_captcha(broker_id, captcha))
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/brokerage/<broker_id>/positions', methods=['GET'])
def brokerage_positions(broker_id):
    """查詢庫存"""
    try:
        result = _run_async(engine_manager.get_positions(broker_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/brokerage/<broker_id>/orders', methods=['GET'])
def brokerage_orders(broker_id):
    """查詢委託"""
    try:
        result = _run_async(engine_manager.get_orders(broker_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/brokerage/<broker_id>/order', methods=['POST'])
def brokerage_place_order(broker_id):
    """下單"""
    try:
        data = request.get_json()
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'BUY')).upper()
        price = float(data.get('price', 0))
        quantity = int(data.get('quantity', 0))
        if not symbol or quantity <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "參數不完整"}), 400
        if side not in ('BUY', 'SELL'):
            return jsonify({"status": "error", "message": "side 必須是 BUY 或 SELL"}), 400
        result = _run_async(engine_manager.place_order(broker_id, symbol, side, price, quantity))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/brokerage/<broker_id>/cancel', methods=['POST'])
def brokerage_cancel_order(broker_id):
    """取消委託"""
    try:
        data = request.get_json() or {}
        order_id = str(data.get('order_id', ''))
        if not order_id:
            return jsonify({"status": "error", "message": "請提供 order_id"}), 400
        result = _run_async(engine_manager.cancel_order(broker_id, order_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/brokerage/<broker_id>/balance', methods=['GET'])
def brokerage_balance(broker_id):
    """查詢帳戶餘額"""
    try:
        result = _run_async(engine_manager.get_balance(broker_id))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI 行情路由（spdQuoteAPI — 股票基本資料含中文名稱）
# ================================================================

@app.route('/api/speedy/quotes/connect', methods=['POST'])
def speedy_quotes_connect():
    """連線行情主機，下載全部股票基本資料（含中文名稱）"""
    try:
        data = request.get_json() or {}
        user_id = str(data.get('user_id', '')).strip()
        password = str(data.get('password', '')).strip()

        if not user_id or not password:
            return jsonify({"status": "error", "message": "請提供身分證字號與密碼"}), 400

        session = get_quote_session()
        result = session.connect_and_download(user_id, password)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/quotes/disconnect', methods=['POST'])
def speedy_quotes_disconnect():
    """中斷行情連線"""
    try:
        session = get_quote_session()
        result = session.disconnect()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/quotes/status', methods=['GET'])
def speedy_quotes_status():
    """查詢行情連線狀態"""
    try:
        session = get_quote_session()
        return jsonify({"status": "success", **session.get_status()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/quotes/stocks', methods=['GET'])
def speedy_quotes_stocks():
    """取得全部股票基本資料（含中文名稱、參考價）"""
    try:
        session = get_quote_session()
        stocks = session.get_all_stocks()
        return jsonify({"status": "success", "count": len(stocks), "stocks": stocks})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/quotes/stock/<symbol>', methods=['GET'])
def speedy_quotes_stock(symbol):
    """查詢單一股票基本資料（含中文名稱）"""
    try:
        session = get_quote_session()
        info = session.get_stock_info(symbol.upper())
        return jsonify({"status": "success", **info})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/quotes/search', methods=['GET'])
def speedy_quotes_search():
    """用關鍵字搜尋股票名稱"""
    try:
        keyword = request.args.get('q', '').strip()
        if not keyword:
            return jsonify({"status": "error", "message": "請提供搜尋關鍵字 q"}), 400
        session = get_quote_session()
        results = session.search_stocks_by_name(keyword)
        return jsonify({"status": "success", "count": len(results), "results": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI — 即時行情訂閱 (SSE 推送)
# ================================================================

import queue
_sse_queues: list = []  # 所有 SSE 客戶端的 queue 清單

@app.route('/api/speedy/quotes/subscribe/stream', methods=['GET'])
def speedy_quotes_subscribe_stream():
    """SSE 即時報價推送（Server-Sent Events）。
    客戶端連線後，伺服器每秒推送新事件。
    """
    def generate():
        q = queue.Queue()
        _sse_queues.append(q)
        try:
            # 初始推送：目前訂閱清單
            session = get_quote_session()
            yield f"data: {json.dumps({'type': 'connected', 'subscribed': session.get_all_subscribed()})}\n\n"
            while True:
                try:
                    # 每秒輪詢新事件
                    events = session.pop_new_events()
                    if events:
                        for evt in events:
                            yield f"data: {json.dumps(evt, ensure_ascii=False, default=str)}\n\n"
                    else:
                        # 每 5 秒送一次 heartbeat
                        yield f": heartbeat\n\n"
                    time.sleep(1)
                except GeneratorExit:
                    break
                except Exception:
                    time.sleep(1)
        finally:
            _sse_queues.remove(q)
    return app.response_class(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )

@app.route('/api/speedy/quotes/subscribe/add', methods=['POST'])
def speedy_quotes_subscribe_add():
    """新增即時報價訂閱"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols', [])
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(',') if s.strip()]
        if not symbols:
            return jsonify({"status": "error", "message": "請提供 symbols 清單"}), 400
        session = get_quote_session()
        result = session.subscribe(symbols)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/quotes/subscribe/remove', methods=['POST'])
def speedy_quotes_subscribe_remove():
    """移除即時報價訂閱"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols', [])
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(',') if s.strip()]
        if not symbols:
            return jsonify({"status": "error", "message": "請提供 symbols 清單"}), 400
        session = get_quote_session()
        result = session.unsubscribe(symbols)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/quotes/subscribe/list', methods=['GET'])
def speedy_quotes_subscribe_list():
    """列出已訂閱標的"""
    try:
        session = get_quote_session()
        return jsonify({"status": "success", "subscribed": session.get_all_subscribed()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/quotes/realtime/<symbol>', methods=['GET'])
def speedy_quotes_realtime(symbol):
    """取得指定標的的即時報價快照"""
    try:
        session = get_quote_session()
        quote = session.get_realtime_quote(symbol.upper())
        return jsonify({"status": "success", **quote})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI K線路由（spdOrderAPI — 日/周/月K，含中文名稱）
# ================================================================

@app.route('/api/speedy/kline/<symbol>', methods=['GET'])
def speedy_kline(symbol):
    """取得個股 K 線資料（含中文名稱 + 技術指標）"""
    try:
        period = request.args.get('period', 'daily')
        session = get_speedy_session()
        result = session.get_kline(symbol.upper(), period)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/kline_adjusted/<symbol>', methods=['GET'])
def speedy_kline_adjusted(symbol):
    """取得個股還原 K 線資料（還原權息）"""
    try:
        period = request.args.get('period', 'daily')
        session = get_speedy_session()
        result = session.get_adjusted_kline(symbol.upper(), period)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI 交易路由（DLL 原生連線，非 Playwright）
# ================================================================

@app.route('/api/speedy/connect', methods=['POST'])
def speedy_connect():
    """連線 + 憑證 + 登入"""
    try:
        data = request.get_json() or {}
        user_id = str(data.get('user_id', '')).strip()
        password = str(data.get('password', '')).strip()
        account = str(data.get('account', '')).strip()
        broker_id = str(data.get('broker_id', '')).strip()
        pfx_password = str(data.get('pfx_password', '')).strip()

        if not all([user_id, password, account, broker_id, pfx_password]):
            return jsonify({"status": "error", "message": "請填寫所有欄位（身分證、密碼、帳號、分公司、憑證密碼）"}), 400

        session = get_speedy_session()
        result = session.connect_and_login(user_id, password, account, broker_id, pfx_password)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/disconnect', methods=['POST'])
def speedy_disconnect():
    """斷線"""
    try:
        session = get_speedy_session()
        result = session.disconnect()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/status', methods=['GET'])
def speedy_status():
    """查詢連線狀態"""
    try:
        session = get_speedy_session()
        return jsonify({"status": "success", **session.get_status()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/positions', methods=['GET'])
def speedy_positions():
    """查詢證券庫存"""
    try:
        session = get_speedy_session()
        result = session.query_positions()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/orders', methods=['GET'])
def speedy_orders():
    """查詢當日委託"""
    try:
        session = get_speedy_session()
        result = session.query_orders()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/matches', methods=['GET'])
def speedy_matches():
    """查詢當日成交"""
    try:
        session = get_speedy_session()
        result = session.query_matches()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/order', methods=['POST'])
def speedy_place_order():
    """下單"""
    try:
        data = request.get_json() or {}
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'BUY')).upper()
        price = float(data.get('price', 0))
        quantity = int(data.get('quantity', 0))
        market = str(data.get('market', 'tse')).lower()

        if not symbol or quantity <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "參數不完整"}), 400
        if side not in ('BUY', 'SELL'):
            return jsonify({"status": "error", "message": "side 必須是 BUY 或 SELL"}), 400

        session = get_speedy_session()
        result = session.place_order(symbol, side, price, quantity, market)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/speedy/cancel', methods=['POST'])
def speedy_cancel_order():
    """取消委託"""
    try:
        data = request.get_json() or {}
        order_id = str(data.get('order_id', '')).strip()
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'B')).upper()

        if not order_id:
            return jsonify({"status": "error", "message": "請提供 order_id"}), 400

        session = get_speedy_session()
        result = session.cancel_order(order_id, symbol, side)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI — 改單
# ================================================================

@app.route('/api/speedy/replace', methods=['POST'])
def speedy_replace_order():
    """改單（改價/減量）"""
    try:
        data = request.get_json() or {}
        order_id = str(data.get('order_id', '')).strip()
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'BUY')).upper()
        new_price = float(data.get('new_price', 0))
        new_quantity = int(data.get('new_quantity', 0))
        market = str(data.get('market', 'tse')).lower()

        if not order_id or not symbol:
            return jsonify({"status": "error", "message": "請提供 order_id 與 symbol"}), 400
        if new_price <= 0 and new_quantity <= 0:
            return jsonify({"status": "error", "message": "請提供 new_price 或 new_quantity"}), 400

        session = get_speedy_session()
        result = session.replace_order(order_id, symbol, side, new_price, new_quantity, market)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI — 海外股票
# ================================================================

@app.route('/api/speedy/foreign/order', methods=['POST'])
def speedy_foreign_order():
    """海外股票下單"""
    try:
        data = request.get_json() or {}
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'BUY')).upper()
        price = float(data.get('price', 0))
        quantity = int(data.get('quantity', 0))
        exchange = str(data.get('exchange', 'US')).upper()
        order_type = str(data.get('order_type', 'L'))
        stop_price = float(data.get('stop_price', 0))
        currency = str(data.get('currency', '2'))

        if not symbol or quantity <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "參數不完整"}), 400

        session = get_speedy_session()
        result = session.place_foreign_order(symbol, side, price, quantity, exchange, order_type, "R", stop_price, currency)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign/cancel', methods=['POST'])
def speedy_foreign_cancel():
    """海外股票刪單"""
    try:
        data = request.get_json() or {}
        order_id = str(data.get('order_id', '')).strip()
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'B')).upper()
        exchange = str(data.get('exchange', 'US')).upper()

        if not order_id:
            return jsonify({"status": "error", "message": "請提供 order_id"}), 400

        session = get_speedy_session()
        result = session.cancel_foreign_order(order_id, symbol, side, exchange)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign/positions', methods=['GET'])
def speedy_foreign_positions():
    """查詢海外股票庫存"""
    try:
        session = get_speedy_session()
        result = session.query_foreign_inventory()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign/orders', methods=['GET'])
def speedy_foreign_orders():
    """查詢海外股票委託"""
    try:
        qry_kind = request.args.get('qry_kind', '0')
        session = get_speedy_session()
        result = session.query_foreign_orders(qry_kind)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign/matches', methods=['GET'])
def speedy_foreign_matches():
    """查詢海外股票成交"""
    try:
        session = get_speedy_session()
        result = session.query_foreign_matches()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign/products', methods=['GET'])
def speedy_foreign_products():
    """下載海外股票商品資料"""
    try:
        session = get_speedy_session()
        result = session.download_foreign_products()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign/currency', methods=['GET'])
def speedy_foreign_currency():
    """下載海外股票幣別資料"""
    try:
        session = get_speedy_session()
        result = session.download_foreign_currency()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign/markets', methods=['GET'])
def speedy_foreign_markets():
    """下載海外股票市場資料"""
    try:
        session = get_speedy_session()
        result = session.download_foreign_markets()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI — 海外期貨
# ================================================================

@app.route('/api/speedy/foreign_fut/order', methods=['POST'])
def speedy_foreign_fut_order():
    """海外期貨下單"""
    try:
        data = request.get_json() or {}
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'BUY')).upper()
        price = float(data.get('price', 0))
        quantity = int(data.get('quantity', 0))
        maturity = str(data.get('maturity', '')).strip()
        exchange = str(data.get('exchange', '')).upper()
        stop_price = float(data.get('stop_price', 0))
        order_type = str(data.get('order_type', 'L'))

        if not symbol or quantity <= 0 or not maturity:
            return jsonify({"status": "error", "message": "參數不完整（symbol, quantity, maturity 為必填）"}), 400

        session = get_speedy_session()
        result = session.place_foreign_fut_order(symbol, side, price, quantity, maturity, exchange, stop_price, 1, order_type)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign_fut/cancel', methods=['POST'])
def speedy_foreign_fut_cancel():
    """海外期貨刪單"""
    try:
        data = request.get_json() or {}
        order_id = str(data.get('order_id', '')).strip()
        exchange = str(data.get('exchange', '')).upper()

        if not order_id:
            return jsonify({"status": "error", "message": "請提供 order_id"}), 400

        session = get_speedy_session()
        result = session.cancel_foreign_fut_order(order_id, exchange)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/foreign_fut/replace', methods=['POST'])
def speedy_foreign_fut_replace():
    """海外期貨改單"""
    try:
        data = request.get_json() or {}
        order_id = str(data.get('order_id', '')).strip()
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'BUY')).upper()
        maturity = str(data.get('maturity', '')).strip()
        exchange = str(data.get('exchange', '')).upper()
        new_price = float(data.get('new_price', 0))
        new_quantity = int(data.get('new_quantity', 0))
        stop_price = float(data.get('stop_price', 0))
        order_type = str(data.get('order_type', 'L'))

        if not order_id or not symbol:
            return jsonify({"status": "error", "message": "請提供 order_id 與 symbol"}), 400

        session = get_speedy_session()
        result = session.replace_foreign_fut_order(order_id, symbol, side, maturity, exchange, new_price, new_quantity, stop_price, 1, order_type)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI — 國內期貨
# ================================================================

@app.route('/api/speedy/fut/orders', methods=['GET'])
def speedy_fut_orders():
    """查詢期貨當日委託"""
    try:
        qry_type = request.args.get('qry_type', '0')
        apcode = request.args.get('apcode', '')
        session = get_speedy_session()
        result = session.query_fut_orders(qry_type, apcode)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/fut/matches', methods=['GET'])
def speedy_fut_matches():
    """查詢期貨當日成交"""
    try:
        apcode = request.args.get('apcode', '')
        session = get_speedy_session()
        result = session.query_fut_matches(apcode)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/fut/uncover', methods=['GET'])
def speedy_fut_uncover():
    """查詢期貨未平倉"""
    try:
        password = request.args.get('password', '')
        session = get_speedy_session()
        result = session.query_fut_uncover(password)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/fut/uncover_rt', methods=['GET'])
def speedy_fut_uncover_rt():
    """查詢期貨即時未平倉"""
    try:
        symbol = request.args.get('symbol', '')
        currency = request.args.get('currency', '')
        session = get_speedy_session()
        result = session.query_fut_uncover_rt(symbol, currency)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI — 保證金
# ================================================================

@app.route('/api/speedy/margin', methods=['GET'])
def speedy_margin():
    """查詢期貨權益數與保證金"""
    try:
        qry_type = request.args.get('qry_type', '0')
        password = request.args.get('password', '')
        session = get_speedy_session()
        result = session.query_margin(qry_type, password)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  兆豐 SpeedyAPI — 變更密碼
# ================================================================

@app.route('/api/speedy/change_password', methods=['POST'])
def speedy_change_password():
    """變更電子交易密碼"""
    try:
        data = request.get_json() or {}
        old_pwd = str(data.get('old_password', '')).strip()
        new_pwd = str(data.get('new_password', '')).strip()

        if not old_pwd or not new_pwd:
            return jsonify({"status": "error", "message": "請提供舊密碼與新密碼"}), 400

        session = get_speedy_session()
        result = session.change_password(old_pwd, new_pwd)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/config', methods=['GET'])
def speedy_config():
    """從 .env 讀取 SpeedyAPI 連線參數（不含密碼，僅供前端預填）"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return jsonify({
            "status": "success",
            "user_id": os.getenv("MEGA_ID", ""),
            "account": os.getenv("MEGA_ACCOUNT", ""),
            "broker_id": os.getenv("MEGA_BRANCH", "")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  銀行餘額管理 API
# ================================================================

@app.route('/api/bank/balance', methods=['GET'])
def bank_balance_get():
    """取得銀行現金餘額"""
    try:
        conn = get_db_connection()
        row = conn.execute("SELECT balance, updated_at FROM bank_balance WHERE id = 1").fetchone()
        conn.close()
        if row:
            return jsonify({
                "status": "success",
                "balance": float(row[0]),
                "updated_at": str(row[1])
            })
        else:
            return jsonify({"status": "success", "balance": 0, "updated_at": None})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/bank/balance', methods=['POST'])
def bank_balance_update():
    """更新銀行現金餘額"""
    try:
        data = request.get_json() or {}
        balance = float(data.get('balance', 0))
        if balance < 0:
            return jsonify({"status": "error", "message": "餘額不可為負數"}), 400

        conn = get_db_connection()
        now = datetime.now()
        conn.execute("""
            INSERT INTO bank_balance (id, balance, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT (id) DO UPDATE SET balance = EXCLUDED.balance, updated_at = ?
        """, [balance, now, now])
        conn.close()
        return jsonify({
            "status": "success",
            "balance": balance,
            "message": f"銀行餘額已更新為 ${balance:,.0f}",
            "updated_at": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  格式化 SpeedyAPI 庫存 + 資產總覽 + AI 策略
# ================================================================

@app.route('/api/speedy/positions_formatted', methods=['GET'])
def speedy_positions_formatted():
    """取得 Speedy 庫存並格式化（SpeedyAPI 即時價優先 + yfinance fallback）"""
    try:
        session = get_speedy_session()
        raw = session.query_positions()
        if raw.get('status') != 'success':
            return jsonify({"status": "error", "message": raw.get('message', '無法取得庫存')}), 500

        stksum = raw.get('parsed', [])
        # ── 解包 wrapper dict（_parse_result 會把整個 dict 包成 list） ──
        if len(stksum) == 1 and isinstance(stksum[0], dict) and 'stksumList' in stksum[0]:
            stksum = stksum[0]['stksumList']
        if not stksum:
            return jsonify({"status": "success", "holdings": [], "summary": {"total_cost": 0, "total_value": 0, "total_pnl": 0, "total_pnl_pct": 0}})

        holdings = []
        total_cost = 0.0
        total_value = 0.0

        for s in stksum:
            # ── 欄位對應 SpeedyAPI 實際名稱 ──
            symbol = (s.get('stkno') or s.get('stkidx') or s.get('stock', '')).strip()
            name = s.get('stkna') or s.get('stkname') or symbol  # SpeedyAPI 用 stkna
            cost_qty = int(float(s.get('costqty', 0)))
            avg_cost = float(s.get('priceavg') or s.get('avgcost') or 0)  # SpeedyAPI 用 priceavg
            cost_basis = cost_qty * avg_cost
            total_cost += cost_basis

            # ── 即時價格：SpeedyAPI 優先 ──
            price = None
            pricemkt = s.get('pricemkt') or s.get('pricenow')
            if pricemkt is not None and float(pricemkt) > 0:
                price = float(pricemkt)

            # ── 未實現損益：SpeedyAPI 優先 ──
            pnl = None
            makeasum = s.get('makeasum')
            if makeasum is not None:
                pnl = float(makeasum)

            # ── 市值：SpeedyAPI 優先 ──
            current_value = None
            valuemkt = s.get('valuemkt') or s.get('valuenow')
            if valuemkt is not None and float(valuemkt) > 0:
                current_value = float(valuemkt)

            # ── yfinance fallback（上市上櫃自動判斷後綴） ──
            if price is None and symbol:
                try:
                    stype = s.get('stype', 'H')  # H=上市, O=上櫃, R=興櫃
                    suffix = '.TWO' if stype in ('O', 'R') else '.TW'
                    tw_symbol = f"{symbol}{suffix}"
                    ticker = yf.Ticker(tw_symbol)
                    info = ticker.info
                    fast = ticker.fast_info
                    price = fast.get('last_price') or info.get('currentPrice') or info.get('regularMarketPreviousClose')
                except:
                    pass

            if current_value is None:
                current_value = cost_qty * price if price else cost_basis
            if pnl is None:
                pnl = current_value - cost_basis if price else 0

            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
            makeaper = s.get('makeaper')
            if makeaper is not None:
                pnl_pct = float(makeaper)

            total_value += current_value

            holdings.append({
                "symbol": symbol,
                "name": name,
                "shares": cost_qty,
                "avg_cost": round(avg_cost, 2),
                "price": round(price, 2) if price else None,
                "cost_basis": round(cost_basis, 2),
                "current_value": round(current_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2)
            })

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        return jsonify({
            "status": "success",
            "holdings": holdings,
            "summary": {
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2)
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/speedy/asset_summary', methods=['GET'])
def speedy_asset_summary():
    """總資產摘要：Speedy 庫存市值 + 銀行餘額"""
    try:
        session = get_speedy_session()
        raw = session.query_positions()
        stock_value = 0.0
        bank_balance = 0.0

        if raw.get('status') == 'success':
            stksum = raw.get('parsed', [])
            # ── 解包 wrapper dict ──
            if len(stksum) == 1 and isinstance(stksum[0], dict) and 'stksumList' in stksum[0]:
                stksum = stksum[0]['stksumList']
            for s in stksum:
                symbol = (s.get('stkno') or s.get('stkidx') or s.get('stock', '')).strip()
                cost_qty = int(float(s.get('costqty', 0)))
                avg_cost = float(s.get('priceavg') or s.get('avgcost') or 0)

                # ── 市值：SpeedyAPI 優先 ──
                valuemkt = s.get('valuemkt') or s.get('valuenow')
                if valuemkt is not None and float(valuemkt) > 0:
                    stock_value += float(valuemkt)
                    continue

                # ── 即時價：SpeedyAPI 優先 ──
                price = None
                pricemkt = s.get('pricemkt') or s.get('pricenow')
                if pricemkt is not None and float(pricemkt) > 0:
                    price = float(pricemkt)

                # ── yfinance fallback ──
                if price is None and symbol:
                    try:
                        stype = s.get('stype', 'H')
                        suffix = '.TWO' if stype in ('O', 'R') else '.TW'
                        tw_symbol = f"{symbol}{suffix}"
                        ticker = yf.Ticker(tw_symbol)
                        fast = ticker.fast_info
                        price = fast.get('last_price') or ticker.info.get('currentPrice')
                    except:
                        pass

                stock_value += cost_qty * (price if price else avg_cost)

        # 銀行餘額（從 DuckDB bank_balance 表）
        try:
            conn = get_db_connection()
            row = conn.execute("SELECT balance FROM bank_balance WHERE id = 1").fetchone()
            if row and row[0]:
                bank_balance = float(row[0])
            conn.close()
        except:
            pass

        total_assets = stock_value + bank_balance

        return jsonify({
            "status": "success",
            "stock_value": round(stock_value, 2),
            "bank_balance": round(bank_balance, 2),
            "total_assets": round(total_assets, 2),
            "stock_pct": round(stock_value / total_assets * 100, 1) if total_assets > 0 else 0,
            "bank_pct": round(bank_balance / total_assets * 100, 1) if total_assets > 0 else 0,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  合併持倉 API：個人券商庫存 + AI 紙上庫存 + 銀行餘額
# ================================================================

@app.route('/api/portfolio/holdings/all', methods=['GET'])
def portfolio_holdings_all():
    """合併全部持倉（Speedy 券商 + AI 紙上）與銀行餘額，產出總資產收益摘要"""
    try:
        holdings = []
        total_cost = 0.0
        total_value = 0.0

        # ── 個人券商庫存（SpeedyAPI）──
        try:
            session = get_speedy_session()
            raw = session.query_positions()
            if raw.get('status') == 'success':
                stksum = raw.get('parsed', [])
                if len(stksum) == 1 and isinstance(stksum[0], dict) and 'stksumList' in stksum[0]:
                    stksum = stksum[0]['stksumList']
                for s in stksum:
                    symbol = (s.get('stkno') or s.get('stkidx') or s.get('stock', '')).strip()
                    name = s.get('stkna') or s.get('stkname') or symbol
                    cost_qty = int(float(s.get('costqty', 0)))
                    avg_cost = float(s.get('priceavg') or s.get('avgcost') or 0)
                    cost_basis = cost_qty * avg_cost
                    total_cost += cost_basis

                    # 即時價與市值
                    price = None
                    pricemkt = s.get('pricemkt') or s.get('pricenow')
                    if pricemkt is not None and float(pricemkt) > 0:
                        price = float(pricemkt)
                    valuemkt = s.get('valuemkt') or s.get('valuenow')
                    if valuemkt is not None and float(valuemkt) > 0:
                        current_value = float(valuemkt)
                    else:
                        current_value = cost_qty * price if price else cost_basis
                    if price is None and symbol:
                        try:
                            stype = s.get('stype', 'H')
                            suffix = '.TWO' if stype in ('O', 'R') else '.TW'
                            ticker = yf.Ticker(f"{symbol}{suffix}")
                            fast = ticker.fast_info
                            price = fast.get('last_price') or ticker.info.get('currentPrice')
                            if price: current_value = cost_qty * price
                        except: pass

                    pnl = current_value - cost_basis if price else 0
                    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
                    makeaper = s.get('makeaper')
                    if makeaper is not None: pnl_pct = float(makeaper)
                    total_value += current_value
                    holdings.append({
                        "symbol": symbol, "name": name, "shares": cost_qty,
                        "avg_cost": round(avg_cost, 2), "price": round(price, 2) if price else None,
                        "cost_basis": round(cost_basis, 2), "current_value": round(current_value, 2),
                        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "source": "speedy"
                    })
        except Exception as e:
            pass  # Speedy 未連線，跳過

        # ── AI 紙上庫存 ──
        try:
            ai_positions = paper_engine.get_positions()
            for p in ai_positions:
                sym = p['symbol']
                # 避免與 Speedy 庫存重複
                if any(h['symbol'] == sym and h['source'] == 'speedy' for h in holdings):
                    continue
                shares = p['shares']
                avg_cost = p['avg_cost']
                cost_basis = shares * avg_cost
                total_cost += cost_basis
                price = p.get('price')
                current_value = p.get('current_value', cost_basis)
                if not current_value and price:
                    current_value = shares * price
                total_value += current_value
                pnl = current_value - cost_basis if price else 0
                pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
                holdings.append({
                    "symbol": sym, "name": p.get('name', sym), "shares": shares,
                    "avg_cost": round(avg_cost, 2), "price": round(price, 2) if price else None,
                    "cost_basis": round(cost_basis, 2), "current_value": round(current_value, 2),
                    "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "source": "ai_paper"
                })
        except Exception as e:
            pass

        # ── 銀行餘額 ──
        bank_balance = 0.0
        try:
            conn = get_db_connection()
            row = conn.execute("SELECT balance FROM bank_balance WHERE id = 1").fetchone()
            if row and row[0]: bank_balance = float(row[0])
            conn.close()
        except: pass

        total_assets = total_value + bank_balance
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        return jsonify({
            "status": "success",
            "holdings": holdings,
            "summary": {
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "bank_balance": round(bank_balance, 2),
                "total_assets": round(total_assets, 2),
                "speedy_count": sum(1 for h in holdings if h['source'] == 'speedy'),
                "ai_count": sum(1 for h in holdings if h['source'] == 'ai_paper'),
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================================================================
#  除錯端點：直接回傳 raw stksumList 以確認欄位名稱
# ================================================================

@app.route('/api/speedy/debug_positions', methods=['GET'])
def speedy_debug_positions():
    """除錯用：直接回傳 SpeedyAPI 原始 stksumList，確認實際欄位名稱"""
    try:
        session = get_speedy_session()
        raw = session.query_positions()
        if raw.get('status') != 'success':
            return jsonify({"status": "error", "message": raw.get('message', '無法取得庫存')}), 500

        stksum = raw.get('parsed', [])
        if len(stksum) == 1 and isinstance(stksum[0], dict) and 'stksumList' in stksum[0]:
            stksum = stksum[0]['stksumList']

        return jsonify({
            "status": "success",
            "count": len(stksum),
            "raw_stksumList": stksum
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/strategy/analyze', methods=['POST'])
def strategy_analyze():
    """AI 策略分析：根據預算、風險偏好、投資週期產出配置建議"""
    try:
        data = request.get_json() or {}
        budget = float(data.get('budget', 100000))
        risk = str(data.get('risk', 'moderate')).lower()  # conservative / moderate / aggressive
        horizon = str(data.get('horizon', 'medium')).lower()  # short / medium / long

        # 策略權重
        strategies = {
            'conservative': {'stock': 0.30, 'bond_etf': 0.40, 'cash': 0.30},
            'moderate':    {'stock': 0.55, 'bond_etf': 0.25, 'cash': 0.20},
            'aggressive':  {'stock': 0.80, 'bond_etf': 0.10, 'cash': 0.10}
        }
        horizons = {
            'short':  {'label': '短期 (1-3月)', 'suggestion': '高流動性標的，嚴格停損 ±5%'},
            'medium': {'label': '中期 (3-12月)', 'suggestion': '產業龍頭 + ETF 分批布局'},
            'long':   {'label': '長期 (1年+)', 'suggestion': '指數型 ETF + 優質個股定期定額'}
        }

        weights = strategies.get(risk, strategies['moderate'])
        horizon_info = horizons.get(horizon, horizons['medium'])

        allocation = {
            "stock_amount": round(budget * weights['stock'], 2),
            "bond_etf_amount": round(budget * weights['bond_etf'], 2),
            "cash_reserve": round(budget * weights['cash'], 2)
        }

        return jsonify({
            "status": "success",
            "budget": budget,
            "risk_profile": risk,
            "horizon": horizon_info['label'],
            "horizon_suggestion": horizon_info['suggestion'],
            "allocation": allocation,
            "disclaimer": "⚠️ 此為 AI 策略建議，非投資建議。實際操作請自行評估風險。",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
#  紙上交易 Paper Trading API
# ═══════════════════════════════════════════════════════════════

@app.route('/api/paper/account', methods=['GET'])
def paper_account():
    """紙上帳戶摘要"""
    try:
        acc = paper_engine.get_account()
        return jsonify({"status": "success", **acc})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/positions', methods=['GET'])
def paper_positions():
    """紙上持倉清單"""
    try:
        positions = paper_engine.get_positions()
        return jsonify({"status": "success", "positions": positions})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/orders', methods=['GET'])
def paper_orders():
    """紙上委託歷史"""
    try:
        limit = request.args.get('limit', 50, type=int)
        orders = paper_engine.get_orders(limit=limit)
        return jsonify({"status": "success", "orders": orders})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/trade', methods=['POST'])
def paper_trade():
    """手動紙上交易"""
    try:
        data = request.get_json() or {}
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'BUY')).upper()
        shares = int(data.get('shares', 0))
        price = float(data.get('price', 0))

        if not symbol or shares <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "參數不完整"}), 400
        if side not in ('BUY', 'SELL'):
            return jsonify({"status": "error", "message": "side 必須是 BUY 或 SELL"}), 400

        if side == 'BUY':
            result = paper_engine.buy(symbol, shares, price, strategy='manual')
        else:
            result = paper_engine.sell(symbol, shares, price, strategy='manual')
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/reset', methods=['POST'])
def paper_reset():
    """重置紙上帳戶"""
    try:
        data = request.get_json() or {}
        initial = float(data.get('initial_balance', 1000000))
        result = paper_engine.reset(initial)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/performance', methods=['GET'])
def paper_performance():
    """紙上交易績效指標"""
    try:
        perf = paper_engine.get_performance()
        return jsonify({"status": "success", "performance": perf})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ─── 策略管理 ───

@app.route('/api/paper/strategy/config', methods=['GET'])
def paper_strategy_config_get():
    """取得策略設定"""
    try:
        config = paper_engine.get_strategy_config()
        return jsonify({"status": "success", "config": config})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/strategy/config', methods=['POST'])
def paper_strategy_config_update():
    """更新策略設定"""
    try:
        data = request.get_json() or {}
        allowed = ["strategy_name", "interval_minutes", "max_position_pct",
                   "stop_loss_pct", "take_profit_pct", "symbols", "params"]
        kwargs = {k: v for k, v in data.items() if k in allowed}
        config = paper_engine.update_strategy_config(**kwargs)
        return jsonify({"status": "success", "config": config})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/strategy/start', methods=['POST'])
def paper_strategy_start():
    """啟動自主交易（若無標的，自動觸發 AI 研究）"""
    try:
        result = paper_trader_runner.start()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/strategy/stop', methods=['POST'])
def paper_strategy_stop():
    """停止自主交易"""
    try:
        result = paper_trader_runner.stop()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/strategy/status', methods=['GET'])
def paper_strategy_status():
    """自主交易狀態"""
    try:
        config = paper_engine.get_strategy_config()
        return jsonify({
            "status": "success",
            "is_running": paper_trader_runner.is_running(),
            "config": config,
            "last_tick": paper_trader_runner.last_tick,
            "tick_count": paper_trader_runner.tick_count,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/strategy/signals', methods=['GET'])
def paper_strategy_signals():
    """掃描所有追蹤標的，回傳當前信號"""
    try:
        config = paper_engine.get_strategy_config()
        symbols = [s.strip() for s in config.get('symbols', '').split(',') if s.strip()]
        if not symbols:
            return jsonify({"status": "success", "signals": [], "message": "未設定追蹤標的"})

        strategy_name = config.get('strategy_name', 'combined')
        signals = []
        for sym in symbols:
            try:
                r = analyze_symbol(sym, strategy_name)
                signals.append({"symbol": sym, **r})
            except Exception as e:
                signals.append({"symbol": sym, "signal": "ERROR", "reason": str(e)})

        return jsonify({"status": "success", "strategy": strategy_name, "signals": signals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/strategy/available', methods=['GET'])
def paper_strategy_available():
    """列出所有可用策略（含詳細說明）"""
    try:
        strategies = [
            {"id": "ma_crossover", "name": "MA 均線交叉", "short_desc": "5日/20日均線黃金交叉買入，死亡交叉賣出",
             "description": STRATEGY_INFO.get("ma_crossover", {}).get("description", ""),
             "parameters": STRATEGY_INFO.get("ma_crossover", {}).get("parameters", {}),
             "suitable_for": STRATEGY_INFO.get("ma_crossover", {}).get("suitable_for", "")},
            {"id": "rsi", "name": "RSI 動能", "short_desc": "RSI < 30 超賣買入，> 70 超買賣出",
             "description": STRATEGY_INFO.get("rsi", {}).get("description", ""),
             "parameters": STRATEGY_INFO.get("rsi", {}).get("parameters", {}),
             "suitable_for": STRATEGY_INFO.get("rsi", {}).get("suitable_for", "")},
            {"id": "macd", "name": "MACD 信號", "short_desc": "MACD/DIF 黃金交叉買入，死亡交叉賣出",
             "description": STRATEGY_INFO.get("macd", {}).get("description", ""),
             "parameters": STRATEGY_INFO.get("macd", {}).get("parameters", {}),
             "suitable_for": STRATEGY_INFO.get("macd", {}).get("suitable_for", "")},
            {"id": "bollinger", "name": "布林通道", "short_desc": "觸及下軌買入，觸及上軌賣出",
             "description": STRATEGY_INFO.get("bollinger", {}).get("description", ""),
             "parameters": STRATEGY_INFO.get("bollinger", {}).get("parameters", {}),
             "suitable_for": STRATEGY_INFO.get("bollinger", {}).get("suitable_for", "")},
            {"id": "combined", "name": "🤖 複合投票", "short_desc": "四指標多數決：3+ 指標同向才觸發",
             "description": STRATEGY_INFO.get("combined", {}).get("description", ""),
             "parameters": STRATEGY_INFO.get("combined", {}).get("parameters", {}),
             "suitable_for": STRATEGY_INFO.get("combined", {}).get("suitable_for", "")},
            {"id": "adaptive", "name": "🧠 自適應策略", "short_desc": "依大盤波動率自動調整參數的複合投票",
             "description": STRATEGY_INFO.get("adaptive", {}).get("description", ""),
             "parameters": STRATEGY_INFO.get("adaptive", {}).get("parameters", {}),
             "suitable_for": STRATEGY_INFO.get("adaptive", {}).get("suitable_for", "")},
        ]
        return jsonify({"status": "success", "strategies": strategies})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/strategy/detail/<name>', methods=['GET'])
def paper_strategy_detail(name):
    """取得特定策略的詳細說明"""
    try:
        strategy = get_strategy(name)
        detail = strategy.get_detail()
        return jsonify({"status": "success", "strategy": detail})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── 帳戶設定 ───

@app.route('/api/paper/account/update', methods=['POST'])
def paper_account_update():
    """更新紙上帳戶資金（保留持倉不變）"""
    try:
        data = request.get_json() or {}
        new_balance = data.get('balance')
        if new_balance is None:
            return jsonify({"status": "error", "message": "請提供 balance"}), 400
        new_balance = float(new_balance)
        if new_balance < 0:
            return jsonify({"status": "error", "message": "餘額不可為負"}), 400

        result = paper_engine.adjust_balance(new_balance)
        if result.get('status') != 'success':
            return jsonify(result), 500

        acc = paper_engine.get_account()
        return jsonify({
            "status": "success",
            "message": f"帳戶現金已更新：${result['old_balance']:,.0f} → ${new_balance:,.0f}",
            "balance": new_balance,
            "total_assets": acc.get('total_assets', new_balance),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



# ═══════════════════════════════════════════════════════════════
#  🤖 自主投資代理人 API (Autonomous Investment Agent)
# ═══════════════════════════════════════════════════════════════

_agent_log_store = []

@app.route('/api/paper/agent/research', methods=['POST'])
def agent_research():
    """觸發 AI 自主研究：題材發現 → 概念股篩選 → 技術分析 → 投資計畫"""
    try:
        data = request.get_json() or {}
        budget = float(data.get('budget', 1000000))
        strategy_name = str(data.get('strategy', 'combined'))
        user_topic = str(data.get('topic', '')).strip()  # 使用者指定的題材/主題

        agent = get_agent()

        # 注入 LLM provider 以啟用 Phase 1 辯論引擎 + Phase 2 LLM 動態映射
        if "call_llm" not in agent.providers:
            agent.providers["call_llm"] = _make_call_llm()

        # 若使用者指定了題材，注入為 extra_prompts 引導新聞搜尋方向
        extra_prompts = None
        if user_topic:
            extra_prompts = [
                f"2026 台股 {user_topic} 概念股 趨勢",
                f"2026 {user_topic} 產業 利多 供應鏈",
                f"{user_topic} 台灣 相關股票 熱門",
            ]

        p1 = agent.phase1_debate_discover_themes(
            force_debate=False,
            extra_prompts=extra_prompts,
        )

        # 若使用者指定了題材，強制注入 active_themes（保證 Phase 2 會映射）
        if user_topic:
            # 檢查是否已在已知題材中
            known = match_themes_from_text(user_topic)
            if known:
                for t in known:
                    if t not in agent.active_themes:
                        agent.active_themes.insert(0, t)
            elif user_topic not in agent.active_themes:
                # 未知新題材 → 加入，Phase 2 會用 LLM 動態映射
                agent.active_themes.insert(0, user_topic)
        p2 = agent.phase2_screen_candidates(
            fetch_stock_info_fn=_make_fetch_stock_info(),
            fetch_stock_price_fn=_make_fetch_stock_price(),
        )
        if p2.get("status") != "success":
            return jsonify({"status": "error", "phase": 2, "detail": p2}), 500

        p3 = agent.phase3_technical_review(
            analyze_fn=lambda sym, strat: analyze_symbol(sym, strat),
            strategy_name=strategy_name,
        )
        p4 = agent.phase4_generate_plan(budget=budget)

        _agent_log_store.append({
            "event": "research_complete",
            "themes": p1.get("themes", []),
            "candidates_count": p2.get("screened_count", 0),
            "timestamp": datetime.now().isoformat(),
        })

        return jsonify({"status": "success", "phase1": p1, "phase2": p2, "phase3": p3, "phase4": p4})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/paper/agent/plan', methods=['GET'])
def agent_plan():
    """取得當前投資計畫"""
    plan = get_agent().get_plan()
    if not plan:
        return jsonify({"status": "success", "plan": None, "message": "尚未產出投資計畫"})
    return jsonify({"status": "success", "plan": plan})


@app.route('/api/paper/agent/log', methods=['GET'])
def agent_log():
    """取得 AI 代理人日誌"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({"status": "success", "log": get_agent().get_log(limit=limit), "store_log": _agent_log_store[-20:]})


@app.route('/api/agent/debate/history', methods=['GET'])
def agent_debate_history():
    """取得 AI 辯論歷史記錄（四角色完整論述 + 裁決）"""
    try:
        agent = get_agent()
        limit = request.args.get('limit', 20, type=int)
        history = agent.get_debate_history(limit=limit)
        summaries = []
        for rec in history:
            summaries.append({
                "debate_id": rec.get("debate_id"),
                "timestamp": rec.get("timestamp"),
                "themes": rec.get("themes", []),
                "decision": rec.get("decision"),
                "confidence": rec.get("confidence"),
                "market_stage": rec.get("market_stage"),
                "summary": rec.get("summary", ""),
            })
        return jsonify({"status": "success", "history": summaries, "count": len(summaries)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/agent/debate/<int:debate_id>', methods=['GET'])
def agent_debate_detail(debate_id):
    """取得單筆辯論的完整逐字稿（四角色完整論述）"""
    try:
        agent = get_agent()
        # 遍歷全部歷史找尋固定 debate_id
        full_history = agent.get_debate_history(limit=100)
        rec = None
        for r in full_history:
            if r.get("debate_id") == debate_id:
                rec = r
                break
        if rec is None:
            return jsonify({"status": "error", "message": f"辯論記錄 #{debate_id} 不存在"}), 404
        return jsonify({
            "status": "success",
            "debate": {
                "debate_id": debate_id,
                "timestamp": rec.get("timestamp"),
                "themes": rec.get("themes", []),
                "decision": rec.get("decision"),
                "confidence": rec.get("confidence"),
                "market_stage": rec.get("market_stage"),
                "summary": rec.get("summary", ""),
                "bull_argument": rec.get("bull_argument", ""),
                "bear_argument": rec.get("bear_argument", ""),
                "analyst_argument": rec.get("analyst_argument", ""),
                "trader_decision": rec.get("trader_decision", {}),
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/paper/agent/execute', methods=['POST'])
def agent_execute():
    """執行投資計畫：載入標的並啟動自主交易"""
    plan = get_agent().get_plan()
    if not plan:
        return jsonify({"status": "error", "message": "請先執行研究"}), 400

    all_symbols = []
    for horizon in ["short_term", "mid_term", "long_term"]:
        for pick in plan.get(horizon, {}).get("picks", []):
            sym = pick.get("symbol", "")
            if sym and sym not in all_symbols:
                all_symbols.append(sym)

    if not all_symbols:
        return jsonify({"status": "error", "message": "計畫中無可用標的"}), 400

    symbols_str = ",".join(all_symbols)
    paper_engine.update_strategy_config(symbols=symbols_str)
    _agent_log_store.append({"event": "execute", "symbols": all_symbols, "timestamp": datetime.now().isoformat()})
    runner_result = paper_trader_runner.start()
    return jsonify({"status": "success", "message": f"已載入 {len(all_symbols)} 支: {symbols_str}", "symbols": all_symbols, "runner": runner_result})


@app.route('/api/paper/agent/themes', methods=['GET'])
def agent_themes():
    """取得所有題材 ↔ 概念股映射（含 DuckDB 動態快取）"""
    return jsonify({"status": "success", "themes": {k: v for k, v in sorted(_DYNAMIC_CONCEPT_MAP.items())}})


def _make_fetch_stock_info():
    def _fetch(symbol):
        result = {"symbol": symbol, "name": symbol}

        # ── 第一層：SpeedyAPI 行情資料（中文名稱 + 參考價，最快最準）──
        try:
            quote = get_quote_session()
            if quote.get_status().get("contracts_ready"):
                info = quote.get_stock_info(symbol)
                if info and info.get("name") and info["name"] != symbol:
                    result["name"] = info["name"]
                    if info.get("ref_price"):
                        result["price"] = info["ref_price"]
        except Exception:
            pass

        # ── 第二層：TWSE 公開資料（速度快）──
        tw = _fetch_twse_all_stocks().get(symbol, {})
        if not result.get("price"):
            result["price"] = tw.get("price")
        if not result.get("pe_ratio"):
            result["pe_ratio"] = tw.get("pe")
        if result.get("name") == symbol and tw.get("name"):
            result["name"] = tw.get("name")

        # ── 第三層：yfinance（補 market_cap / sector，最慢）──
        try:
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f"{symbol}{suffix}")
                    info = t.info
                    if not result.get("name") or result["name"] == symbol:
                        result["name"] = info.get("longName") or info.get("shortName", symbol)
                    result["market_cap"] = info.get("marketCap")
                    result["sector"] = info.get("sector") or info.get("industry", "")
                    if not result.get("pe_ratio"):
                        result["pe_ratio"] = info.get("trailingPE") or info.get("forwardPE")
                    break
                except Exception:
                    continue
        except Exception:
            pass

        if "name" not in result or not result["name"]:
            result["name"] = symbol
        return result
    return _fetch


def _make_fetch_stock_price():
    def _fetch(symbol):
        tw = _fetch_twse_all_stocks().get(symbol, {})
        price = tw.get("price")
        if price and price > 0:
            return float(price)
        try:
            return analyze_symbol(symbol, "ma_crossover").get("price")
        except:
            return None
    return _fetch


def _make_call_llm():
    """建立 call_llm provider，橋接到 DeepSeek API（autonomous_loop.LLMClient）。
    供 AutonomousInvestmentAgent 的 Phase 1 辯論引擎 + Phase 2 LLM 動態映射使用。
    """
    def _call(system_prompt: str, user_prompt: str, model: str = "flash") -> str:
        from autonomous_loop import LLMClient
        llm = LLMClient()
        use_pro = (model == "pro")
        return llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4 if use_pro else 0.7,
            max_tokens=2048 if use_pro else 1024,
            use_pro=use_pro,
        )
    return _call


# ─── 市場掃描 ───

_scanner_status = {"running": False, "last_result": None, "last_scan_time": None}

@app.route('/api/paper/scanner/run', methods=['POST'])
def paper_scanner_run():
    """觸發全市場掃描"""
    global _scanner_status
    try:
        data = request.get_json() or {}
        symbols_str = data.get('symbols', '').strip()
        symbols = [s.strip() for s in symbols_str.split(',') if s.strip()] if symbols_str else None
        top_n = int(data.get('top_n', 10))

        _scanner_status["running"] = True
        result = MarketScanner.scan(symbols=symbols, top_n=top_n)
        _scanner_status["running"] = False
        _scanner_status["last_result"] = result
        _scanner_status["last_scan_time"] = datetime.now().isoformat()

        return jsonify(result)
    except Exception as e:
        _scanner_status["running"] = False
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/paper/scanner/result', methods=['GET'])
def paper_scanner_result():
    """取得最近一次掃描結果"""
    global _scanner_status
    if _scanner_status["last_result"]:
        return jsonify({
            "status": "success",
            **(_scanner_status["last_result"] or {}),
            "scan_time": _scanner_status["last_scan_time"],
        })
    return jsonify({"status": "success", "top_picks": [], "message": "尚未執行掃描"})

@app.route('/api/paper/scanner/status', methods=['GET'])
def paper_scanner_status():
    """掃描狀態"""
    global _scanner_status
    return jsonify({
        "status": "success",
        "running": _scanner_status["running"],
        "last_scan_time": _scanner_status["last_scan_time"],
    })


# ═══════════════════════════════════════════════════════════════
#  自主交易執行器 (Background Thread)
# ═══════════════════════════════════════════════════════════════

class PaperTraderRunner:
    """紙上交易自主執行器 — 背景執行緒"""

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self.last_tick = None
        self.tick_count = 0

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> dict:
        if self.is_running():
            return {"status": "error", "message": "自主交易已在運行中"}
        config = paper_engine.get_strategy_config()

        # 若無追蹤標的，自動觸發 AI 研究
        if not config.get('symbols', '').strip():
            try:
                agent = get_agent()
                agent.phase1_discover_themes()
                agent.phase2_screen_candidates(
                    fetch_stock_info_fn=_make_fetch_stock_info(),
                    fetch_stock_price_fn=_make_fetch_stock_price(),
                )
                agent.phase3_technical_review(
                    analyze_fn=lambda sym, strat: analyze_symbol(sym, strat),
                    strategy_name=config.get('strategy_name', 'combined'),
                )
                agent.phase4_generate_plan(budget=1000000)
                plan = agent.get_plan()
                if plan:
                    all_syms = []
                    for h in ["short_term", "mid_term", "long_term"]:
                        for p in plan.get(h, {}).get("picks", []):
                            s = p.get("symbol", "")
                            if s and s not in all_syms:
                                all_syms.append(s)
                    if all_syms:
                        paper_engine.update_strategy_config(symbols=",".join(all_syms))
                        config = paper_engine.get_strategy_config()
            except Exception as e:
                log.warning(f"自動研究失敗: {e}")

        if not config.get('symbols', '').strip():
            return {"status": "error", "message": "無法自動發現標的，請手動設定追蹤股票代號"}

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        paper_engine.update_strategy_config(is_running=True)
        return {"status": "success", "message": f"🚀 自主交易已啟動！策略：{config['strategy_name']}，標的：{config['symbols']}"}

    def stop(self) -> dict:
        if not self.is_running():
            return {"status": "error", "message": "自主交易未在運行"}
        self._stop_event.set()
        paper_engine.update_strategy_config(is_running=False)
        return {"status": "success", "message": "⏹️ 自主交易已停止"}

    def _run(self):
        config = paper_engine.get_strategy_config()
        interval = max(5, config.get('interval_minutes', 15))
        log.info(f"📊 自主交易執行器啟動，間隔 {interval} 分鐘")

        while not self._stop_event.is_set():
            try:
                self._tick()
                self.tick_count += 1
                self.last_tick = datetime.now().isoformat()
            except Exception as e:
                log.error(f"自主交易 tick 錯誤: {e}")

            # 每 30 秒檢查一次停止信號
            for _ in range(interval * 2):
                if self._stop_event.is_set():
                    break
                time.sleep(30)

    def _tick(self):
        config = paper_engine.get_strategy_config()
        symbols = [s.strip() for s in config.get('symbols', '').split(',') if s.strip()]
        if not symbols:
            return

        strategy = get_strategy(config['strategy_name'])
        account = paper_engine.get_account()
        positions = {p['symbol']: p for p in paper_engine.get_positions()}
        strategy_name = config['strategy_name']

        for symbol in symbols:
            try:
                result = strategy.analyze(symbol)
                price = result.get('price')
                if not price or price <= 0:
                    continue

                # ── 檢查現有持倉：停損 / 停利 / 賣出信號 ──
                if symbol in positions:
                    pos = positions[symbol]
                    pnl_pct = (price - pos['avg_cost']) / pos['avg_cost'] if pos['avg_cost'] > 0 else 0

                    sell_reason = None
                    if pnl_pct <= -config['stop_loss_pct']:
                        sell_reason = f"🛑 停損 ({pnl_pct*100:+.1f}%)"
                    elif pnl_pct >= config['take_profit_pct']:
                        sell_reason = f"🎯 停利 ({pnl_pct*100:+.1f}%)"
                    elif result['signal'] == 'SELL' and result['confidence'] >= 50:
                        sell_reason = result['reason']

                    if sell_reason:
                        paper_engine.sell(symbol, pos['shares'], price,
                                         strategy=strategy_name, note=sell_reason)
                        log.info(f"📉 賣出 {symbol} @ ${price:.2f} — {sell_reason}")

                # ── 檢查新買入信號 ──
                elif result['signal'] == 'BUY' and result['confidence'] >= 50:
                    # 計算部位上限
                    max_pos_value = account['total_assets'] * config['max_position_pct']
                    shares_to_buy = int(max_pos_value / price / 100) * 100  # 整張
                    if shares_to_buy < 100:
                        shares_to_buy = int(max_pos_value / price)  # 零股

                    if shares_to_buy > 0:
                        est_cost = shares_to_buy * price * 1.002  # 預估含手續費
                        if est_cost <= account['balance']:
                            paper_engine.buy(symbol, shares_to_buy, price,
                                           strategy=strategy_name)
                            log.info(f"📈 買入 {symbol} {shares_to_buy}股 @ ${price:.2f} — {result['reason']}")

            except Exception as e:
                log.warning(f"分析 {symbol} 失敗: {e}")
                continue


paper_trader_runner = PaperTraderRunner()


# ═══════════════════════════════════════════════════════════════
#  📋 Mission 任務管理 API
# ═══════════════════════════════════════════════════════════════

@app.route('/api/mission/list', methods=['GET'])
def mission_list():
    """列出所有 Mission"""
    try:
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT id, description, risk_level, timeframe_days, target_return_pct,
                   status, start_balance, current_balance, start_date, deadline, created_at
            FROM paper_missions ORDER BY created_at DESC LIMIT 50
        """).fetchall()
        conn.close()
        missions = []
        for r in rows:
            missions.append({
                "id": r[0], "description": r[1], "risk_level": r[2],
                "timeframe_days": r[3], "target_return_pct": float(r[4]),
                "status": r[5], "start_balance": float(r[6]),
                "current_balance": float(r[7]), "start_date": str(r[8]),
                "deadline": str(r[9]), "created_at": str(r[10])
            })
        return jsonify({"status": "success", "missions": missions})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mission/create', methods=['POST'])
def mission_create():
    """從自然語言建立新 Mission"""
    try:
        data = request.get_json() or {}
        text = str(data.get('text', '')).strip()
        budget = data.get('budget')  # 前端指定的投資金額（選填）

        if not text:
            return jsonify({"status": "error", "message": "請輸入任務描述"}), 400

        from mission_parser import MissionParser
        params = MissionParser.parse(text)

        # 若前端提供了明確的投資金額，調整紙上帳戶資金
        if budget is not None:
            budget_val = float(budget)
            if budget_val >= 1000:
                paper_engine.adjust_balance(budget_val)
            else:
                return jsonify({"status": "error", "message": "投資金額至少 1,000 TWD"}), 400

        result = paper_engine.create_mission(
            description=text,
            risk_level=params.risk_level,
            timeframe_days=params.timeframe_days,
            target_return_pct=params.target_return_pct,
            max_positions=params.max_positions,
            max_position_pct=params.max_position_pct,
            stop_loss_pct=params.stop_loss_pct,
            take_profit_pct=params.take_profit_pct,
            allow_margin=params.allow_margin,
            preferred_market=params.preferred_market,
            scan_frequency=params.scan_frequency,
        )

        result["parsed_params"] = {
            "risk_level": params.risk_level,
            "timeframe_days": params.timeframe_days,
            "target_return_pct": params.target_return_pct,
            "max_positions": params.max_positions,
            "stop_loss_pct": round(params.stop_loss_pct * 100, 1),
            "take_profit_pct": round(params.take_profit_pct * 100, 1),
            "preferred_market": params.preferred_market,
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mission/<int:mission_id>', methods=['GET'])
def mission_detail(mission_id):
    """取得單一 Mission 詳情含進度"""
    try:
        result = paper_engine.get_mission_progress(mission_id)
        if result.get("status") != "success":
            return jsonify(result), 404

        eval_result = mission_tracker.evaluate(mission_id)
        mission = result["mission"]
        mission["evaluation"] = eval_result.get("evaluation", {}) if eval_result.get("status") == "success" else {}
        return jsonify({"status": "success", "mission": mission})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mission/<int:mission_id>/execute', methods=['POST'])
def mission_execute(mission_id):
    """手動觸發一次 Mission 決策循環"""
    try:
        data = request.get_json() or {}
        mode = str(data.get('mode', 'paper'))

        from mission_executor import get_executor
        executor = get_executor()
        result = executor.execute_cycle(mission_id=mission_id, mode=mode)

        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mission/<int:mission_id>/progress', methods=['GET'])
def mission_progress(mission_id):
    """取得 Mission 進度評估"""
    try:
        result = mission_tracker.evaluate(mission_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mission/<int:mission_id>/complete', methods=['POST'])
def mission_complete(mission_id):
    """標記 Mission 為完成"""
    try:
        conn = get_db_connection()
        conn.execute(
            "UPDATE paper_missions SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=?",
            [mission_id]
        )
        conn.close()
        return jsonify({"status": "success", "message": f"Mission #{mission_id} 已標記為完成"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
#  🤖 24/7 AI 自主投資循環 API
# ═══════════════════════════════════════════════════════════════

@app.route('/api/paper/autonomous/start', methods=['POST'])
def autonomous_start():
    """啟動 24/7 AI 自主投資循環"""
    try:
        data = request.get_json() or {}
        interval = int(data.get('interval_minutes', 60))
        loop = get_autonomous_loop()
        result = loop.start(interval_minutes=interval)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/paper/autonomous/stop', methods=['POST'])
def autonomous_stop():
    """停止 AI 自主投資循環"""
    try:
        loop = get_autonomous_loop()
        result = loop.stop()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/paper/autonomous/status', methods=['GET'])
def autonomous_status():
    """查詢 AI 自主投資循環狀態"""
    try:
        loop = get_autonomous_loop()
        status = loop.get_status()
        return jsonify({"status": "success", **status})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/paper/autonomous/alerts', methods=['GET'])
def autonomous_alerts():
    """取得最近的 AI 調整建議警報"""
    try:
        loop = get_autonomous_loop()
        limit = request.args.get('limit', 20, type=int)
        alerts = loop.alerts[-limit:] if loop.alerts else []
        return jsonify({"status": "success", "alerts": alerts, "count": len(alerts)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
#  💬 AI 策略討論 Chat API
# ═══════════════════════════════════════════════════════════════

@app.route('/api/paper/chat', methods=['POST'])
def paper_chat():
    """AI 策略討論對話"""
    try:
        data = request.get_json() or {}
        message = str(data.get('message', '')).strip()
        if not message:
            return jsonify({"status": "error", "message": "請提供對話內容"}), 400

        loop = get_autonomous_loop()
        response = loop.chat(message)
        return jsonify({"status": "success", "response": response})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/paper/chat/history', methods=['GET'])
def paper_chat_history():
    """取得對話歷史"""
    try:
        loop = get_autonomous_loop()
        limit = request.args.get('limit', 20, type=int)
        history = loop.chat_history[-limit:] if loop.chat_history else []
        return jsonify({"status": "success", "history": history, "count": len(history)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/paper/chat/clear', methods=['POST'])
def paper_chat_clear():
    """清除對話歷史"""
    try:
        loop = get_autonomous_loop()
        result = loop.clear_chat_history()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
#  🤖 AI 交易工具層 API (AITradingToolkit)
# ═══════════════════════════════════════════════════════════════

@app.route('/api/ai/toolkit/account', methods=['GET'])
def ai_toolkit_account():
    """AI 查詢帳戶（支援 mode=paper|live 參數）"""
    try:
        from ai_trading_toolkit import get_toolkit
        mode = request.args.get('mode', 'paper')
        toolkit = get_toolkit(default_mode=mode)
        result = toolkit.get_account()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ai/toolkit/positions', methods=['GET'])
def ai_toolkit_positions():
    """AI 查詢庫存（支援 mode=paper|live 參數）"""
    try:
        from ai_trading_toolkit import get_toolkit
        mode = request.args.get('mode', 'paper')
        toolkit = get_toolkit(default_mode=mode)
        result = toolkit.get_positions()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ai/toolkit/orders', methods=['GET'])
def ai_toolkit_orders():
    """AI 查詢委託（支援 mode=paper|live 參數）"""
    try:
        from ai_trading_toolkit import get_toolkit
        mode = request.args.get('mode', 'paper')
        toolkit = get_toolkit(default_mode=mode)
        result = toolkit.get_orders()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ai/toolkit/order', methods=['POST'])
def ai_toolkit_place_order():
    """AI 下單（支援 mode=paper|live 參數）"""
    try:
        from ai_trading_toolkit import get_toolkit
        data = request.get_json() or {}
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'BUY')).upper()
        price = float(data.get('price', 0))
        quantity = int(data.get('quantity', 0))
        mode = str(data.get('mode', 'paper'))
        market = str(data.get('market', 'tse')).lower()

        if not symbol or quantity <= 0 or price <= 0:
            return jsonify({"status": "error", "message": "參數不完整（symbol, price, quantity）"}), 400
        if side not in ('BUY', 'SELL'):
            return jsonify({"status": "error", "message": "side 必須是 BUY 或 SELL"}), 400

        toolkit = get_toolkit(default_mode=mode)
        risk = toolkit.check_risk(symbol, side, quantity, price, mode)
        if risk.get("status") == "blocked":
            return jsonify({
                "status": "blocked",
                "message": "風險檢查未通過",
                "issues": risk["issues"],
            }), 400

        result = toolkit.place_order(symbol, side, price, quantity, mode, market)
        return jsonify({
            "status": "success" if result.success else "error",
            "action": result.action,
            "mode": result.mode,
            "symbol": result.symbol,
            "quantity": result.quantity,
            "price": result.price,
            "order_id": result.order_id,
            "message": result.message,
            "warnings": risk.get("warnings", []),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ai/toolkit/cancel', methods=['POST'])
def ai_toolkit_cancel_order():
    """AI 刪單（支援 mode=paper|live 參數）"""
    try:
        from ai_trading_toolkit import get_toolkit
        data = request.get_json() or {}
        order_id = str(data.get('order_id', '')).strip()
        symbol = str(data.get('symbol', '')).strip().upper()
        side = str(data.get('side', 'B')).upper()
        mode = str(data.get('mode', 'paper'))

        if not order_id:
            return jsonify({"status": "error", "message": "請提供 order_id"}), 400

        toolkit = get_toolkit(default_mode=mode)
        result = toolkit.cancel_order(order_id, symbol, side, mode)
        return jsonify({
            "status": "success" if result.success else "error",
            "mode": result.mode,
            "order_id": result.order_id,
            "message": result.message,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ai/toolkit/price/<symbol>', methods=['GET'])
def ai_toolkit_stock_price(symbol):
    """AI 查詢即時報價"""
    try:
        from ai_trading_toolkit import get_toolkit
        toolkit = get_toolkit()
        result = toolkit.get_stock_price(symbol.upper())
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ai/toolkit/mode', methods=['GET'])
def ai_toolkit_get_mode():
    """查詢目前 AI 交易模式"""
    try:
        from ai_trading_toolkit import get_toolkit
        toolkit = get_toolkit()
        return jsonify({
            "status": "success",
            "mode": toolkit.get_mode(),
            "available_modes": ["paper", "live"],
            "live_max_order": toolkit.max_order_value_live,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ai/toolkit/mode', methods=['POST'])
def ai_toolkit_set_mode():
    """切換 AI 交易模式（paper / live）"""
    try:
        from ai_trading_toolkit import get_toolkit
        data = request.get_json() or {}
        mode = str(data.get('mode', 'paper')).lower()

        if mode not in ('paper', 'live'):
            return jsonify({"status": "error", "message": "模式只能為 paper 或 live"}), 400

        toolkit = get_toolkit()
        toolkit.set_mode(mode)
        return jsonify({
            "status": "success",
            "message": f"AI 交易模式已切換為 {mode}",
            "mode": mode,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
#  📰 新聞摘要 API
# ═══════════════════════════════════════════════════════════════

@app.route('/api/paper/news', methods=['GET'])
def paper_news():
    """取得最新財經新聞摘要"""
    try:
        loop = get_autonomous_loop()
        articles = loop.news.get_recent(hours=6)
        return jsonify({
            "status": "success",
            "articles": articles,
            "count": len(articles),
            "last_fetch": loop.news.last_fetch.isoformat() if loop.news.last_fetch else None,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/paper/news/refresh', methods=['POST'])
def paper_news_refresh():
    """手動刷新新聞"""
    try:
        loop = get_autonomous_loop()
        articles = loop.news.fetch_news()
        return jsonify({
            "status": "success",
            "articles": articles,
            "count": len(articles),
            "last_fetch": loop.news.last_fetch.isoformat() if loop.news.last_fetch else None,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def _auto_connect_speedy_quote():
    """啟動時自動連接 SpeedyAPI 行情（從 .env 讀取 MEGA_ID / MEGA_PASSWORD）"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        user_id = os.getenv("MEGA_ID", "").strip()
        password = os.getenv("MEGA_PASSWORD", "").strip()
        if not user_id or not password:
            print("[SpeedyQuote] .env 未設定 MEGA_ID/MEGA_PASSWORD，跳過行情自動連線")
            return
        print(f"[SpeedyQuote] 🔗 自動連線行情主機...")
        session = get_quote_session()
        result = session.connect_and_download(user_id, password, timeout=35)
        print(f"[SpeedyQuote] 結果: {result.get('message', result)}")
        if result.get('status') == 'success':
            print(f"[SpeedyQuote] ✅ 已下載 {result.get('stock_count', 0)} 檔股票基本資料（含中文名稱）")
    except Exception as e:
        print(f"[SpeedyQuote] ⚠️ 自動連線失敗: {e}")


def start_ui_server(port=5000):
    """
    在背景啟動 Flask Server
    """
    _init_investment_db()
    # ── 背景自動連接 SpeedyAPI 行情（非阻塞）──
    threading.Thread(target=_auto_connect_speedy_quote, daemon=True).start()
    print(f"✨ Alice 控制面板已啟動！請在瀏覽器開啟: http://127.0.0.1:{port}")
    try:
        import webbrowser
        # 自動打開瀏覽器
        # webbrowser.open(f"http://127.0.0.1:{port}")
    except:
        pass
    
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_server_in_background():
    # 使用 Thread 將 Flask 跑在背景，以免卡住 Telegram Polling
    server_thread = threading.Thread(target=start_ui_server, daemon=True)
    server_thread.start()
    return server_thread

if __name__ == '__main__':
    start_ui_server(port=5002)
