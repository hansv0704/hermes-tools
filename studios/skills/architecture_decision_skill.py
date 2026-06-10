"""
architecture_decision_skill.py — Phase 3.2: /architecture-decision
移植自 CCGS architecture-decision SKILL.md

單一 ADR (Architecture Decision Record) 寫作工具
支援 Foundation / Core / Extension 三層
"""

import json
import re
from datetime import datetime
from typing import Any


class ArchitectureDecisionSkill:
    """ADR 寫作器"""

    name = "architecture_decision"

    # ── ADR 模板 ────────────────────────────────────────────────
    ADR_TEMPLATE = """# {adr_id}: {title}

## 中繼資料
| 欄位 | 值 |
|:--|:--|
| **ADR ID** | {adr_id} |
| **標題** | {title} |
| **類別** | {category} |
| **狀態** | {status} |
| **作者** | Alice Game Studio |
| **日期** | {date} |
| **版本** | 1.0 |

---

## 1. 背景與問題陳述

{context}

## 2. 決策驅動因素

{drivers}

## 3. 選項評估

### 選項 A：{option_a_name}
- **優點**：{option_a_pros}
- **缺點**：{option_a_cons}
- **實作難度**：{option_a_effort}
- **長期維護**：{option_a_maintenance}

### 選項 B：{option_b_name}
- **優點**：{option_b_pros}
- **缺點**：{option_b_cons}
- **實作難度**：{option_b_effort}
- **長期維護**：{option_b_maintenance}

### 選項 C：{option_c_name}（可選）
- **優點**：{option_c_pros}
- **缺點**：{option_c_cons}
- **實作難度**：{option_c_effort}
- **長期維護**：{option_c_maintenance}

## 4. 決策

**選定方案：{decision}**

理由：
{decision_rationale}

## 5. 影響與後果

### 正面影響
{positive_impacts}

### 負面影響
{negative_impacts}

### 緩解策略
{mitigation}

## 6. 相關 ADR

{related_adrs}

## 7. 參考資料

{references}

---

*此 ADR 由 Alice Game Studio 於 {date} 生成*
"""

    # ── 預定義 ADR 引導問題 ───────────────────────────────────
    ADR_GUIDES = {
        "ADR-001": {
            "context_hint": "選擇遊戲引擎是專案最基礎的技術決策。需要考慮：目標平台支援、團隊熟悉度、生態系統成熟度、授權費用、效能目標。",
            "option_a_name": "Godot 4.x",
            "option_b_name": "Unity 6",
            "option_c_name": "Unreal Engine 5",
            "drivers": "1. 目標平台覆蓋率\n2. 團隊技術棧\n3. 2D/3D 需求比例\n4. 開源授權需求\n5. 社群與文件品質",
        },
        "ADR-002": {
            "context_hint": "選擇主要開發語言與腳本策略，影響開發效率、效能、以及團隊組建。",
            "option_a_name": "GDScript（Godot 原生）",
            "option_b_name": "C#（.NET）",
            "option_c_name": "C++（GDExtension）",
            "drivers": "1. 團隊語言熟悉度\n2. 效能需求\n3. 型別安全需求\n4. 生態系統整合",
        },
        "ADR-004": {
            "context_hint": "目錄結構與命名規範是團隊協作的基礎，必須在專案開始時確立。",
            "option_a_name": "依功能分層（Feature-based）",
            "option_b_name": "依資源類型分層（Asset-type-based）",
            "option_c_name": "混合模式",
            "drivers": "1. 團隊規模\n2. 資產重用需求\n3. 模組獨立性\n4. 新人上手速度",
        },
        "ADR-010": {
            "context_hint": "場景管理與加載策略直接影響玩家體驗（載入時間、轉場流暢度）。",
            "option_a_name": "單一場景 + 動態加載（Additive Loading）",
            "option_b_name": "多場景 + 同步切換",
            "option_c_name": "多場景 + 非同步載入畫面",
            "drivers": "1. 遊戲類型（開放世界 vs 關卡制）\n2. 場景大小\n3. 記憶體限制\n4. 轉場體驗要求",
        },
        "ADR-011": {
            "context_hint": "遊戲狀態機架構管理遊戲的核心邏輯流程（選單、遊玩、暫停、結束）。",
            "option_a_name": "有限狀態機（FSM）",
            "option_b_name": "階層式狀態機（HFSM）",
            "option_c_name": "自訂狀態管理器 + 事件驅動",
            "drivers": "1. 狀態數量\n2. 狀態轉換複雜度\n3. 存檔系統整合\n4. 可擴展性",
        },
        "ADR-025": {
            "context_hint": "效能預算決定遊戲能在哪些硬體上流暢運行，影響美術風格與技術選型。",
            "option_a_name": "高階硬體優先（30 / 60 FPS）",
            "option_b_name": "廣泛相容（中低階硬體 30 FPS）",
            "option_c_name": "行動裝置優先（30 FPS）",
            "drivers": "1. 目標平台\n2. 目標玩家群\n3. 視覺風格\n4. 發行策略",
        },
    }

    @classmethod
    def init_session(cls, project_id: str, adr_id: str,
                     adr_info: dict = None) -> dict:
        """初始化 ADR 寫作 session"""
        guide = cls.ADR_GUIDES.get(adr_id, {})

        return {
            "project_id": project_id,
            "adr_id": adr_id,
            "adr_info": adr_info or {},
            "phase": "context",
            "fields": {
                "adr_id": adr_id,
                "title": (adr_info or {}).get("title", adr_id),
                "category": (adr_info or {}).get("category", "Core"),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "status": "Proposed",
                "context": "",
                "drivers": guide.get("drivers", ""),
                "option_a_name": guide.get("option_a_name", "方案 A"),
                "option_a_pros": "",
                "option_a_cons": "",
                "option_a_effort": "",
                "option_a_maintenance": "",
                "option_b_name": guide.get("option_b_name", "方案 B"),
                "option_b_pros": "",
                "option_b_cons": "",
                "option_b_effort": "",
                "option_b_maintenance": "",
                "option_c_name": guide.get("option_c_name", "方案 C"),
                "option_c_pros": "",
                "option_c_cons": "",
                "option_c_effort": "",
                "option_c_maintenance": "",
                "decision": "",
                "decision_rationale": "",
                "positive_impacts": "",
                "negative_impacts": "",
                "mitigation": "",
                "related_adrs": "",
                "references": "",
            },
            "current_field": None,
            "guided_questions": cls._get_guided_questions(adr_id, guide),
        }

    @classmethod
    def _get_guided_questions(cls, adr_id: str, guide: dict) -> list:
        """根據 ADR 類型取得引導問題"""
        base_questions = [
            {"field": "context", "prompt": "請描述此架構決策的背景與要解決的問題。",
             "hint": guide.get("context_hint", "")},
            {"field": "drivers", "prompt": "列出驅動此決策的關鍵因素：",
             "hint": guide.get("drivers", "")},
            {"field": "option_a_pros", "prompt": f"選項 A（{guide.get('option_a_name', '方案 A')}）的優點：",
             "hint": ""},
            {"field": "option_a_cons", "prompt": "選項 A 的缺點：", "hint": ""},
            {"field": "option_a_effort", "prompt": "選項 A 的實作難度（低/中/高）：", "hint": ""},
            {"field": "option_a_maintenance", "prompt": "選項 A 的長期維護評估：", "hint": ""},
            {"field": "option_b_pros", "prompt": f"選項 B（{guide.get('option_b_name', '方案 B')}）的優點：",
             "hint": ""},
            {"field": "option_b_cons", "prompt": "選項 B 的缺點：", "hint": ""},
            {"field": "option_b_effort", "prompt": "選項 B 的實作難度（低/中/高）：", "hint": ""},
            {"field": "option_b_maintenance", "prompt": "選項 B 的長期維護評估：", "hint": ""},
            {"field": "decision", "prompt": "最終決策：選擇哪個方案？", "hint": ""},
            {"field": "decision_rationale", "prompt": "選擇理由（基於以上分析）：", "hint": ""},
            {"field": "positive_impacts", "prompt": "此決策的正面影響：", "hint": ""},
            {"field": "negative_impacts", "prompt": "此決策的負面影響：", "hint": ""},
            {"field": "mitigation", "prompt": "負面影響的緩解策略：", "hint": ""},
            {"field": "related_adrs", "prompt": "相關 ADR（如 ADR-001, ADR-002）：", "hint": ""},
            {"field": "references", "prompt": "參考資料（連結、文件等）：", "hint": ""},
        ]
        return base_questions

    @classmethod
    def set_field(cls, session: dict, field: str, value: str) -> dict:
        """設定欄位值"""
        session["fields"][field] = value
        session["current_field"] = field
        return session

    @classmethod
    def get_next_question(cls, session: dict) -> dict:
        """取得下一個引導問題"""
        questions = session.get("guided_questions", [])
        for q in questions:
            if not session["fields"].get(q["field"]):
                session["current_field"] = q["field"]
                return q
        return None  # 全部完成

    @classmethod
    def validate_adr(cls, session: dict) -> dict:
        """驗證 ADR 完整性"""
        fields = session.get("fields", {})
        required = ["context", "decision", "decision_rationale"]
        missing = [r for r in required if not fields.get(r)]

        optional = ["option_a_pros", "option_a_cons", "option_b_pros", "option_b_cons"]
        unfilled_optional = [o for o in optional if not fields.get(o)]

        return {
            "valid": len(missing) == 0,
            "missing_required": missing,
            "unfilled_optional": unfilled_optional,
            "total_fields": len(fields),
            "filled_fields": sum(1 for v in fields.values() if v),
        }

    @classmethod
    def render_adr(cls, session: dict) -> str:
        """渲染完整 ADR Markdown"""
        return cls.ADR_TEMPLATE.format(**session.get("fields", {}))
