"""
IBroker 抽象交易層 + BrokerRegistry 全域註冊表 v1.0
統一券商介面，任何新券商只需實作 IBroker 並註冊即可
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class IBroker(ABC):
    """券商抽象介面 — 所有券商引擎必須實作此介面"""

    @abstractmethod
    async def login(self) -> dict:
        """登入券商，回傳 {'status': 'success'|'captcha_required'|'error', ...}"""
        ...

    @abstractmethod
    async def get_positions(self) -> dict:
        """取得持倉，回傳 {'status': ..., 'positions': [...]} """
        ...

    @abstractmethod
    async def get_orders(self) -> dict:
        """取得當日委託，回傳 {'status': ..., 'orders': [...]} """
        ...

    @abstractmethod
    async def place_order(self, symbol: str, side: str, price: float, quantity: int) -> dict:
        """下單，回傳 {'status': ..., 'message': ...}"""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> dict:
        """取消委託，回傳 {'status': ..., 'message': ...}"""
        ...

    @abstractmethod
    async def get_balance(self) -> dict:
        """取得帳戶餘額，回傳 {'status': ..., 'balance_raw': ...}"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """關閉瀏覽器與釋放資源"""
        ...


class BrokerRegistry:
    """全域券商註冊表 (Singleton) — 管理所有已註冊的券商引擎"""

    _instance: Optional["BrokerRegistry"] = None

    def __new__(cls) -> "BrokerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._engines: Dict[str, IBroker] = {}
            cls._instance._metadata: Dict[str, dict] = {}
        return cls._instance

    def register(self, broker_id: str, engine: IBroker, metadata: Optional[dict] = None) -> None:
        """註冊券商引擎"""
        self._engines[broker_id] = engine
        self._metadata[broker_id] = metadata or {}
        logger.info(f"📋 BrokerRegistry: 已註冊 '{broker_id}'")

    def unregister(self, broker_id: str) -> bool:
        """移除券商引擎"""
        if broker_id in self._engines:
            del self._engines[broker_id]
            self._metadata.pop(broker_id, None)
            logger.info(f"📋 BrokerRegistry: 已移除 '{broker_id}'")
            return True
        return False

    def get(self, broker_id: str) -> Optional[IBroker]:
        """取得券商引擎"""
        return self._engines.get(broker_id)

    def list_all(self) -> List[dict]:
        """列出所有已註冊的券商"""
        return [
            {
                "id": broker_id,
                "metadata": self._metadata.get(broker_id, {}),
                "has_engine": engine is not None,
            }
            for broker_id, engine in self._engines.items()
        ]

    def get_all_engines(self) -> Dict[str, IBroker]:
        """取得所有引擎字典"""
        return dict(self._engines)

    async def close_all(self) -> None:
        """關閉所有券商引擎"""
        for broker_id, engine in list(self._engines.items()):
            try:
                await engine.close()
                logger.info(f"📋 BrokerRegistry: 已關閉 '{broker_id}'")
            except Exception as e:
                logger.error(f"📋 BrokerRegistry: 關閉 '{broker_id}' 時發生錯誤: {e}")
        self._engines.clear()
        self._metadata.clear()


# 全局 singleton 實例
broker_registry = BrokerRegistry()
