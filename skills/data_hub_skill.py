import os
import json
import duckdb
import datetime
from pathlib import Path
from base_skill import BaseSkill
from config import logger

class DataHubSkill(BaseSkill):
    def __init__(self, agent=None):
        super().__init__(agent)
        self.db_path = Path("data/alice_core.db")
        self._initialized = False

    @property
    def name(self):
        return "data_hub_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "manage_data_hub",
                "description": "管理 Alice 的核心數據中樞 (DuckDB)。用於執行 SQL 查詢、存儲事實、管理 Topic 快取與 Pub/Sub 機制。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "query", "execute", "store_fact", "get_fact",
                                "register_topic", "subscribe", "publish",
                                "get_with_policy", "warmup_topics"
                            ],
                            "description": "操作類型：query (查詢), execute (執行), store_fact (存儲), get_fact (獲取), register_topic (註冊 Topic), subscribe (訂閱), publish (發布), get_with_policy (帶 TTL 查詢), warmup_topics (預熱)"
                        },
                        "sql": {"type": "string", "description": "SQL 指令 (用於 query/execute)"},
                        "params": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "SQL 參數清單"
                        },
                        "fact_key": {"type": "string", "description": "事實鍵名 (用於 store_fact/get_fact)"},
                        "fact_value": {"type": "string", "description": "事實內容 (用於 store_fact)"},
                        "category": {"type": "string", "description": "分類 (如 'user_preference', 'asset_status')"},
                        "topic_name": {"type": "string", "description": "Topic 名稱 (用於 register_topic/subscribe/publish/get_with_policy)"},
                        "ttl_seconds": {"type": "integer", "description": "TTL 存活秒數 (用於 register_topic)"},
                        "min_interval_seconds": {"type": "integer", "description": "最小 fetch 間隔秒數 (用於 register_topic)"},
                        "subscriber_id": {"type": "string", "description": "訂閱者 ID (用於 subscribe)"},
                        "callback_info": {"type": "string", "description": "回調資訊 JSON (用於 subscribe)"},
                        "data": {"type": "string", "description": "發布的數據 JSON (用於 publish)"}
                    },
                    "required": ["action"]
                }
            }
        ]

    def execute(self, tool_name, args, context):
        if not self._initialized:
            self._ensure_db_initialized()
            self._initialized = True

        if tool_name == "manage_data_hub":
            action = args.get("action")
            sql = args.get("sql")
            params = args.get("params", [])

            if action == "query":
                return self._query(sql, params)
            elif action == "execute":
                return self._execute(sql, params)
            elif action == "store_fact":
                return self._store_fact(args.get("fact_key"), args.get("fact_value"), args.get("category", "general"))
            elif action == "get_fact":
                return self._get_fact(args.get("fact_key"))
            elif action == "register_topic":
                return self._register_topic(
                    args.get("topic_name"),
                    args.get("ttl_seconds", 300),
                    args.get("min_interval_seconds", 10)
                )
            elif action == "subscribe":
                return self._subscribe(
                    args.get("topic_name"),
                    args.get("subscriber_id"),
                    args.get("callback_info", "{}")
                )
            elif action == "publish":
                return self._publish(args.get("topic_name"), args.get("data"))
            elif action == "get_with_policy":
                return self._get_with_policy(args.get("topic_name"))
            elif action == "warmup_topics":
                return self._warmup_topics()
        return {"error": "Unsupported tool"}

    # ──────────────── 初始化 ────────────────

    def _ensure_db_initialized(self):
        """物理初始化：僅在必要時執行，避免啟動阻塞"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = duckdb.connect(str(self.db_path))
            conn.execute("CREATE SEQUENCE IF NOT EXISTS system_timeline_seq;")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_timeline (
                    event_id INTEGER PRIMARY KEY DEFAULT nextval('system_timeline_seq'),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type VARCHAR,
                    description TEXT,
                    real_time_sync VARCHAR
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_vault (
                    fact_key VARCHAR PRIMARY KEY,
                    fact_value TEXT,
                    category VARCHAR,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS gis_registry (
                    uid VARCHAR PRIMARY KEY,
                    site_id VARCHAR,
                    last_status VARCHAR,
                    is_anomaly BOOLEAN,
                    last_update TIMESTAMP
                )
            """)

            # ✅ P0-2 新增：Topic 快取登錄表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topic_registry (
                    topic_name VARCHAR PRIMARY KEY,
                    ttl_seconds INTEGER NOT NULL DEFAULT 300,
                    min_interval_seconds INTEGER NOT NULL DEFAULT 10,
                    last_fetch_time TIMESTAMP,
                    cached_value TEXT,
                    is_warm BOOLEAN DEFAULT FALSE,
                    is_stale BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ✅ P0-2 新增：Topic 訂閱者表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topic_subscribers (
                    id INTEGER PRIMARY KEY DEFAULT nextval('system_timeline_seq'),
                    topic_name VARCHAR NOT NULL,
                    subscriber_id VARCHAR NOT NULL,
                    callback_info TEXT DEFAULT '{}',
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(topic_name, subscriber_id)
                )
            """)

            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("""
                INSERT INTO system_timeline (event_type, description, real_time_sync)
                VALUES ('SYSTEM_INIT', 'DataHub V4 initialized with TopicPolicy + Pub/Sub.', ?)
            """, [now_str])

            conn.close()
            logger.info("Alice DataHub (V4 - TopicPolicy + Pub/Sub) initialized.")
        except Exception as e:
            logger.error(f"DataHub 初始化失敗: {e}")

    # ──────────────── 核心 CRUD (保留) ────────────────

    def _query(self, sql, params=None):
        if not sql or not isinstance(sql, str):
            return {"status": "error", "message": "sql 參數不得為空且必須為字串"}
        params = self._normalize_params(params)
        conn = None
        try:
            conn = duckdb.connect(str(self.db_path))
            if params:
                res = conn.execute(sql, params).fetchdf().to_dict(orient='records')
            else:
                res = conn.execute(sql).fetchdf().to_dict(orient='records')
            return {"status": "success", "data": res}
        except Exception as e:
            logger.error(f"[_query] SQL 錯誤: {e} | sql={sql[:120]} | params={params}")
            return {"status": "error", "message": str(e)}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _execute(self, sql, params=None):
        if not sql or not isinstance(sql, str):
            return {"status": "error", "message": "sql 參數不得為空且必須為字串"}
        params = self._normalize_params(params)
        conn = None
        try:
            conn = duckdb.connect(str(self.db_path))
            if params:
                conn.execute(sql, params)
            else:
                conn.execute(sql)
            conn.commit()
            return {"status": "success"}
        except Exception as e:
            logger.error(f"[_execute] SQL 錯誤: {e} | sql={sql[:120]} | params={params}")
            return {"status": "error", "message": str(e)}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _normalize_params(self, params):
        """將 params 正規化為 list 或 None，防禦 LLM 傳入錯誤型別（如字串、None、空陣列）"""
        if params is None:
            return None
        if isinstance(params, (list, tuple)):
            return list(params) if len(params) > 0 else None
        if isinstance(params, str):
            stripped = params.strip()
            if not stripped or stripped.lower() == "null":
                return None
            # 嘗試解析 JSON 陣列字串
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed if len(parsed) > 0 else None
                if parsed is None:
                    return None
            except (json.JSONDecodeError, TypeError):
                pass
            # 單一字串：包成單元素 list
            return [stripped]
        # 其他型別（如 int, dict）：包成單元素 list
        return [params]

    def _store_fact(self, key, value, category):
        if not key:
            logger.error(f"[store_fact] 拒絕寫入：fact_key 為空 (key={repr(key)}, value={repr(value)})")
            return {"status": "error", "message": "fact_key 不得為空，請檢查工具呼叫參數是否正確傳遞"}
        conn = None
        try:
            conn = duckdb.connect(str(self.db_path))
            conn.execute("""
                INSERT OR REPLACE INTO user_vault (fact_key, fact_value, category, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, [key, value if value is not None else "", category or "general"])
            conn.commit()
            result = conn.execute(
                "SELECT fact_key FROM user_vault WHERE fact_key = ?", [key]
            ).fetchone()
            if not result:
                logger.error(f"[store_fact] 寫後驗證失敗：key='{key}' 寫入後仍無法讀回")
                return {"status": "error", "message": f"寫入驗證失敗：'{key}' 未出現在資料庫中"}
            logger.info(f"[store_fact] 成功寫入：key='{key}', category='{category}'")
            return {"status": "success", "message": f"事實 '{key}' 已存入保險箱。"}
        except Exception as e:
            logger.error(f"[store_fact] 例外：{e}")
            return {"status": "error", "message": str(e)}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _get_fact(self, key):
        try:
            conn = duckdb.connect(str(self.db_path))
            res = conn.execute("SELECT fact_value FROM user_vault WHERE fact_key = ?", [key]).fetchone()
            conn.close()
            if res:
                return {"status": "success", "value": res[0]}
            return {"status": "not_found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ──────────────── P0-2 新增：TopicPolicy + Pub/Sub ────────────────

    def _register_topic(self, topic_name, ttl_seconds, min_interval_seconds):
        """註冊一個 Topic，設定其 TTL 與最小 fetch 間隔"""
        if not topic_name:
            return {"status": "error", "message": "topic_name 為必填"}
        try:
            conn = duckdb.connect(str(self.db_path))
            conn.execute("""
                INSERT OR REPLACE INTO topic_registry
                    (topic_name, ttl_seconds, min_interval_seconds)
                VALUES (?, ?, ?)
            """, [topic_name, ttl_seconds, min_interval_seconds])
            conn.close()
            logger.info(f"Topic '{topic_name}' registered: TTL={ttl_seconds}s, min_interval={min_interval_seconds}s")
            return {
                "status": "success",
                "message": f"Topic '{topic_name}' 已註冊",
                "config": {"ttl_seconds": ttl_seconds, "min_interval_seconds": min_interval_seconds}
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _subscribe(self, topic_name, subscriber_id, callback_info):
        """訂閱一個 Topic，當 Topic 更新時會通知訂閱者"""
        if not topic_name or not subscriber_id:
            return {"status": "error", "message": "topic_name 與 subscriber_id 為必填"}
        try:
            conn = duckdb.connect(str(self.db_path))
            conn.execute("""
                INSERT INTO topic_subscribers (topic_name, subscriber_id, callback_info)
                VALUES (?, ?, ?)
                ON CONFLICT (topic_name, subscriber_id)
                DO UPDATE SET callback_info = excluded.callback_info
            """, [topic_name, subscriber_id, callback_info])
            conn.close()
            logger.info(f"Subscriber '{subscriber_id}' → Topic '{topic_name}'")
            return {"status": "success", "message": f"已訂閱 Topic '{topic_name}'"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _publish(self, topic_name, data):
        """發布數據到 Topic：更新快取值 + 標記非 stale + 回傳訂閱者清單"""
        if not topic_name:
            return {"status": "error", "message": "topic_name 為必填"}
        try:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn = duckdb.connect(str(self.db_path))

            conn.execute("""
                UPDATE topic_registry
                SET cached_value = ?, last_fetch_time = ?, is_stale = FALSE
                WHERE topic_name = ?
            """, [data or "{}", now, topic_name])

            subscribers = conn.execute("""
                SELECT subscriber_id, callback_info
                FROM topic_subscribers
                WHERE topic_name = ?
            """, [topic_name]).fetchall()

            conn.close()

            subscriber_list = [
                {"subscriber_id": s[0], "callback_info": s[1]}
                for s in subscribers
            ]

            logger.info(f"Published to '{topic_name}': {len(subscriber_list)} subscribers notified")
            return {
                "status": "success",
                "message": f"已發布到 Topic '{topic_name}'",
                "subscribers_notified": len(subscriber_list),
                "subscribers": subscriber_list
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_with_policy(self, topic_name):
        """
        根據 TopicPolicy 獲取數據：
        - 若快取未過期 → 直接回傳 cached_value
        - 若過期但未達 min_interval → 回傳 stale 數據
        - 若過期且超過 min_interval → 回傳 stale + 建議 refresh
        """
        if not topic_name:
            return {"status": "error", "message": "topic_name 為必填"}
        try:
            now = datetime.datetime.now()
            now_str = now.strftime('%Y-%m-%d %H:%M:%S')
            conn = duckdb.connect(str(self.db_path))

            topic = conn.execute("""
                SELECT topic_name, ttl_seconds, min_interval_seconds,
                       last_fetch_time, cached_value, is_warm
                FROM topic_registry
                WHERE topic_name = ?
            """, [topic_name]).fetchone()

            if not topic:
                conn.close()
                return {"status": "not_found", "message": f"Topic '{topic_name}' 尚未註冊，請先 register_topic"}

            ttl = topic[1]
            min_interval = topic[2]
            last_fetch = topic[3]
            cached_value = topic[4]

            if last_fetch:
                if isinstance(last_fetch, str):
                    last_fetch_dt = datetime.datetime.strptime(last_fetch, '%Y-%m-%d %H:%M:%S')
                else:
                    last_fetch_dt = last_fetch
                elapsed = (now - last_fetch_dt).total_seconds()
            else:
                elapsed = float('inf')

            is_fresh = elapsed < ttl
            can_refetch = elapsed >= min_interval
            is_stale = not is_fresh

            if is_stale:
                conn.execute("""
                    UPDATE topic_registry SET is_stale = TRUE WHERE topic_name = ?
                """, [topic_name])

            conn.close()

            result = {
                "status": "success",
                "topic": topic_name,
                "data": json.loads(cached_value) if cached_value else None,
                "fresh": is_fresh,
                "stale": is_stale,
                "can_refetch": can_refetch,
                "elapsed_seconds": elapsed if elapsed != float('inf') else None,
                "ttl_seconds": ttl,
                "checked_at": now_str
            }

            if is_fresh:
                result["source"] = "cache (fresh)"
            elif can_refetch:
                result["source"] = "cache (stale - refresh recommended)"
            else:
                result["source"] = "cache (stale - min_interval not met)"

            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _warmup_topics(self):
        """冷啟動預熱：將 is_warm=TRUE 的所有 Topic 標記為需要 refresh"""
        try:
            conn = duckdb.connect(str(self.db_path))

            warm_topics = conn.execute("""
                SELECT topic_name, ttl_seconds, min_interval_seconds
                FROM topic_registry
                WHERE is_warm = TRUE
            """).fetchall()

            conn.execute("""
                UPDATE topic_registry SET is_stale = TRUE WHERE is_warm = TRUE
            """)

            conn.close()

            topic_list = [
                {"topic_name": t[0], "ttl_seconds": t[1], "min_interval_seconds": t[2]}
                for t in warm_topics
            ]

            logger.info(f"Warmup: {len(topic_list)} topics flagged for refresh")
            return {
                "status": "success",
                "warm_topics_count": len(topic_list),
                "topics": topic_list,
                "message": f"{len(topic_list)} 個 Topic 已標記為待刷新"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
