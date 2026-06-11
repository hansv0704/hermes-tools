"""
Heartbeat 通知系統 v1.0
AI-Trader 風格的即時輪詢監控：GIS 異常 / 股票警報 / 系統健康
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


# --- 配置 ---
@dataclass
class HeartbeatConfig:
    """Heartbeat 監控配置"""
    interval_seconds: int = 300
    gis_enabled: bool = True
    stock_enabled: bool = False
    system_enabled: bool = True
    stock_watchlist: Dict[str, float] = field(default_factory=dict)
    telegram_chat_id: Optional[str] = None


# --- 全域單例 ---
_heartbeat_monitor: Optional['HeartbeatMonitor'] = None


class HeartbeatMonitor:
    """通用 Heartbeat 監控引擎"""

    def __init__(self, config: HeartbeatConfig):
        self.config = config
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_cycle: Optional[datetime] = None
        self._cycle_count: int = 0
        self._alerts_sent: int = 0
        self._notify_callback: Optional[Callable] = None

    def set_notify_callback(self, callback: Callable):
        """設定通知回調（用於 Telegram 推送）"""
        self._notify_callback = callback

    async def _notify(self, message: str):
        """發送通知"""
        if self._notify_callback:
            try:
                await self._notify_callback(message)
            except Exception as e:
                logger.error(f"Heartbeat 通知發送失敗: {e}")

    async def check_gis_health(self) -> List[str]:
        """GIS 異常檢測：檢查 sensor != normal 且未 ack"""
        alerts = []
        try:
            from skills.gis_alert_skill import check_gis_status
            result = await check_gis_status(manual_trigger=False)
            if result and result.get('status') == 'success':
                sensors = result.get('data', {}).get('sensors', [])
                for sensor in sensors:
                    status = sensor.get('status', '')
                    acked = sensor.get('acked', False)
                    if status not in ('normal', 'default', 'maint') and not acked:
                        uid = sensor.get('uid', 'unknown')
                        station = sensor.get('station', '')
                        alerts.append(
                            f"🛰️ GIS 異常: {uid} ({station}) 狀態={status} (未確認)"
                        )
        except ImportError:
            logger.debug("GIS skill 未加載，跳過 GIS 健康檢查")
        except Exception as e:
            logger.error(f"GIS 健康檢查失敗: {e}")
        return alerts

    async def check_stock_alerts(self) -> List[str]:
        """股票價格警報"""
        alerts = []
        if not self.config.stock_watchlist:
            return alerts
        try:
            import yfinance as yf
            for symbol, threshold_pct in self.config.stock_watchlist.items():
                try:
                    ticker = yf.Ticker(symbol)
                    fast_info = ticker.fast_info
                    info = ticker.info
                    price = fast_info.get('last_price') or info.get('currentPrice')
                    prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
                    if price and prev_close:
                        change_pct = ((price - prev_close) / prev_close) * 100
                        if abs(change_pct) >= abs(threshold_pct):
                            direction = "📈" if change_pct > 0 else "📉"
                            name = info.get('shortName', symbol)
                            alerts.append(
                                f"{direction} 股票警報: {name} ({symbol}) ${price:.2f} "
                                f"({change_pct:+.2f}%) 觸發閾值 ±{threshold_pct}%"
                            )
                except Exception as e:
                    logger.error(f"股票 {symbol} 檢查失敗: {e}")
        except ImportError:
            logger.debug("yfinance 未安裝，跳過股票警報")
        except Exception as e:
            logger.error(f"股票警報檢查失敗: {e}")
        return alerts

    async def check_system_health(self) -> List[str]:
        """系統健康檢查"""
        alerts = []
        try:
            # 檢查 DuckDB 連線
            import duckdb
            conn = duckdb.connect('alice_core.db', read_only=True)
            conn.execute("SELECT 1")
            conn.close()
        except Exception as e:
            alerts.append(f"🖥️ DuckDB 數據中樞異常: {e}")
        return alerts

    async def run_cycle(self) -> Dict:
        """執行一次完整巡檢"""
        all_alerts = []

        if self.config.gis_enabled:
            gis_alerts = await self.check_gis_health()
            all_alerts.extend(gis_alerts)

        if self.config.stock_enabled and self.config.stock_watchlist:
            stock_alerts = await self.check_stock_alerts()
            all_alerts.extend(stock_alerts)

        if self.config.system_enabled:
            sys_alerts = await self.check_system_health()
            all_alerts.extend(sys_alerts)

        self._cycle_count += 1
        self._last_cycle = datetime.now()

        if all_alerts:
            self._alerts_sent += len(all_alerts)
            alert_msg = "\n".join(all_alerts)
            await self._notify(f"🔔 Heartbeat 巡檢 #{self._cycle_count}\n{alert_msg}")

        return {
            'cycle': self._cycle_count,
            'alerts': all_alerts,
            'alert_count': len(all_alerts),
            'timestamp': self._last_cycle.isoformat()
        }

    async def _loop(self):
        """背景巡檢迴圈"""
        while self._running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"Heartbeat 巡檢異常: {e}")
                await self._notify(f"⚠️ Heartbeat 巡檢異常: {e}")
            await asyncio.sleep(self.config.interval_seconds)

    async def start(self) -> Dict:
        """啟動背景監控"""
        if self._running:
            return {'status': 'already_running', 'cycle_count': self._cycle_count}
        self._running = True
        self._task = asyncio.create_task(self._loop())
        await self._notify(
            f"✅ Heartbeat 監控已啟動\n"
            f"• 間隔: {self.config.interval_seconds}s\n"
            f"• GIS: {'✅' if self.config.gis_enabled else '❌'}\n"
            f"• 股票: {'✅' if self.config.stock_enabled else '❌'}\n"
            f"• 系統: {'✅' if self.config.system_enabled else '❌'}"
        )
        return {'status': 'started', 'interval_seconds': self.config.interval_seconds}

    async def stop(self) -> Dict:
        """停止監控"""
        if not self._running:
            return {'status': 'already_stopped'}
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._notify(
            f"⏹️ Heartbeat 監控已停止\n"
            f"• 總巡檢次數: {self._cycle_count}\n"
            f"• 總警報數: {self._alerts_sent}"
        )
        return {
            'status': 'stopped',
            'total_cycles': self._cycle_count,
            'total_alerts': self._alerts_sent
        }

    def get_status(self) -> Dict:
        """查詢當前狀態"""
        return {
            'running': self._running,
            'interval_seconds': self.config.interval_seconds,
            'gis_enabled': self.config.gis_enabled,
            'stock_enabled': self.config.stock_enabled,
            'system_enabled': self.config.system_enabled,
            'cycle_count': self._cycle_count,
            'alerts_sent': self._alerts_sent,
            'last_cycle': self._last_cycle.isoformat() if self._last_cycle else None,
            'watchlist_symbols': list(self.config.stock_watchlist.keys())
        }
