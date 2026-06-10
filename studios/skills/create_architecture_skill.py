"""
create_architecture_skill.py — Phase 3.1: /create-architecture
移植自 CCGS create-architecture SKILL.md

從 game-concept.md + map-systems 結果 → 主架構文件 + Required ADR 清單
支援 Foundation / Core / Extension 三層架構
"""

import json
import os
import re
from datetime import datetime
from typing import Any


class CreateArchitectureSkill:
    """主架構文件生成器 + ADR 清單"""

    name = "create_architecture"

    # ── ADR 模板清單（Foundation / Core / Extension）─────────────────
    FOUNDATION_ADRS = [
        {"id": "ADR-001", "title": "遊戲引擎與技術棧選定", "category": "Foundation",
         "question": "使用哪個遊戲引擎？版本？附帶哪些工具鏈？"},
        {"id": "ADR-002", "title": "程式語言與腳本策略", "category": "Foundation",
         "question": "主要開發語言？是否使用 DSL 或視覺化腳本？"},
        {"id": "ADR-003", "title": "版本控制與協作流程", "category": "Foundation",
         "question": "Git 分支策略？資產管線如何納入版本控制？"},
        {"id": "ADR-004", "title": "目錄結構與命名規範", "category": "Foundation",
         "question": "專案目錄結構？資源/場景/腳本命名規範？"},
        {"id": "ADR-005", "title": "建置與 CI/CD 管線", "category": "Foundation",
         "question": "如何自動化建置？目標平台？CI/CD 工具？"},
    ]

    CORE_ADRS = [
        {"id": "ADR-010", "title": "場景管理與加載策略", "category": "Core",
         "question": "場景如何組織？同步/非同步加載？場景轉換流程？"},
        {"id": "ADR-011", "title": "遊戲狀態機架構", "category": "Core",
         "question": "GameState 如何管理？狀態轉換規則？存檔/讀檔策略？"},
        {"id": "ADR-012", "title": "輸入系統架構", "category": "Core",
         "question": "輸入映射如何設計？支援哪些輸入裝置？按鍵重映射？"},
        {"id": "ADR-013", "title": "音訊系統架構", "category": "Core",
         "question": "音訊總線設計？SFX/BGM/環境音分層？動態混音？"},
        {"id": "ADR-014", "title": "UI/UX 框架選定", "category": "Core",
         "question": "UI 框架？佈局策略？多解析度適配？"},
        {"id": "ADR-015", "title": "數據持久化策略", "category": "Core",
         "question": "存檔格式？雲端存檔？資料庫選型？"},
        {"id": "ADR-016", "title": "網路與多人架構", "category": "Core",
         "question": "是否多人？Client-Server 或 P2P？同步模型？"},
    ]

    EXTENSION_ADRS = [
        {"id": "ADR-020", "title": "AI 系統架構", "category": "Extension",
         "question": "AI 使用行為樹/狀態機/GOAP？導航系統？"},
        {"id": "ADR-021", "title": "物理與碰撞系統", "category": "Extension",
         "question": "使用內建物理引擎或第三方？碰撞層設定？"},
        {"id": "ADR-022", "title": "粒子與 VFX 系統", "category": "Extension",
         "question": "粒子系統架構？GPU particles？自訂 shader？"},
        {"id": "ADR-023", "title": "動畫系統架構", "category": "Extension",
         "question": "AnimationTree 設計？動畫混合？IK 需求？"},
        {"id": "ADR-024", "title": "本地化架構", "category": "Extension",
         "question": "多語言支援策略？CSV/PO 格式？字型 Fallback？"},
        {"id": "ADR-025", "title": "效能預算與優化策略", "category": "Extension",
         "question": "FPS 目標？Draw call 預算？LOD 策略？"},
        {"id": "ADR-026", "title": "無障礙設計", "category": "Extension",
         "question": "色盲模式？字體縮放？控制器重新映射？"},
    ]

    ALL_ADRS = FOUNDATION_ADRS + CORE_ADRS + EXTENSION_ADRS

    # ── 架構文件模板段落 ────────────────────────────────────────
    ARCH_SECTIONS = [
        "1. 專案概述與設計目標",
        "2. 技術棧總覽",
        "3. 目錄結構",
        "4. 核心系統架構圖（文字描述）",
        "5. 模組依賴關係",
        "6. 資料流與事件系統",
        "7. 場景與資源管理",
        "8. 效能預算與約束",
        "9. 風險與技術債追蹤",
        "10. ADR 索引",
    ]

    @classmethod
    def init_session(cls, project_id: str, project_path: str,
                     game_concept: dict = None, systems_map: dict = None) -> dict:
        """初始化架構建立 session"""
        session = {
            "project_id": project_id,
            "project_path": project_path,
            "phase": "init",
            "game_concept": game_concept or {},
            "systems_map": systems_map or {},
            "architecture_doc": "",
            "selected_adrs": [],
            "adr_status": {},
            "current_section": 0,
            "sections_content": {},
        }

        # 自動偵測所需 ADR
        session["selected_adrs"] = cls._detect_required_adrs(systems_map or {})
        for adr in session["selected_adrs"]:
            session["adr_status"][adr["id"]] = "pending"

        return session

    @classmethod
    def _detect_required_adrs(cls, systems_map: dict) -> list:
        """根據系統地圖自動偵測需要的 ADR"""
        required = list(cls.FOUNDATION_ADRS)  # Foundation 永遠需要

        systems = systems_map.get("systems", [])
        system_names = " ".join(s.get("name", "") for s in systems).lower()

        # Core ADRs 條件偵測
        core_triggers = {
            "ADR-010": ["場景", "scene", "關卡", "level"],
            "ADR-011": ["狀態", "state", "存檔", "save"],
            "ADR-012": ["輸入", "input", "控制", "control"],
            "ADR-013": ["音訊", "audio", "音效", "sfx", "音樂", "music"],
            "ADR-014": ["ui", "介面", "hud", "選單", "menu"],
            "ADR-015": ["存檔", "save", "資料庫", "database", "持久"],
            "ADR-016": ["多人", "multiplayer", "網路", "network", "連線"],
        }

        for adr in cls.CORE_ADRS:
            triggers = core_triggers.get(adr["id"], [])
            if any(t in system_names for t in triggers):
                required.append(adr)

        # Extension ADRs 條件偵測
        ext_triggers = {
            "ADR-020": ["ai", "人工智慧", "行為", "behavior", "導航", "nav"],
            "ADR-021": ["物理", "physics", "碰撞", "collision"],
            "ADR-022": ["粒子", "particle", "vfx", "特效"],
            "ADR-023": ["動畫", "animation", "anim"],
            "ADR-024": ["本地化", "localization", "多語言", "i18n"],
            "ADR-025": ["效能", "performance", "優化", "optimize"],
            "ADR-026": ["無障礙", "accessibility", "a11y"],
        }

        for adr in cls.EXTENSION_ADRS:
            triggers = ext_triggers.get(adr["id"], [])
            if any(t in system_names for t in triggers):
                required.append(adr)

        return required

    @classmethod
    def get_section_prompt(cls, section_index: int, game_concept: dict,
                           systems_map: dict) -> str:
        """取得指定段落的引導提示"""
        prompts = {
            0: f"""請為遊戲「{game_concept.get('title', '未命名')}」撰寫架構文件的第 1 段：專案概述與設計目標。

包含：
- 專案一句話描述
- 核心設計支柱 (3-5 個)
- 目標平台與受眾
- 技術層面的主要挑戰

目前已知系統：{', '.join(s.get('name', '') for s in systems_map.get('systems', []))}""",

            1: f"""請撰寫第 2 段：技術棧總覽。

包含：
- 遊戲引擎及版本
- 主要程式語言
- 關鍵第三方庫/插件
- 開發工具鏈（IDE、版本控制、CI/CD）
- 資產製作工具（美術、音訊）""",

            2: f"""請撰寫第 3 段：目錄結構。

請以樹狀圖描述專案目錄結構，包含：
- src/（原始碼）
- assets/（美術、音訊等資源）
- scenes/（場景檔案）
- docs/（文件）
- tests/（測試）
- build/（建置輸出）

並簡述每個目錄的用途與命名規範。""",

            3: f"""請撰寫第 4 段：核心系統架構圖。

以文字描述系統架構：
- 頂層模組劃分
- 各模組職責
- 模組間的通訊方式（信號/事件/直接呼叫）
- 數據流向

已知系統：
{json.dumps([{'name': s.get('name'), 'tier': s.get('tier'), 'depends_on': s.get('depends_on', [])} for s in systems_map.get('systems', [])], ensure_ascii=False, indent=2)}""",

            4: f"""請撰寫第 5 段：模組依賴關係。

以清單形式描述每個模組的依賴：
- 模組名稱
- 依賴的其他模組
- 提供的介面/API
- 初始化順序

嚴禁循環依賴。標記任何潛在的依賴問題。""",

            5: f"""請撰寫第 6 段：資料流與事件系統。

包含：
- 事件總線設計（Global EventBus 或分散式信號）
- 常用事件清單
- 資料持久化流程
- 跨場景資料傳遞策略""",

            6: f"""請撰寫第 7 段：場景與資源管理。

包含：
- 場景分類（啟動場景、主選單、遊戲場景、載入場景）
- 資源引用策略（preload vs lazy load）
- 資源生命週期管理
- Asset Bundle 策略""",

            7: f"""請撰寫第 8 段：效能預算與約束。

包含：
- 目標 FPS
- Draw call 預算
- 記憶體預算
- CPU/GPU 瓶頸預測
- 最低硬體規格""",

            8: """請撰寫第 9 段：風險與技術債追蹤。

列出：
- 已識別的技術風險（高/中/低）
- 緩解策略
- 技術債項目
- 償還計畫""",

            9: f"""請撰寫第 10 段：ADR 索引。

列出所有需要的 ADR：
{chr(10).join(f'- {adr["id"]}: {adr["title"]} [{adr["category"]}]' for adr in cls.ALL_ADRS)}""",
        }

        return prompts.get(section_index, "")

    @classmethod
    def generate_architecture_doc(cls, sections_content: dict,
                                  game_concept: dict,
                                  selected_adrs: list) -> str:
        """將所有段落組合成完整架構文件"""
        doc = f"""# 技術架構文件：{game_concept.get('title', '未命名')}

> 生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}
> 文件版本：v1.0
> 狀態：Draft

---

"""
        for i, section_title in enumerate(cls.ARCH_SECTIONS):
            content = sections_content.get(str(i), "")
            doc += f"## {section_title}\n\n{content}\n\n---\n\n"

        doc += "## ADR 狀態\n\n"
        doc += "| ADR ID | 標題 | 類別 | 狀態 |\n"
        doc += "|:--|:--|:--|:--|\n"
        for adr in selected_adrs:
            doc += f"| {adr['id']} | {adr['title']} | {adr['category']} | ⏳ Pending |\n"

        return doc

    @classmethod
    def get_adr_status(cls, session: dict) -> list:
        """取得 ADR 狀態清單"""
        return [
            {**adr, "status": session.get("adr_status", {}).get(adr["id"], "pending")}
            for adr in session.get("selected_adrs", [])
        ]

    @classmethod
    def export_to_markdown(cls, session: dict) -> str:
        """匯出為 .md 檔案內容"""
        return cls.generate_architecture_doc(
            session.get("sections_content", {}),
            session.get("game_concept", {}),
            session.get("selected_adrs", [])
        )
