"""
create_control_manifest_skill.py — Phase 3.4: /create-control-manifest
移植自 CCGS create-control-manifest SKILL.md

從 ADR 與架構文件產生程式設計師規則表 (Control Manifest)
這是給程式設計師的"必須遵守的規則清單"
"""

import json
import re
from datetime import datetime
from typing import Any


class CreateControlManifestSkill:
    """Control Manifest 生成器 — 程式設計師規則表"""

    name = "create_control_manifest"

    # ── Manifest 類別 ──────────────────────────────────────────
    MANIFEST_CATEGORIES = [
        {
            "id": "naming",
            "name": "命名規範",
            "icon": "🏷️",
            "description": "所有檔案、類別、變數、資源的命名規則",
            "default_rules": [
                "場景檔案：snake_case（如 player_hub.tscn）",
                "腳本檔案：snake_case（如 player_controller.gd）",
                "類別名稱：PascalCase（如 PlayerController）",
                "常數：UPPER_SNAKE_CASE（如 MAX_HEALTH）",
                "資源檔案：小寫 + 底線（如 icon_sword.png）",
                "材質與 Shader：mat_ 或 shd_ 前綴",
                "不允許使用中文命名任何檔案或變數",
                "不允許使用特殊字元或空格",
            ],
        },
        {
            "id": "structure",
            "name": "目錄結構",
            "icon": "📁",
            "description": "專案目錄組織規則",
            "default_rules": [
                "所有腳本放在 src/ 下對應模組目錄",
                "所有場景放在 scenes/ 下",
                "所有美術資源放在 assets/ 下對應子目錄",
                "測試放在 tests/ 下，結構鏡像 src/",
                "第三方資源放在 addons/ 下",
                "禁止將資源直接放在根目錄",
            ],
        },
        {
            "id": "code_style",
            "name": "程式碼風格",
            "icon": "💻",
            "description": "程式碼撰寫風格與慣例",
            "default_rules": [
                "使用 Tab 縮排（Godot 預設）",
                "每行不超過 120 字元",
                "每個函式不超過 100 行（特殊情況除外）",
                "必須使用型別提示（Type Hints in GDScript）",
                "公開方法必須有 docstring",
                "使用信號（signal）而非直接呼叫跨節點方法",
                "禁止使用 magic number，必須定義為常數",
                "私有方法以底線開頭（_method_name）",
            ],
        },
        {
            "id": "architecture",
            "name": "架構規則",
            "icon": "🏗️",
            "description": "架構層級的限制與規範",
            "default_rules": [
                "禁止循環依賴（模組 A → B → A）",
                "Foundation 層不得依賴 Core/Extension 層",
                "Core 層不得依賴 Extension 層",
                "所有跨模組通訊必須透過 EventBus",
                "場景之間不得直接存取彼此節點",
                "資料存取統一透過 Repository 模式",
                "UI 邏輯與遊戲邏輯分離",
            ],
        },
        {
            "id": "performance",
            "name": "效能規則",
            "icon": "⚡",
            "description": "效能相關的硬性限制",
            "default_rules": [
                "Draw call 上限：依平台設定（見 ADR-025）",
                "禁止在 _process() 中執行 heavy 操作",
                "資源預加載使用 preload()，非必要不使用 load()",
                "所有紋理必須為 2 的冪次方",
                "音訊檔案：短音效使用 WAV，背景音樂使用 OGG",
                "粒子數量上限：單一場景不超過 500",
                "必須使用 Object Pooling 管理頻繁生成/銷毀物件",
            ],
        },
        {
            "id": "testing",
            "name": "測試規則",
            "icon": "🧪",
            "description": "測試相關的強制要求",
            "default_rules": [
                "每個核心系統至少有一個整合測試",
                "新功能必須包含測試才可合併",
                "測試檔案命名：test_<module_name>.gd",
                "使用 GUT（Godot Unit Test）框架",
                "測試覆蓋率目標：核心系統 > 70%",
            ],
        },
        {
            "id": "version_control",
            "name": "版本控制",
            "icon": "🔀",
            "description": "Git 與版本控制規則",
            "default_rules": [
                "使用 Git Flow 分支策略",
                "Commit message 格式：type(scope): description",
                "類型：feat / fix / refactor / docs / test / chore",
                "所有 .import 檔案必須納入版本控制",
                "禁止提交二進位大型資產（使用 Git LFS）",
                "合併到 main 前必須通過 CI",
            ],
        },
        {
            "id": "docs",
            "name": "文件規則",
            "icon": "📝",
            "description": "文件產出與維護規範",
            "default_rules": [
                "每個模組必須有 README.md",
                "ADR 必須在實作前完成",
                "API 變更必須更新對應文件",
                "Changelog 在每個版本發布時更新",
                "程式碼註解使用繁體中文",
            ],
        },
    ]

    @classmethod
    def init_session(cls, project_id: str, architecture_doc: str = "",
                     adrs: list = None) -> dict:
        """初始化 Control Manifest session"""
        categories = []
        for cat in cls.MANIFEST_CATEGORIES:
            cat_copy = dict(cat)
            cat_copy["custom_rules"] = []
            cat_copy["enabled"] = True
            categories.append(cat_copy)

        return {
            "project_id": project_id,
            "architecture_doc": architecture_doc,
            "adrs": adrs or [],
            "categories": categories,
            "phase": "init",
            "current_category": 0,
        }

    @classmethod
    def get_category(cls, session: dict, index: int) -> dict:
        """取得指定類別"""
        categories = session.get("categories", [])
        if 0 <= index < len(categories):
            return categories[index]
        return None

    @classmethod
    def add_custom_rule(cls, session: dict, category_index: int,
                        rule: str) -> dict:
        """新增自訂規則"""
        categories = session.get("categories", [])
        if 0 <= category_index < len(categories):
            categories[category_index]["custom_rules"].append(rule)
        return session

    @classmethod
    def remove_rule(cls, session: dict, category_index: int,
                    rule_index: int, is_custom: bool = False) -> dict:
        """移除規則"""
        categories = session.get("categories", [])
        if 0 <= category_index < len(categories):
            if is_custom:
                rules = categories[category_index]["custom_rules"]
            else:
                rules = categories[category_index]["default_rules"]
            if 0 <= rule_index < len(rules):
                rules.pop(rule_index)
        return session

    @classmethod
    def toggle_category(cls, session: dict, category_index: int) -> dict:
        """啟用/停用類別"""
        categories = session.get("categories", [])
        if 0 <= category_index < len(categories):
            categories[category_index]["enabled"] = \
                not categories[category_index]["enabled"]
        return session

    @classmethod
    def generate_manifest(cls, session: dict) -> str:
        """生成完整 Control Manifest Markdown"""
        categories = session.get("categories", [])

        doc = f"""# Control Manifest — 程式設計師規則表

> 生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}
> 專案：{session.get('project_id', 'Unknown')}
> 此文件為程式碼審查與 CI 檢查的規則來源

---

## 📋 規則總覽

| 類別 | 預設規則數 | 自訂規則數 | 狀態 |
|:--|:--|:--|:--|
"""
        for cat in categories:
            status = "✅ 啟用" if cat.get("enabled", True) else "❌ 停用"
            doc += f"| {cat['icon']} {cat['name']} | {len(cat['default_rules'])} | {len(cat['custom_rules'])} | {status} |\n"

        doc += "\n---\n\n"

        for i, cat in enumerate(categories):
            if not cat.get("enabled", True):
                continue
            doc += f"## {cat['icon']} {cat['name']}\n\n"
            doc += f"> {cat['description']}\n\n"

            doc += "### 預設規則\n\n"
            for j, rule in enumerate(cat["default_rules"], 1):
                doc += f"{j}. {rule}\n"

            if cat["custom_rules"]:
                doc += "\n### 自訂規則\n\n"
                for j, rule in enumerate(cat["custom_rules"], 1):
                    doc += f"{j}. {rule}\n"

            doc += "\n---\n\n"

        doc += f"""
## 📊 統計

| 指標 | 數值 |
|:--|:--|
| 總類別數 | {len(categories)} |
| 啟用類別數 | {sum(1 for c in categories if c.get('enabled', True))} |
| 總規則數 | {sum(len(c['default_rules']) + len(c['custom_rules']) for c in categories)} |
| 自訂規則數 | {sum(len(c['custom_rules']) for c in categories)} |

---

*此文件由 Alice Game Studio Control Manifest Engine 生成*
*每次架構變更後應重新生成*
"""
        return doc

    @classmethod
    def validate_against_adrs(cls, session: dict) -> dict:
        """驗證 Manifest 與 ADR 的一致性"""
        adrs = session.get("adrs", [])
        categories = session.get("categories", [])
        all_rules = []
        for cat in categories:
            all_rules.extend(cat.get("default_rules", []))
            all_rules.extend(cat.get("custom_rules", []))

        issues = []
        # 檢查是否有 ADR 未對應到任何規則
        for adr in adrs:
            adr_keywords = adr.get("title", "").lower().split()
            matched = False
            for rule in all_rules:
                if any(kw in rule.lower() for kw in adr_keywords if len(kw) > 2):
                    matched = True
                    break
            if not matched:
                issues.append({
                    "adr_id": adr.get("id"),
                    "title": adr.get("title"),
                    "issue": "此 ADR 無對應的 Control Manifest 規則",
                })

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "total_adrs": len(adrs),
            "matched_adrs": len(adrs) - len(issues),
        }
