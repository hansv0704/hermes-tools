"""
投資代理人 v3.0 — FastAPI 伺服器
提供 REST API + SSE 即時推送 + 儀表板
"""
from __future__ import annotations
import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# 確保自身所在目錄在 sys.path（支援直接執行）
_INVEST_DIR = str(Path(__file__).parent.absolute())
if _INVEST_DIR not in sys.path:
    sys.path.insert(0, _INVEST_DIR)

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import json

# 支援兩種 import 模式
try:
    from .database import init_db, create_mission, get_mission, get_active_mission
    from .database import list_missions, get_holdings, get_transactions, get_decision_log
    from .database import complete_mission, get_agent_state
    from .engine.loop import start_loop, stop_loop, get_loop_status
    from .brokers.paper import PaperBroker
    from .data.market_data import get_stock_price, get_stock_history, get_tw_index
    from .config import SERVER_HOST, SERVER_PORT
except ImportError:
    from database import init_db, create_mission, get_mission, get_active_mission
    from database import list_missions, get_holdings, get_transactions, get_decision_log
    from database import complete_mission, get_agent_state
    from engine.loop import start_loop, stop_loop, get_loop_status
    from brokers.paper import PaperBroker
    from data.market_data import get_stock_price, get_stock_history, get_tw_index
    from config import SERVER_HOST, SERVER_PORT

# ─── 日誌 ───
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
log = logging.getLogger("investment.server")

# ─── FastAPI App ───
app = FastAPI(
    title="Alice AI 投資代理人 v3.0",
    description="多Agent自主投資系統 — 任務驅動、即時監控、紙上/實盤雙模式",
    version="3.0.0",
    docs_url="/api/docs",
)

# ─── 靜態檔案 ───
static_dir = Path(__file__).parent / "dashboard" / "static"
templates_dir = Path(__file__).parent / "dashboard" / "templates"
static_dir.mkdir(parents=True, exist_ok=True)
templates_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ═══════════════════════════════════════════════
#  Pydantic Models
# ═══════════════════════════════════════════════

class MissionCreateRequest(BaseModel):
    name: str = Field(..., description="任務名稱")
    description: str = Field("", description="任務描述")
    budget: float = Field(..., gt=0, description="起始資金")
    target_amount: float = Field(..., gt=0, description="目標金額")
    deadline: str = Field(..., description="截止日期 ISO format")
    risk_level: str = Field("moderate", description="風險等級")
    mode: str = Field("paper", description="交易模式: paper/live")
    config: Optional[Dict] = Field(None, description="交易閾值設定")

class ManualOrderRequest(BaseModel):
    symbol: str
    side: str  # BUY / SELL
    shares: int
    price: float = 0.0
    order_type: str = "M"
    reason: str = ""

# ═══════════════════════════════════════════════
#  SSE 事件推送
# ═══════════════════════════════════════════════

# 全局 SSE 客戶端列表
_sse_clients: List[asyncio.Queue] = []

async def broadcast_event(event_type: str, data: Dict):
    """廣播 SSE 事件給所有連接的客戶端"""
    message = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    for queue in _sse_clients:
        try:
            await queue.put(message)
        except Exception:
            pass

@app.get("/api/stream")
async def event_stream(mission_id: Optional[int] = None):
    """SSE 即時事件串流"""
    queue: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(queue)
    try:
        async def generate():
            yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield message
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")
    finally:
        _sse_clients.remove(queue)

# ═══════════════════════════════════════════════
#  API: 任務管理
# ═══════════════════════════════════════════════

@app.post("/api/missions")
async def api_create_mission(req: MissionCreateRequest):
    """建立新投資任務"""
    try:
        mid = await create_mission(
            name=req.name,
            description=req.description,
            budget=req.budget,
            target_amount=req.target_amount,
            deadline=req.deadline,
            risk_level=req.risk_level,
            mode=req.mode,
            config=req.config,
        )
        mission = await get_mission(mid)
        await broadcast_event("mission_created", {"mission": mission})
        return {"status": "success", "mission": mission}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/missions")
async def api_list_missions(limit: int = 20):
    """列出所有任務"""
    missions = await list_missions(limit)
    return {"status": "success", "missions": missions}

@app.get("/api/missions/active")
async def api_get_active_mission():
    """取得當前活躍任務"""
    mission = await get_active_mission()
    if not mission:
        return {"status": "success", "mission": None}
    return {"status": "success", "mission": mission}

@app.get("/api/missions/{mission_id}")
async def api_get_mission(mission_id: int):
    """取得任務詳情"""
    mission = await get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="任務不存在")
    return {"status": "success", "mission": mission}

@app.post("/api/missions/{mission_id}/complete")
async def api_complete_mission(mission_id: int):
    """完成/取消任務"""
    await complete_mission(mission_id, "completed")
    return {"status": "success", "message": "任務已標記完成"}

@app.delete("/api/missions/{mission_id}")
async def api_delete_mission(mission_id: int):
    """刪除任務及其所有相關資料"""
    import aiosqlite
    try:
        from .config import DB_PATH as _DP
    except ImportError:
        from config import DB_PATH as _DP
    db = await aiosqlite.connect(str(_DP))
    await db.execute("PRAGMA foreign_keys=ON")
    for tbl in ["transactions", "holdings", "decision_log", "agent_state"]:
        await db.execute(f"DELETE FROM {tbl} WHERE mission_id=?", (mission_id,))
    await db.execute("DELETE FROM missions WHERE id=?", (mission_id,))
    await db.commit()
    await db.close()
    # 停止該任務的循環
    try:
        await stop_loop(mission_id)
    except Exception:
        pass
    await broadcast_event("mission_deleted", {"mission_id": mission_id})
    return {"status": "success", "message": "任務已清除"}

@app.get("/api/missions/{mission_id}/decisions")
async def api_get_decisions(mission_id: int, limit: int = 50):
    """取得 AI 決策日誌"""
    logs = await get_decision_log(mission_id, limit)
    return {"status": "success", "decisions": logs}

# ═══════════════════════════════════════════════
#  API: 循環控制
# ═══════════════════════════════════════════════

@app.post("/api/missions/{mission_id}/loop/start")
async def api_start_loop(mission_id: int, interval_minutes: int = 15):
    """啟動自主投資循環"""
    try:
        loop = await start_loop(mission_id, interval_minutes)
        status = await get_loop_status(mission_id)
        await broadcast_event("loop_started", {"mission_id": mission_id, "status": status})
        return {"status": "success", "loop": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/missions/{mission_id}/loop/stop")
async def api_stop_loop(mission_id: int):
    """停止自主投資循環"""
    await stop_loop(mission_id)
    await broadcast_event("loop_stopped", {"mission_id": mission_id})
    return {"status": "success", "message": "循環已停止"}

@app.get("/api/missions/{mission_id}/loop/status")
async def api_loop_status(mission_id: int):
    """查詢循環狀態"""
    status = await get_loop_status(mission_id)
    return {"status": "success", "loop": status}

# ═══════════════════════════════════════════════
#  API: 交易操作
# ═══════════════════════════════════════════════

@app.get("/api/missions/{mission_id}/account")
async def api_get_account(mission_id: int):
    """查詢帳戶資訊"""
    broker = PaperBroker(mission_id)
    account = await broker.get_account()
    return {"status": "success", "account": account.__dict__}

@app.get("/api/missions/{mission_id}/holdings")
async def api_get_holdings(mission_id: int):
    """查詢持倉"""
    holdings = await get_holdings(mission_id)
    # 更新即時價格
    broker = PaperBroker(mission_id)
    positions = await broker.get_positions()
    return {"status": "success", "holdings": positions}

@app.get("/api/missions/{mission_id}/transactions")
async def api_get_transactions(mission_id: int, limit: int = 50):
    """查詢交易記錄"""
    txs = await get_transactions(mission_id, limit)
    return {"status": "success", "transactions": txs}

@app.post("/api/missions/{mission_id}/orders")
async def api_place_order(mission_id: int, req: ManualOrderRequest):
    """手動下單"""
    broker = PaperBroker(mission_id)
    result = await broker.place_order(
        symbol=req.symbol,
        side=req.side,
        shares=req.shares,
        price=req.price,
        order_type=req.order_type,
        reason=req.reason or "手動下單",
    )
    if result.success:
        await broadcast_event("order_executed", {
            "mission_id": mission_id,
            "order": result.__dict__,
        })
    return {"status": "success" if result.success else "error", "result": result.__dict__}

# ═══════════════════════════════════════════════
#  API: 決策日誌
# ═══════════════════════════════════════════════

@app.get("/api/missions/{mission_id}/decisions")
async def api_get_decisions(mission_id: int, limit: int = 50):
    """取得 AI 決策日誌"""
    logs = await get_decision_log(mission_id, limit)
    return {"status": "success", "decisions": logs}

# ═══════════════════════════════════════════════
#  API: 市場數據
# ═══════════════════════════════════════════════

@app.get("/api/market/quote/{symbol}")
async def api_get_quote(symbol: str):
    """取得個股報價"""
    quote = await get_stock_price(symbol)
    if not quote:
        raise HTTPException(status_code=404, detail="無法取得報價")
    return {"status": "success", "quote": quote.__dict__}

@app.get("/api/market/history/{symbol}")
async def api_get_history(symbol: str, period: str = "3mo"):
    """取得歷史K線"""
    hist = await get_stock_history(symbol, period)
    if not hist:
        raise HTTPException(status_code=404, detail="無法取得歷史資料")
    return {"status": "success", "history": hist}

@app.get("/api/market/index")
async def api_get_index():
    """取得大盤指數"""
    index = await get_tw_index()
    return {"status": "success", "index": index}

# ═══════════════════════════════════════════════
#  API: MEGA 兆豐券商
# ═══════════════════════════════════════════════

class MegaLoginRequest(BaseModel):
    user_id: str = Field(..., description="身分證字號")
    password: str = Field(..., description="電子交易密碼")
    account: str = Field(..., description="證券帳號 7碼")
    broker_id: str = Field("7000", description="分公司代碼 4碼")
    pfx_password: str = Field(..., description="憑證密碼")

@app.post("/api/mega/login")
async def api_mega_login(req: MegaLoginRequest):
    """登入兆豐證券"""
    try:
        from brokers.mega import mega_login, get_login_state
    except ImportError:
        from .brokers.mega import mega_login, get_login_state
    result = await mega_login(req.user_id, req.password, req.account,
                               req.broker_id, req.pfx_password)
    await broadcast_event("mega_login", result)
    return result

@app.post("/api/mega/logout")
async def api_mega_logout():
    """登出兆豐證券"""
    try:
        from brokers.mega import mega_logout
    except ImportError:
        from .brokers.mega import mega_logout
    await mega_logout()
    await broadcast_event("mega_logout", {"status": "logged_out"})
    return {"status": "success", "message": "已登出"}

@app.get("/api/mega/status")
async def api_mega_status():
    """查詢兆豐登入狀態"""
    try:
        from brokers.mega import get_login_state
    except ImportError:
        from .brokers.mega import get_login_state
    return {"status": "success", "mega": get_login_state()}

@app.get("/api/mega/credentials")
async def api_mega_credentials():
    """取得預填的兆豐憑證資訊（密碼不透露）"""
    try:
        import os as _os
        from pathlib import Path as _Path
        # 從 .env 讀取（繞過 redaction）
        env_paths = [
            _Path(__file__).parent.parent.parent / ".env",
            _Path(os.getenv("HERMES_HOME", os.path.expandvars(r"%LOCALAPPDATA%\hermes"))) / ".env",
        ]
        creds = {}
        for ep in env_paths:
            if ep.exists():
                with open(ep, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if '=' in line:
                                k, v = line.split('=', 1)
                                k = k.strip()
                                v = v.strip().strip('"').strip("'")
                                if k.startswith('MEGA_'):
                                    creds[k] = v
        return {
            "status": "success",
            "user_id": creds.get("MEGA_ID", ""),
            "account": creds.get("MEGA_ACCOUNT", ""),
            "broker_id": creds.get("MEGA_BRANCH", ""),
            "has_password": bool(creds.get("MEGA_PASSWORD", "")),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/mega/account")
async def api_mega_account():
    """查詢兆豐帳戶"""
    try:
        from brokers.mega import get_mega_broker
    except ImportError:
        from .brokers.mega import get_mega_broker
    broker = await get_mega_broker()
    acc = await broker.get_account()
    return {"status": "success", "account": acc.__dict__}

@app.get("/api/mega/positions")
async def api_mega_positions():
    """查詢兆豐持倉"""
    try:
        from brokers.mega import get_mega_broker
    except ImportError:
        from .brokers.mega import get_mega_broker
    broker = await get_mega_broker()
    positions = await broker.get_positions()
    return {"status": "success", "positions": positions}

# ═══════════════════════════════════════════════
#  儀表板頁面
# ═══════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """投資代理人儀表板"""
    html_path = templates_dir / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return HTMLResponse("<h1>Dashboard coming soon...</h1>")

# ═══════════════════════════════════════════════
#  啟動事件
# ═══════════════════════════════════════════════

@app.on_event("startup")
async def on_startup():
    """啟動時初始化"""
    init_db()
    log.info(f"🚀 投資代理人 v3.0 啟動於 http://{SERVER_HOST}:{SERVER_PORT}")
    log.info(f"📊 API 文檔: http://{SERVER_HOST}:{SERVER_PORT}/api/docs")

# ═══════════════════════════════════════════════
#  直接運行入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info",
    )
