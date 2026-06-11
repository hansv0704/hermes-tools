"""
art_bible_skill.py — Phase 3.5: /art-bible
移植自 CCGS art-bible SKILL.md

美術風格聖經：9 段落完整視覺規範
色盤 / 字體 / UI 風格 / 角色 / 環境 / VFX / 音訊氛圍 / 技術規格 / 參考
"""

import json
from datetime import datetime
from typing import Any


class ArtBibleSkill:
    """美術聖經 — 9 段落視覺規範"""

    name = "art_bible"

    SECTIONS = [
        {
            "id": "overview",
            "name": "1. 視覺風格總覽",
            "prompt": """請描述遊戲的整體視覺風格與藝術方向：
- 風格關鍵詞（如：像素風、low-poly、賽博龐克、手繪水彩...）
- 視覺參考作品（遊戲/電影/動畫/畫作）
- 想要傳達給玩家的情感與氛圍
- 美術風格的獨特賣點（為什麼玩家看到截圖會想玩）""",
        },
        {
            "id": "color_palette",
            "name": "2. 色盤與色彩策略",
            "prompt": """定義遊戲的色盤：
- 主色調（Primary）：HEX 色碼 + 用途
- 輔色調（Secondary）：HEX 色碼 + 用途
- 強調色（Accent）：HEX 色碼 + 用途
- 背景/中性色（Neutral）：HEX 色碼 + 用途
- UI 專用色
- 情緒色板（快樂/悲傷/緊張場景的色彩變化）
- 色彩無障礙考量""",
        },
        {
            "id": "typography",
            "name": "3. 字體與排版",
            "prompt": """定義遊戲的字體系統：
- 主要 UI 字體（名稱 + 用途）
- 對話/敘述字體
- 標題/logo 字體
- 字體大小階層（H1/H2/H3/Body/Caption）
- 中文字體回退方案
- 行距與字距設定
- 不同解析度下的字體縮放策略""",
        },
        {
            "id": "ui_style",
            "name": "4. UI 風格與元件",
            "prompt": """定義 UI 的視覺風格：
- UI 整體風格（簡約/科幻/奇幻/復古...）
- 按鈕風格（形狀/顏色/hover/點擊狀態）
- 面板與對話框風格（邊框/背景/陰影）
- 圖示風格（線條粗細/填滿/顏色）
- 進度條/血量條/數值顯示風格
- 粒子與微互動效果
- 動畫曲線（easing）偏好""",
        },
        {
            "id": "character_design",
            "name": "5. 角色與生物設計",
            "prompt": """定義角色美術方向：
- 角色風格（寫實/卡通/Q版/chibi...）
- 比例與身形參考（頭身比/體型範圍）
- 主角設計方向（外觀關鍵特徵/色系/輪廓）
- NPC 設計方向（如何與主角區分）
- 敵人/生物設計方向
- 表情系統需求
- 服裝/裝備設計風格""",
        },
        {
            "id": "environment",
            "name": "6. 環境與場景設計",
            "prompt": """定義環境美術方向：
- 場景風格（寫實/風格化/抽象...）
- 關卡色調規劃（各關卡/區域的主色調）
- 地形與植被風格
- 建築風格（時代/文化參考）
- 光影方向（Day/Night cycle? 動態光源?）
- 遠景與天空盒風格
- 場景轉換的視覺語言""",
        },
        {
            "id": "vfx",
            "name": "7. 特效與視覺回饋",
            "prompt": """定義 VFX 風格：
- 粒子風格（寫實/卡通/像素...）
- 打擊感特效（命中閃光/震動/速度線）
- 魔法/技能特效風格
- 爆炸/煙霧/火焰風格
- UI 回饋特效（取得道具/升級/成就）
- 轉場特效
- 後製效果（Bloom/色調映射/動態模糊/暈影）""",
        },
        {
            "id": "audio_visual",
            "name": "8. 音訊與視覺的關聯",
            "prompt": """定義音訊如何與視覺搭配：
- 整體音訊氛圍方向
- 視覺事件對應的音效風格
- UI 音效風格（click/hover/confirm/cancel）
- 環境音與場景的對應
- 音樂風格與場景情緒的對應
- 音量分層與動態混音需求""",
        },
        {
            "id": "technical",
            "name": "9. 技術規格",
            "prompt": """定義美術技術規格：
- 目標解析度（如 1920x1080 / 4K）
- 紋理解析度上限
- 模型面數限制（角色 / 道具 / 場景）
- 紋理格式與壓縮方式
- 檔案命名規範
- PBR 或手繪材質工作流
- 匯入設定標準（Godot Import Settings）
- LOD 層級規劃
- 碰撞體與視覺模型的關係""",
        },
    ]

    @classmethod
    def init_session(cls, project_id: str, game_concept: dict = None) -> dict:
        """初始化 Art Bible session"""
        return {
            "project_id": project_id,
            "game_concept": game_concept or {},
            "phase": "init",
            "current_section": 0,
            "sections_content": {},
            "completed_sections": [],
        }

    @classmethod
    def get_section(cls, index: int) -> dict:
        """取得指定段落定義"""
        if 0 <= index < len(cls.SECTIONS):
            return cls.SECTIONS[index]
        return None

    @classmethod
    def set_section_content(cls, session: dict, section_index: int,
                            content: str) -> dict:
        """設定段落內容"""
        section = cls.get_section(section_index)
        if section:
            session["sections_content"][section["id"]] = content
            if section["id"] not in session["completed_sections"]:
                session["completed_sections"].append(section["id"])
        return session

    @classmethod
    def get_progress(cls, session: dict) -> dict:
        """取得進度"""
        completed = len(session.get("completed_sections", []))
        return {
            "total_sections": len(cls.SECTIONS),
            "completed": completed,
            "remaining": len(cls.SECTIONS) - completed,
            "percentage": round(completed / len(cls.SECTIONS) * 100),
            "next_section": completed if completed < len(cls.SECTIONS) else None,
            "next_section_name": cls.SECTIONS[completed]["name"] if completed < len(cls.SECTIONS) else "全部完成",
        }

    @classmethod
    def generate_art_bible(cls, session: dict) -> str:
        """生成完整 Art Bible Markdown"""
        game = session.get("game_concept", {})
        sections = session.get("sections_content", {})

        doc = f"""# 🎨 美術風格聖經：{game.get('title', '未命名')}

> 生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}
> 版本：v1.0
> 狀態：Draft

---

## 目錄

"""
        for s in cls.SECTIONS:
            status = "✅" if s["id"] in sections else "⏳"
            doc += f"- {status} [{s['name']}](#{s['id']})\n"

        doc += "\n---\n\n"

        for s in cls.SECTIONS:
            content = sections.get(s["id"], "*此段落尚未填寫*")
            doc += f"## {s['name']}\n\n{content}\n\n---\n\n"

        doc += f"""
## 📊 完成度

| 段落 | 狀態 |
|:--|:--|
"""
        for s in cls.SECTIONS:
            status = "✅ 完成" if s["id"] in sections else "⏳ 待填寫"
            doc += f"| {s['name']} | {status} |\n"

        doc += f"""

---

*此文件由 Alice Game Studio Art Bible Engine 生成*
"""
        return doc

    @classmethod
    def validate_bible(cls, session: dict) -> dict:
        """驗證 Art Bible 完整性"""
        sections = session.get("sections_content", {})
        missing = [s["id"] for s in cls.SECTIONS if s["id"] not in sections]

        # 檢查色盤是否有 HEX 色碼
        color_section = sections.get("color_palette", "")
        has_hex = "#" in color_section

        # 檢查技術規格是否有解析度
        tech_section = sections.get("technical", "")
        has_resolution = any(
            d in tech_section for d in ["1920", "1080", "4K", "720", "解析度"]
        )

        return {
            "complete": len(missing) == 0,
            "total_sections": len(cls.SECTIONS),
            "completed": len(sections),
            "missing_sections": missing,
            "has_color_palette": has_hex,
            "has_resolution_spec": has_resolution,
        }
