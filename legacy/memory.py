import json
import uuid
import sqlite3
from pathlib import Path
from datetime import datetime
from config import logger

class MemorySystem:
    def __init__(self, base_dir="memory"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        self.short_term_file = self.base_dir / "short_term.json"
        self.medium_term_file = self.base_dir / "medium_term.json"
        self.long_term_file = self.base_dir / "long_term.json"
        self.tasks_file = self.base_dir / "tasks.json"
        
        self.db_path = self.base_dir / "fts_memory.db"
        self._init_fts_db()

        # === 向量記憶層 (Qdrant 本地模式，無需 Docker) ===
        self._qdrant_client = None
        self._qdrant_available = False
        self._init_qdrant()

        # === 記憶進化引擎 (Memory Evolution Engine v1.0) ===
        self.scores_file = self.base_dir / "memory_scores.json"
        self.memory_scores = {}  # {memory_id: {"score": float, "access_count": int, "last_accessed": str, "created": str, "source": str}}

        self.short_term = []
        self.medium_term = [] # Stores summaries
        self.long_term = {
            "user_info": {},    # Key-value pairs like {"name": "Alice"}
            "preferences": [], 
            "knowledge": [],
            "core_directives": [], # 新增：存放核心教訓與鐵律
            "settings": {}      # 新增：儲存系統設定 (如語音)
        }
        self.tasks = [] # To-Do list (Mixed with scheduled tasks)
        
        self.load_all()
        self.unsaved_changes = False

    def _init_fts_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_memory 
                USING fts5(timestamp, role, content, summary)
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"FTS DB Init Error: {e}")

    def _init_qdrant(self):
        """初始化 Qdrant 本地向量庫（無需 Docker，純檔案模式）。
        若 qdrant-client 未安裝或無法啟動，則優雅降級為純 FTS 模式。"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            qdrant_path = self.base_dir / "qdrant_data"
            qdrant_path.mkdir(exist_ok=True)

            self._qdrant_client = QdrantClient(path=str(qdrant_path))
            collections = [c.name for c in self._qdrant_client.get_collections().collections]

            if "alice_memories" not in collections:
                self._qdrant_client.create_collection(
                    collection_name="alice_memories",
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
                )
                logger.info("🧬 [Qdrant] 向量庫已建立 (768d / Cosine / 本地檔案模式)")
            self._qdrant_available = True
        except Exception as e:
            logger.info(f"📝 [Qdrant] 向量庫未啟用（qdrant-client 未安裝或初始化失敗），降級為純 FTS 模式: {e}")

    def _embed_text(self, text: str) -> list | None:
        """使用 Ollama nomic-embed-text 做純 Embedding（不經任何 LLM，避免循環）"""
        try:
            import requests
            r = requests.post(
                "http://localhost:11434/api/embed",
                json={"model": "nomic-embed-text", "input": text[:500]},
                timeout=10
            )
            if r.status_code == 200:
                return r.json()["embeddings"][0]
        except Exception:
            pass
        return None

    def _add_to_qdrant(self, timestamp: str, text: str):
        """非阻塞寫入 Qdrant 向量庫（純 Embedding，不調用 LLM）。
        此為核心安全設計：永遠不會觸發 AI 回覆循環。"""
        if not self._qdrant_available or not text:
            return
        try:
            vector = self._embed_text(text)
            if not vector:
                return
            from qdrant_client.models import PointStruct
            import uuid
            point_id = str(uuid.uuid4())[:8]
            self._qdrant_client.upsert(
                collection_name="alice_memories",
                points=[PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"timestamp": timestamp, "text": text[:500]}
                )]
            )
        except Exception:
            pass  # 向量寫入失敗不影響主流程

    def search_vector_memory(self, query: str, limit: int = 5) -> list:
        """純向量語義搜尋（語意相似度）"""
        if not self._qdrant_available:
            return []
        vector = self._embed_text(query)
        if not vector:
            return []
        try:
            results = self._qdrant_client.search(
                collection_name="alice_memories",
                query_vector=vector,
                limit=limit
            )
            return [{"timestamp": r.payload.get("timestamp", ""),
                     "text": r.payload.get("text", ""),
                     "score": round(r.score, 4)} for r in results]
        except Exception:
            return []

    def hybrid_search(self, query: str, limit: int = 10) -> list:
        """混合搜尋：向量語義 + FTS 關鍵字，合併去重排序。
        向量結果在前（語意優先），FTS 結果在後補充（關鍵字覆蓋）。"""
        results = []

        # 1. 向量搜尋
        vec_results = self.search_vector_memory(query, limit)
        seen_texts = set()
        for r in vec_results:
            key = r["text"][:100]
            if key not in seen_texts:
                seen_texts.add(key)
                results.append({**r, "source": "vector"})

        # 2. FTS 全文搜尋
        try:
            fts_results = self.search_fts_memory(query, limit)
            for r in fts_results:
                key = r.get("content", "")[:100]
                if key and key not in seen_texts:
                    seen_texts.add(key)
                    results.append({
                        "timestamp": r.get("timestamp", ""),
                        "text": r.get("content", ""),
                        "score": 0.5,
                        "source": "fts"
                    })
        except Exception:
            pass

        return results[:limit]

    def add_fts_memory(self, timestamp, role, content, summary=""):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                INSERT INTO fts_memory(timestamp, role, content, summary)
                VALUES(?, ?, ?, ?)
            ''', (timestamp, role, content, summary))
            conn.commit()
            conn.close()
            # 檢查 FTS 記憶表大小，超過 1000 筆則壓縮舊記錄為摘要
            self._check_fts_size()
            # 🔒 安全寫入向量層：純 Embedding，不經 LLM（永不觸發循環）
            if self._qdrant_available:
                try:
                    self._add_to_qdrant(timestamp, content)
                except Exception:
                    pass
            # 🧬 記憶進化引擎：為每筆新記憶建立初始評分
            self._score_memory(timestamp, content)
        except Exception as e:
            logger.error(f"FTS Insert Error: {e}")

    def search_fts_memory(self, query_text, limit=5):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # 支援簡單的 FTS match
            c.execute('''
                SELECT timestamp, role, content, summary 
                FROM fts_memory 
                WHERE fts_memory MATCH ? 
                ORDER BY rank LIMIT ?
            ''', (query_text, limit))
            results = c.fetchall()
            conn.close()
            # 🧬 記憶進化引擎：命中加分
            for r in results:
                mem_id = f"fts_{r[0][:19]}"  # timestamp 作為 ID 前綴
                self._boost_score(mem_id, boost=0.05)
            return [{"timestamp": r[0], "role": r[1], "content": r[2], "summary": r[3]} for r in results]
        except Exception as e:
            logger.error(f"FTS Search Error: {e}")
            return []

    def load_all(self):
        def _load(path, default):
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except: pass
            return default

        self.short_term = _load(self.short_term_file, [])
        self.medium_term = _load(self.medium_term_file, [])
        
        # 載入長期記憶並進行型別檢查與修復
        loaded_long_term = _load(self.long_term_file, None)
        
        if isinstance(loaded_long_term, dict):
            self.long_term = loaded_long_term
        elif loaded_long_term is None:
            pass
        else:
            logger.warning("⚠️ 長期記憶格式錯誤 (非 Dict)，已重置為預設結構。")

        if self.long_term.get("user_info") is None or not isinstance(self.long_term.get("user_info"), dict):
            if self.long_term.get("user_info") is not None:
                logger.warning("⚠️ user_info 格式異常，已重置為 {}")
            self.long_term["user_info"] = {}
            
        if not isinstance(self.long_term.get("preferences"), list):
            self.long_term["preferences"] = []
            
        if not isinstance(self.long_term.get("knowledge"), list):
            self.long_term["knowledge"] = []
            
        if not isinstance(self.long_term.get("core_directives"), list):
            self.long_term["core_directives"] = []
            
        # 確保 settings 存在
        if "settings" not in self.long_term or not isinstance(self.long_term["settings"], dict):
            self.long_term["settings"] = {}
            
        self.tasks = _load(self.tasks_file, [])
        self._load_scores()

    def save_all_force(self):
        def _save(path, data):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        try:
            _save(self.short_term_file, self.short_term)
            _save(self.medium_term_file, self.medium_term)
            _save(self.long_term_file, self.long_term)
            _save(self.tasks_file, self.tasks)
            self._save_scores()
            logger.info("💾 [System] Memory Saved Successfully.")
            self.unsaved_changes = False
        except Exception as e:
            logger.error(f"Save failed: {e}")

    def add_short_term(self, role, content, reasoning_content=None):
        """Add to short term memory and return current count"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "role": role, 
            "content": content, 
            "timestamp": timestamp,
            "reasoning_content": reasoning_content
        }
        self.short_term.append(entry)
        self.unsaved_changes = True
        
        # 寫入 FTS (可作為未來語義搜索的基礎)
        if isinstance(content, str): # 有時 content 會是 dict (如 function call)
            self.add_fts_memory(timestamp, role, content)
            
        # 改為非同步儲存，這裡不再強制寫入磁碟，大幅提升回應速度
        # self.save_all_force() 
        
        # === 短期記憶自動清理：防止無限增生 ===
        if len(self.short_term) > 500:
            self.short_term = self.short_term[-200:]
            self._prune_long_term_lists()
            logger.info(f"🧹 記憶自動清理：短期 trim 至 200 筆，長期偏好/知識已修剪")
        
        return len(self.short_term)

    def get_recent_short_term(self, count=10):
        """取得最近 N 則短期記憶的原始對話內容，供跨模型繼承使用"""
        if not self.short_term:
            return []
        recent = self.short_term[-count:] if len(self.short_term) > count else self.short_term
        return recent

    # --- 排程任務管理 (新增功能) ---
    def add_scheduled_task(self, chat_id, content, target_time_dt, recurrence=None):
        """新增一個排程任務到 tasks.json。recurrence: None=一次性, 'daily'=每日循環"""
        task_id = str(uuid.uuid4())[:8]
        new_task = {
            "id": task_id,
            "type": "scheduled",
            "chat_id": chat_id,
            "task": content,
            "target_time": target_time_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "recurrence": recurrence,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.tasks.append(new_task)
        self.save_all_force() # 重要任務仍保持強制存檔，避免遺失
        return task_id

    def get_pending_scheduled_tasks(self):
        """取得所有尚未執行的排程任務"""
        pending = []
        for t in self.tasks:
            if isinstance(t, dict) and t.get("type") == "scheduled" and t.get("status") == "pending":
                pending.append(t)
        return pending

    def delete_task(self, task_id):
        """物理刪除任務（已完成或過期），不留記錄"""
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if not (isinstance(t, dict) and t.get("id") == task_id)]
        if len(self.tasks) < before:
            self.save_all_force()
            return True
        return False

    def mark_task_completed(self, task_id):
        """【向後兼容】標記任務為完成 → 現在直接物理刪除，不留記錄"""
        return self.delete_task(task_id)

    def cleanup_expired_tasks(self, expire_minutes=5):
        """批次清理過期任務（物理刪除，不留記錄）"""
        now = datetime.now()
        removed = 0
        for t in list(self.tasks):
            if isinstance(t, dict) and t.get("type") == "scheduled" and t.get("status") == "pending":
                try:
                    target = datetime.strptime(t["target_time"], "%Y-%m-%d %H:%M:%S")
                    if (now - target).total_seconds() > expire_minutes * 60:
                        self.tasks.remove(t)
                        removed += 1
                except Exception:
                    pass
        if removed:
            self.save_all_force()
        return removed

    # --- (以下為原有的記憶整合邏輯) ---

    def get_batch_for_consolidation(self, limit=40):
        if len(self.short_term) < limit:
            return None
        return self.short_term[:limit]

    # --- 智慧壓縮 (v6.6) ---
    def _check_fts_size(self):
        """檢查 FTS 記憶表大小，超過 800 筆觸發進化引擎，超過 1000 筆強制壓縮"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM fts_memory")
            count = c.fetchone()[0]
            conn.close()
            
            # 進化引擎：800 筆時啟動價值型淘汰
            if count > 800:
                evolved = self._evolve_memories()
                if evolved > 0:
                    logger.info(f"🧬 [Evolution] 進化引擎淘汰 {evolved} 筆，當前評分表 {len(self.memory_scores)} 筆")
            
            # 安全網：1000 筆時強制數量型壓縮（防止評分表未追蹤到的舊記錄增生）
            if count > 1000:
                self._compress_fts(count - 1000 + 500)
        except Exception as e:
            logger.error(f"FTS Size Check Error: {e}")

    def _compress_fts(self, to_remove):
        """取出最舊 N 筆 FTS 記錄，壓縮為摘要後刪除"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT content FROM fts_memory ORDER BY rowid LIMIT ?", (to_remove,))
            rows = c.fetchall()
            
            if rows:
                # 提取非空的 content 摘要
                contents = [r[0][:100] for r in rows if r[0] and isinstance(r[0], str)]
                unique_topics = list(dict.fromkeys(contents))[:20]  # 去重後取前 20
                summary = "【FTS 舊記憶壓縮摘要】" + " | ".join(unique_topics)
                
                # 將摘要存入長期記憶 knowledge
                if len(self.long_term.get("knowledge", [])) >= 300:
                    self.long_term["knowledge"] = self.long_term["knowledge"][-250:]
                self.long_term["knowledge"].append(summary)
                
                # 刪除最舊的記錄
                c.execute("DELETE FROM fts_memory WHERE rowid IN (SELECT rowid FROM fts_memory ORDER BY rowid LIMIT ?)", (to_remove,))
                conn.commit()
                logger.info(f"🧹 [FTS 壓縮] 已將 {to_remove} 筆舊記憶壓縮為摘要")
            
            conn.close()
        except Exception as e:
            logger.error(f"FTS Compression Error: {e}")

    def _prune_long_term_lists(self):
        """偏好超過 200 條或知識超過 300 條時，將舊項目壓縮為摘要"""
        # 偏好上限保護
        prefs = self.long_term.get("preferences", [])
        if isinstance(prefs, list) and len(prefs) > 200:
            overflow = prefs[:-150]  # 超過 150 條的舊項目
            if overflow:
                summary = "【偏好壓縮摘要】" + " | ".join(overflow[:30])
                if len(self.long_term.get("knowledge", [])) >= 300:
                    self.long_term["knowledge"] = self.long_term["knowledge"][-250:]
                self.long_term["knowledge"].append(summary)
            self.long_term["preferences"] = prefs[-150:]  # 保留最近 150 條
            logger.info(f"🧹 [偏好壓縮] 已將 {len(overflow)} 條舊偏好壓縮為摘要")
        
        # 知識上限保護
        knowledge = self.long_term.get("knowledge", [])
        if isinstance(knowledge, list) and len(knowledge) > 300:
            overflow = knowledge[:-250]  # 超過 250 條的舊項目
            if overflow:
                summary = "【知識壓縮摘要】" + " | ".join(overflow[:30])
                self.long_term["knowledge"] = self.long_term["knowledge"][-250:]
                self.long_term["knowledge"].append(summary)
                logger.info(f"🧹 [知識壓縮] 已將 {len(overflow)} 條舊知識合併為摘要")

    def commit_consolidation(self, batch_size, ai_result):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        if ai_result.get("summary"):
            self.medium_term.append({
                "date": timestamp,
                "summary": ai_result["summary"]
            })
            if len(self.medium_term) > 50:
                self.medium_term = self.medium_term[-50:]

        updates = ai_result.get("new_facts", {})
        
        if "user_info" in updates and isinstance(updates["user_info"], dict):
            if isinstance(self.long_term["user_info"], dict):
                self.long_term["user_info"].update(updates["user_info"])
            else:
                self.long_term["user_info"] = updates["user_info"]
        
        for cat in ["preferences", "knowledge"]:
            if cat in updates and isinstance(updates[cat], list):
                if not isinstance(self.long_term.get(cat), list):
                    self.long_term[cat] = []
                    
                current_set = set(self.long_term[cat])
                for item in updates[cat]:
                    if item not in current_set:
                        self.long_term[cat].append(item)

        if ai_result.get("new_tasks") and isinstance(ai_result["new_tasks"], list):
            for task in ai_result["new_tasks"]:
                # 一般文字型任務 (非排程)
                self.tasks.append({
                    "id": str(uuid.uuid4())[:8],
                    "type": "todo",
                    "task": task,
                    "created_at": timestamp,
                    "status": "pending"
                })

        if batch_size > 0:
            self.short_term = self.short_term[batch_size:]
        
        self.unsaved_changes = True
        # 智慧壓縮：偏好超過 200 條或知識超過 300 條時自動合併為摘要
        self._prune_long_term_lists()
        # 移除強制儲存，改由外部 Agent 呼叫 background save
        # self.save_all_force()
        logger.info(f"🧠 [Memory] Consolidated {batch_size} messages.")

    # ============================================================
    # 🧬 記憶進化引擎 (Memory Evolution Engine v1.0)
    # 借鑒 hermes-agent memory_manager.py 的評分/淘汰/嵌入閉環
    # 核心哲學：記憶價值隨時間衰減，常用記憶保持活力，淘汰前摘要保留
    # ============================================================

    def _load_scores(self):
        """載入記憶評分資料（原子讀取，失敗不中斷）"""
        try:
            if self.scores_file.exists():
                with open(self.scores_file, "r", encoding="utf-8") as f:
                    self.memory_scores = json.load(f)
        except Exception:
            self.memory_scores = {}

    def _save_scores(self):
        """儲存記憶評分資料（原子寫入：tempfile + os.replace）"""
        import tempfile, os
        try:
            fd, tmp = tempfile.mkstemp(suffix=".json", dir=str(self.base_dir))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.memory_scores, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.scores_file)
        except Exception as e:
            logger.error(f"Memory Scores Save Error: {e}")

    def _score_memory(self, timestamp: str, content: str, source: str = "fts"):
        """計算記憶的初始價值分數。
        
        分數公式 = 基礎分 (5.0) 
                 + 內容深度加分 (1~800 chars → 0.1~1.6)
                 + 關鍵資訊加分 (含數字/日期/金額 +0.5)
                 - 重複性懲罰 (與現有記憶相似 → -1.0)
        
        分數範圍：0.0 ~ 10.0（初始約 5.5~7.1）
        """
        mem_id = f"mem_{timestamp[:19]}"
        
        # 避免重複評分
        if mem_id in self.memory_scores:
            return self.memory_scores[mem_id]["score"]
        
        score = 5.0
        
        # 內容深度：越長越可能有價值（但非線性，上限 1.6）
        content_len = len(content) if content else 0
        score += min(content_len / 500, 1.6)
        
        # 關鍵資訊加分：包含數字、日期、金額
        import re
        has_numbers = bool(re.search(r'\d{2,}', content))
        has_date = bool(re.search(r'\d{4}[-/年]\d{1,2}[-/月]', content))
        has_currency = bool(re.search(r'[¥$€]|NT\$|元|萬|億', content))
        if has_numbers or has_date or has_currency:
            score += 0.5
        
        # 重複性懲罰：與現有高評分記憶內容相似則扣分
        for existing_id, existing_data in self.memory_scores.items():
            if existing_data.get("content_sample", "")[:50] == content[:50]:
                score -= 1.0
                break
        
        score = max(0.0, min(10.0, score))
        
        self.memory_scores[mem_id] = {
            "score": round(score, 4),
            "access_count": 0,
            "last_accessed": timestamp,
            "created": timestamp,
            "source": source,
            "content_sample": content[:200]  # 保留前 200 字作為採樣（不存全文）
        }
        self.unsaved_changes = True

    def _boost_score(self, mem_id: str, boost: float = 0.1):
        """當記憶被搜尋命中時，提升其分數（上限 10.0）。
        使用頻率越高的記憶越有價值，自然保留下來。"""
        if mem_id in self.memory_scores:
            data = self.memory_scores[mem_id]
            data["score"] = min(10.0, data["score"] + boost)
            data["access_count"] = data.get("access_count", 0) + 1
            data["last_accessed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.unsaved_changes = True
            return data["score"]
        
        # 若記憶尚未在評分表中（例如從 FTS 直接命中），自動建立
        self.memory_scores[mem_id] = {
            "score": round(5.0 + boost, 4),
            "access_count": 1,
            "last_accessed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "auto",
            "content_sample": ""
        }
        self.unsaved_changes = True
        return 5.0 + boost

    def _decay_scores(self, decay_rate: float = 0.02):
        """全域時間衰減：所有記憶的分數隨時間自然下降。
        
        衰減公式：new_score = score * (1 - decay_rate)
        預設每次衰減 2%，約 35 次後降至原始的一半。
        通常在 _evolve_memories 中被呼叫。
        """
        decayed = 0
        for mem_id in list(self.memory_scores.keys()):
            data = self.memory_scores[mem_id]
            old_score = data["score"]
            data["score"] = round(old_score * (1 - decay_rate), 4)
            if old_score != data["score"]:
                decayed += 1
        
        if decayed > 0:
            self.unsaved_changes = True
            logger.info(f"🧬 [Evolution] 已對 {decayed} 筆記憶執行時間衰減 (rate={decay_rate})")
        return decayed

    def _evolve_memories(self, min_score: float = 1.5, max_total: int = 500):
        """進化引擎主循環：評分衰減 → 淘汰低分 → 摘要保留。
        
        流程：
        1. 時間衰減（所有記憶 -2%）
        2. 淘汰分數低於 min_score 的記憶
        3. 若仍超過 max_total，淘汰最低分直到達標
        4. 被淘汰的記憶壓縮為摘要存入長期知識庫
        
        觸發時機：FTS 超過 800 筆時（在 _check_fts_size 中觸發）
        """
        # 1. 時間衰減
        self._decay_scores()
        
        # 2. 找出低於閾值的記憶
        to_evict = []
        for mem_id, data in list(self.memory_scores.items()):
            if data["score"] < min_score:
                to_evict.append((mem_id, data))
        
        # 3. 若仍超量，按分數排序淘汰最低分
        remaining = {k: v for k, v in self.memory_scores.items() if v["score"] >= min_score}
        if len(remaining) > max_total:
            sorted_remaining = sorted(remaining.items(), key=lambda x: x[1]["score"])
            overflow = sorted_remaining[:len(sorted_remaining) - max_total]
            to_evict.extend(overflow)
        
        if not to_evict:
            return 0
        
        # 4. 摘要保留（取樣前 5 條內容，生成摘要）
        samples = [d.get("content_sample", "")[:80] for _, d in to_evict[:5] if d.get("content_sample")]
        summary = "【記憶進化摘要】" + " | ".join(samples) if samples else "【記憶進化摘要】無採樣內容"
        
        if len(self.long_term.get("knowledge", [])) >= 300:
            self.long_term["knowledge"] = self.long_term["knowledge"][-250:]
        self.long_term["knowledge"].append(summary)
        
        # 5. 從評分表中移除
        for mem_id, _ in to_evict:
            del self.memory_scores[mem_id]
        
        self.unsaved_changes = True
        logger.info(f"🧬 [Evolution] 淘汰 {len(to_evict)} 筆低分記憶，摘要已存入長期知識庫 (min_score={min_score})")
        return len(to_evict)

    def get_memory_health(self) -> dict:
        """取得記憶健康度報告（供 self_review_skill 調用）"""
        total = len(self.memory_scores)
        if total == 0:
            return {"total": 0, "avg_score": 0, "active": 0, "stale": 0, "health": "empty"}
        
        scores = [d["score"] for d in self.memory_scores.values()]
        avg_score = round(sum(scores) / total, 4)
        active = sum(1 for s in scores if s >= 3.0)
        stale = sum(1 for s in scores if s < 1.5)
        
        if avg_score >= 5.0:
            health = "excellent"
        elif avg_score >= 3.0:
            health = "good"
        elif avg_score >= 1.5:
            health = "fair"
        else:
            health = "critical"
        
        return {
            "total": total,
            "avg_score": avg_score,
            "active": active,
            "stale": stale,
            "health": health,
            "top_score": max(scores) if scores else 0,
            "bottom_score": min(scores) if scores else 0
        }

    def get_long_term_system_prompt(self):
        context = "【🧠 核心記憶庫】\n"
        
        # 最高優先級的系統鐵律
        if self.long_term.get("core_directives") and isinstance(self.long_term["core_directives"], list) and len(self.long_term["core_directives"]) > 0:
            context += "\n⚠️【系統鐵律與過往教訓 (Core Directives)】⚠️ (絕對遵守)\n"
            for i, rule in enumerate(self.long_term["core_directives"], 1):
                context += f"{i}. {rule}\n"
            context += "\n"
        
        if self.long_term.get("user_info") and isinstance(self.long_term["user_info"], dict):
            context += "[使用者資訊]: " + json.dumps(self.long_term["user_info"], ensure_ascii=False) + "\n"
        


        # 只顯示 type=todo 的待辦事項，避免混亂排程
        pending_tasks = [t['task'] for t in self.tasks if isinstance(t, dict) and t.get('status') == 'pending' and t.get('type') != 'scheduled']
        if pending_tasks:
            context += f"\n【📝 待辦事項 (Pending)】\n" + "\n".join([f"- {t}" for t in pending_tasks]) + "\n"
            
        recents = self.medium_term[-5:]
        if recents:
            context += "\n【📜 前情提要 (Recent Context)】\n"
            for r in recents:
                if isinstance(r, dict):
                    context += f"[{r.get('date', '')}] {r.get('summary', '')}\n"
        
        # 近期對話脈絡已由 Sliding Window (agent.get_cleaned_history) 處理，此處不再重複內嵌
            
        return context
