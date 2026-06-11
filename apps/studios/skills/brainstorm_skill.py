"""
brainstorm_skill.py — Alice Game Studio
移植自 CCGS brainstorm/SKILL.md (6 Phase 完整創意發想)

Phase 1: Creative Discovery (情感錨點 + 品味輪廓 + 限制)
Phase 2: Concept Generation (3 技法: Verb-First / Mashup / MDA-Backward)
Phase 3: Core Loop Design (30秒/5分/會話/進度)
Phase 4: Pillars & Boundaries (3-5 柱 + Anti-pillars)
Phase 5: Player Type Validation (Bartle + SDT)
Phase 6: Scope & Feasibility (MVP + 風險 + 範圍層級)
"""

import uuid
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any


# ─── 預設概念庫 (Phase 2 模板匹配用，v2 改為 LLM 生成) ───

CONCEPT_TEMPLATES = {
    "action": [
        {
            "title": "Chrono Break",
            "pitch": "A roguelike where time only moves when you do — plan every step in frozen moments, then watch chaos unfold.",
            "verb": "Plan & Execute",
            "fantasy": "Tactical mastery over time itself",
            "hook": "Like Superhot meets Hades — AND ALSO every enemy has their own time-manipulation ability.",
            "mda": "Challenge",
            "scope": "Medium",
            "why": "Turn-based tactics meets real-time spectacle = viral clip potential.",
            "risk": "Can time-freeze planning feel tedious rather than empowering?"
        },
        {
            "title": "Rift Breakers",
            "pitch": "A co-op survival action game where you defend reality from dimensional fractures — build, fight, and seal rifts together.",
            "verb": "Defend & Seal",
            "fantasy": "Last line of defense against cosmic entropy",
            "hook": "Like Deep Rock Galactic meets Pacific Rim — AND ALSO the terrain itself is your enemy.",
            "mda": "Fellowship",
            "scope": "Large",
            "why": "Co-op PvE is the fastest-growing segment; dimensional theme = infinite enemy variety.",
            "risk": "Scope: co-op netcode + procedural terrain = 2x dev time."
        },
        {
            "title": "Neon Drift",
            "pitch": "A high-speed cyberpunk parkour racer where you chain wall-runs, slides, and grapples through a vertical city.",
            "verb": "Flow & Race",
            "fantasy": "Untouchable speed in a living city",
            "hook": "Like Mirror's Edge meets Trackmania — AND ALSO the city changes layout every run.",
            "mda": "Sensation",
            "scope": "Medium",
            "why": "Speedrunning community + cyberpunk aesthetic = built-in audience.",
            "risk": "Procedural city generation must not break flow-state movement."
        }
    ],
    "rpg": [
        {
            "title": "Echoes of the Fallen",
            "pitch": "A narrative RPG where you absorb the memories of the dead — every skill you learn comes with a story, and a burden.",
            "verb": "Remember & Wield",
            "fantasy": "Carrying lost stories and making them matter",
            "hook": "Like Disco Elysium meets Dark Souls — AND ALSO every ability has an emotional cost.",
            "mda": "Narrative",
            "scope": "Large",
            "why": "Narrative-roguelike hybrid is underexplored; emotional weight = word-of-mouth.",
            "risk": "Writing quality must be exceptional — one weak story breaks the spell."
        },
        {
            "title": "Starforged",
            "pitch": "A space opera RPG where you're not the hero — you're the blacksmith who forges their weapons, and your choices shape the galaxy.",
            "verb": "Craft & Influence",
            "fantasy": "Shaping legends from behind the forge",
            "hook": "Like Stardew Valley meets Mass Effect — AND ALSO the heroes succeed or fail based on what you make.",
            "mda": "Expression",
            "scope": "Medium",
            "why": "Crafting games have massive retention; indirect storytelling = unique angle.",
            "risk": "Players must care about heroes they never directly control."
        },
        {
            "title": "Warden's Oath",
            "pitch": "A tactical RPG where you're the prison warden of a dungeon that holds ancient evils — manage inmates, prevent breakouts, and uncover why they were sealed.",
            "verb": "Contain & Investigate",
            "fantasy": "Holding the line against unspeakable forces",
            "hook": "Like RimWorld meets Persona — AND ALSO every inmate has a social link system.",
            "mda": "Discovery",
            "scope": "Medium",
            "why": "Prison management + RPG = fresh take; social links = emotional investment.",
            "risk": "Balancing management sim depth with RPG narrative pacing."
        }
    ],
    "strategy": [
        {
            "title": "Tide of Iron",
            "pitch": "A real-time tactics game where you command a mercenary company in a dieselpunk world — every unit has a personality, and every death is permanent.",
            "verb": "Command & Mourn",
            "fantasy": "Leading soldiers who feel like people",
            "hook": "Like XCOM meets Iron Harvest — AND ALSO your soldiers write letters home that you can read.",
            "mda": "Challenge",
            "scope": "Large",
            "why": "Permadeath + personality = stories players tell for years.",
            "risk": "Asset generation for unique soldier appearances is expensive."
        },
        {
            "title": "Spore Wars",
            "pitch": "A 4X strategy game where you play as a fungal hive mind — grow, consume, and adapt, but every expansion risks mutation.",
            "verb": "Spread & Adapt",
            "fantasy": "Inexorable, beautiful decay",
            "hook": "Like Civilization meets Carrion — AND ALSO your empire can literally mutate in unexpected ways.",
            "mda": "Discovery",
            "scope": "Small",
            "why": "Fungal theme = unique visual identity; mutation = emergent gameplay.",
            "risk": "Mutation system could feel random rather than strategic."
        },
        {
            "title": "Council of Shadows",
            "pitch": "A political strategy game where you're a shadow council manipulating a fantasy kingdom — no direct control, only whispers, bribes, and assassinations.",
            "verb": "Manipulate & Scheme",
            "fantasy": "The power behind the throne",
            "hook": "Like Crusader Kings meets Among Us — AND ALSO you never know which council members are loyal.",
            "mda": "Fellowship",
            "scope": "Medium",
            "why": "Social deduction + grand strategy = streaming gold.",
            "risk": "AI must convincingly simulate political actors with hidden agendas."
        }
    ],
    "sim": [
        {
            "title": "Hollow Harvest",
            "pitch": "A cozy farming sim set in a world where the seasons are broken — grow crops that fix the weather, befriend spirits, and restore the calendar.",
            "verb": "Grow & Restore",
            "fantasy": "Healing a world one garden at a time",
            "hook": "Like Stardew Valley meets Spiritfarer — AND ALSO your crops literally change the biome.",
            "mda": "Expression",
            "scope": "Medium",
            "why": "Cozy games are booming; environmental restoration = meaningful progression.",
            "risk": "Crop-biome interaction system is technically complex."
        },
        {
            "title": "Workshop Wonders",
            "pitch": "A tinkering sim where you run a magical workshop — build contraptions from monster parts, fulfill customer orders, and accidentally create chaos.",
            "verb": "Build & Fulfill",
            "fantasy": "Mad genius with a heart of gold",
            "hook": "Like Factorio meets Recettear — AND ALSO every contraption has unintended side effects.",
            "mda": "Expression",
            "scope": "Small",
            "why": "Crafting + shop management = proven loop; chaos = humor.",
            "risk": "Physics simulation for contraptions may be janky in Godot."
        },
        {
            "title": "Aquapolis",
            "pitch": "An underwater city builder where you construct a thriving civilization on the ocean floor — manage oxygen, pressure, and the creatures of the deep.",
            "verb": "Build & Survive",
            "fantasy": "Taming the abyss",
            "hook": "Like Cities: Skylines meets Subnautica — AND ALSO the ocean has a day/night ecosystem that reacts to your city.",
            "mda": "Discovery",
            "scope": "Large",
            "why": "Underwater = untapped city builder aesthetic; ecosystem = emergent storytelling.",
            "risk": "3D underwater pathfinding and fluid dynamics are technically demanding."
        }
    ],
    "horror": [
        {
            "title": "The Static Between",
            "pitch": "A psychological horror game where you're a radio operator in an Antarctic station — the voices on the other end aren't always human.",
            "verb": "Listen & Survive",
            "fantasy": "The terror of being alone... but not really",
            "hook": "Like Firewatch meets SOMA — AND ALSO you can never trust what you hear.",
            "mda": "Narrative",
            "scope": "Small",
            "why": "Audio-driven horror is underserved; single-room setting = low asset cost.",
            "risk": "Must sustain tension with minimal visual variety."
        },
        {
            "title": "Mirror Mirror",
            "pitch": "A body-swap horror where you and your reflection trade places — every time you look in a mirror, you lose a piece of yourself.",
            "verb": "Swap & Reclaim",
            "fantasy": "Fighting the other you",
            "hook": "Like Inside meets The Prestige — AND ALSO your reflection learns from every swap.",
            "mda": "Sensation",
            "scope": "Small",
            "why": "Mirror mechanic = instant visual hook; learning AI = replayability.",
            "risk": "Mirror-swap mechanic must feel fair, not frustrating."
        },
        {
            "title": "Cordyceps Kingdom",
            "pitch": "A survival horror where you play as the last uninfected in a world overtaken by a fungal hive mind — the fungus doesn't want to kill you, it wants to love you.",
            "verb": "Resist & Escape",
            "fantasy": "Staying human when humanity is optional",
            "hook": "Like The Last of Us meets Annihilation — AND ALSO the infected try to persuade you.",
            "mda": "Fantasy",
            "scope": "Medium",
            "why": "Fungal horror is culturally hot; persuasion angle = fresh take.",
            "risk": "Dialogue-heavy horror must maintain tension during conversations."
        }
    ],
    "puzzle": [
        {
            "title": "Recursive",
            "pitch": "A puzzle game where you solve rooms by recording and layering your own actions — your past selves are your only tools.",
            "verb": "Record & Layer",
            "fantasy": "Outsmarting yourself across timelines",
            "hook": "Like The Talos Principle meets Braid — AND ALSO you can argue with your recordings.",
            "mda": "Challenge",
            "scope": "Small",
            "why": "Time-recording puzzles are proven winners; argument mechanic = humor.",
            "risk": "Puzzle design complexity scales exponentially with layers."
        },
        {
            "title": "Gravity Shift",
            "pitch": "A physics puzzle platformer where you paint gravity onto surfaces — red pulls, blue pushes, and mixing creates chaos.",
            "verb": "Paint & Manipulate",
            "fantasy": "Bending physics to your will",
            "hook": "Like Portal meets Splatoon — AND ALSO gravity paint colors can mix.",
            "mda": "Sensation",
            "scope": "Small",
            "why": "Physics + color = GIF-able moments; small scope = achievable.",
            "risk": "Mixed-gravity physics must be deterministic for fair puzzles."
        },
        {
            "title": "Signal Lost",
            "pitch": "A puzzle game where you reconstruct corrupted data streams by rewinding, splicing, and decoding fragments of a lost transmission.",
            "verb": "Decode & Reconstruct",
            "fantasy": "Archaeologist of the digital age",
            "hook": "Like Return of the Obra Dinn meets Hacknet — AND ALSO every puzzle reveals part of a larger story.",
            "mda": "Discovery",
            "scope": "Small",
            "why": "Data archaeology = compelling fantasy; narrative integration = replay.",
            "risk": "Must tutorialize complex mechanics without breaking immersion."
        }
    ]
}


class BrainstormSession:
    """單一 brainstorm 會話的狀態管理"""

    def __init__(self, session_id: str, genre_hint: str = None):
        self.id = session_id
        self.genre_hint = genre_hint
        self.phase = "discovery"
        self.step = 0
        self.created_at = datetime.now().isoformat()

        # Phase 1 data
        self.emotional_anchors: Dict = {}
        self.taste_profile: Dict = {}
        self.constraints: Dict = {}
        self.creative_brief: str = ""

        # Phase 2 data
        self.concepts: list = []
        self.selected_concept_index: int = -1

        # Phase 3 data
        self.core_loop: Dict = {
            "30s": "", "5m": "", "session": "", "progression": ""
        }
        self.sdt: Dict = {"autonomy": "", "competence": "", "relatedness": ""}

        # Phase 4 data
        self.pillars: list = []
        self.anti_pillars: list = []

        # Phase 5 data
        self.player_type: Dict = {
            "primary": "", "secondary": "", "not_for": "", "market": ""
        }

        # Phase 6 data
        self.platform: str = ""
        self.engine: str = ""
        self.art_pipeline: str = ""
        self.content_scope: str = ""
        self.mvp: str = ""
        self.risks: Dict = {}
        self.scope_tiers: str = ""

        # Meta
        self.review_mode: str = "lean"
        self.visual_direction: str = ""
        self.visual_rule: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "phase": self.phase,
            "step": self.step,
            "genre_hint": self.genre_hint,
            "created_at": self.created_at,
            "creative_brief": self.creative_brief,
            "selected_concept_index": self.selected_concept_index,
            "review_mode": self.review_mode
        }


class BrainstormSkill:
    """
    Alice Game Studio — Brainstorm Skill
    6 Phase 遊戲創意發想引擎，移植自 CCGS brainstorm/SKILL.md
    """

    def __init__(self):
        self.sessions: Dict[str, BrainstormSession] = {}

    # ─── Session Management ───

    def create_session(self, genre_hint: str = None) -> BrainstormSession:
        sid = f"bs_{uuid.uuid4().hex[:8]}"
        session = BrainstormSession(sid, genre_hint)
        self.sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[BrainstormSession]:
        return self.sessions.get(session_id)

    # ─── Phase 1: Creative Discovery ───

    def phase1_start(self, session: BrainstormSession) -> dict:
        """開始 Phase 1 — 情感錨點問題"""
        session.phase = "discovery"
        session.step = 1
        return {
            "phase": "discovery",
            "step": 1,
            "title": "🎨 Phase 1: Creative Discovery",
            "subtitle": "先了解你，再了解遊戲",
            "prompt": "我們先從你開始。告訴我：\n\n**在遊戲中，有沒有某個時刻真正打動了你、讓你熱血沸騰、或讓你完全忘記時間？是什麼創造了那種感覺？**",
            "input_type": "text",
            "field": "emotional_moment"
        }

    def phase1_step2(self, session: BrainstormSession, response: str) -> dict:
        session.emotional_anchors["moment"] = response
        session.step = 2
        return {
            "phase": "discovery",
            "step": 2,
            "prompt": "**有沒有你一直想在遊戲中體驗、但始終沒找到的幻想或能力？**\n\n（例如：操控時間但沒人做得好、想當反派但遊戲不允許、想飛但只有過場動畫...）",
            "input_type": "text",
            "field": "unfulfilled_fantasy"
        }

    def phase1_step3(self, session: BrainstormSession, response: str) -> dict:
        session.emotional_anchors["fantasy"] = response
        session.step = 3
        return {
            "phase": "discovery",
            "step": 3,
            "title": "🎮 品味輪廓",
            "prompt": "**你花最多時間的 3 款遊戲是什麼？是什麼讓你一直回去？**",
            "input_type": "text",
            "field": "top_games"
        }

    def phase1_step4(self, session: BrainstormSession, response: str) -> dict:
        session.taste_profile["top_games"] = response
        session.step = 4
        return {
            "phase": "discovery",
            "step": 4,
            "prompt": "**有你特別喜歡的遊戲類型嗎？有特別不碰的嗎？為什麼？**",
            "input_type": "text",
            "field": "genre_preferences"
        }

    def phase1_step5(self, session: BrainstormSession, response: str) -> dict:
        session.taste_profile["genres"] = response
        session.step = 5
        return {
            "phase": "discovery",
            "step": 5,
            "title": "⚙️ 實際限制",
            "prompt": "**你希望玩家獲得什麼樣的體驗？**",
            "input_type": "choice",
            "field": "experience_type",
            "options": [
                {"id": "challenge", "label": "🏆 挑戰與精通 — 征服困難、證明自己"},
                {"id": "story", "label": "📖 故事與探索 — 沉浸於另一個世界"},
                {"id": "expression", "label": "🎨 表達與創造 — 建造、設計、留下印記"},
                {"id": "relaxation", "label": "🌿 放鬆與心流 — 逃離壓力、純粹享受"}
            ]
        }

    def phase1_step6(self, session: BrainstormSession, response: str) -> dict:
        session.constraints["experience"] = response
        session.step = 6
        return {
            "phase": "discovery",
            "step": 6,
            "prompt": "**你的開發時程有多長？**",
            "input_type": "choice",
            "field": "timeline",
            "options": [
                {"id": "weeks", "label": "數週 — 快速原型、Game Jam 風格"},
                {"id": "months", "label": "數月 — 完整的小型遊戲"},
                {"id": "1-2y", "label": "1-2 年 — 中型專案"},
                {"id": "multi", "label": "多年 — 大型野心之作"}
            ]
        }

    def phase1_step7(self, session: BrainstormSession, response: str) -> dict:
        session.constraints["timeline"] = response
        session.step = 7
        return {
            "phase": "discovery",
            "step": 7,
            "prompt": "**你的開發經驗在哪個階段？**",
            "input_type": "choice",
            "field": "dev_level",
            "options": [
                {"id": "first", "label": "🌱 第一款遊戲"},
                {"id": "shipped", "label": "🚀 曾發布過遊戲"},
                {"id": "pro", "label": "💼 專業開發背景"}
            ]
        }

    def phase1_finalize(self, session: BrainstormSession, response: str) -> dict:
        session.constraints["dev_level"] = response
        session.step = 8

        # 生成 Creative Brief
        brief = self._generate_creative_brief(session)
        session.creative_brief = brief

        return {
            "phase": "discovery",
            "step": 8,
            "title": "📋 Creative Brief",
            "creative_brief": brief,
            "prompt": "這是我根據你的回答彙整的創意摘要。請確認這是否抓住了你的想法：\n\n---\n" + brief + "\n---",
            "input_type": "choice",
            "field": "brief_confirm",
            "options": [
                {"id": "confirm", "label": "✅ 確認，進入概念發想"},
                {"id": "revise", "label": "✏️ 需要修改某個部分"}
            ]
        }

    def _generate_creative_brief(self, session: BrainstormSession) -> str:
        """根據收集的答案生成 Creative Brief"""
        parts = []

        exp = session.constraints.get("experience", "")
        exp_map = {
            "challenge": "挑戰與精通",
            "story": "故事與探索",
            "expression": "表達與創造",
            "relaxation": "放鬆與心流"
        }

        timeline = session.constraints.get("timeline", "")
        tl_map = {"weeks": "數週", "months": "數月", "1-2y": "1-2 年", "multi": "多年"}

        dev = session.constraints.get("dev_level", "")
        dev_map = {"first": "初次開發者", "shipped": "有發布經驗", "pro": "專業背景"}

        parts.append(f"玩家體驗方向：{exp_map.get(exp, exp)}。")
        parts.append(f"開發時程：{tl_map.get(timeline, timeline)}。")
        parts.append(f"開發者狀態：{dev_map.get(dev, dev)}。")

        if session.taste_profile.get("top_games"):
            parts.append(f"參考遊戲：{session.taste_profile['top_games']}。")
        if session.emotional_anchors.get("moment"):
            parts.append(f"感動時刻：{session.emotional_anchors['moment']}")
        if session.emotional_anchors.get("fantasy"):
            parts.append(f"未實現的幻想：{session.emotional_anchors['fantasy']}")

        return "\n".join(parts)

    # ─── Phase 2: Concept Generation ───

    def phase2_start(self, session: BrainstormSession) -> dict:
        """開始 Phase 2 — 概念生成"""
        session.phase = "concept_generation"
        session.step = 1

        # 根據 creative brief 匹配概念
        concepts = self._match_concepts(session)
        session.concepts = concepts

        concept_list = []
        for i, c in enumerate(concepts):
            concept_list.append({
                "index": i,
                "title": c["title"],
                "pitch": c["pitch"],
                "core_verb": c["verb"],
                "core_fantasy": c["fantasy"],
                "unique_hook": c["hook"],
                "mda": c["mda"],
                "scope": c["scope"],
                "why": c["why"],
                "risk": c["risk"]
            })

        return {
            "phase": "concept_generation",
            "step": 1,
            "title": "💡 Phase 2: Concept Generation",
            "subtitle": "基於你的 Creative Brief，這裡有三個不同方向的遊戲概念",
            "concepts": concept_list,
            "prompt": "哪個概念最吸引你？你可以選一個、融合元素、或要求全新的方向。",
            "input_type": "choice",
            "field": "concept_selection",
            "options": [
                {"id": "0", "label": f"概念 1 — {concepts[0]['title']}"},
                {"id": "1", "label": f"概念 2 — {concepts[1]['title']}"},
                {"id": "2", "label": f"概念 3 — {concepts[2]['title']}"},
                {"id": "combine", "label": "🔀 融合不同概念的元素"},
                {"id": "fresh", "label": "🔄 給我全新的方向"}
            ]
        }

    def _match_concepts(self, session: BrainstormSession) -> list:
        """根據 creative brief 和 genre_hint 匹配概念模板"""
        brief = session.creative_brief.lower() if session.creative_brief else ""
        hint = session.genre_hint.lower() if session.genre_hint else ""

        # 嘗試從 brief 和 hint 中判斷類型
        type_scores = {}
        type_keywords = {
            "action": ["動作", "戰鬥", "即時", "刺激", "反應", "熱血", "action", "combat", "fight"],
            "rpg": ["角色扮演", "故事", "成長", "劇情", "rpg", "升級", "裝備", "冒險", "角色"],
            "strategy": ["策略", "戰術", "思考", "規劃", "strategy", "戰棋", "指揮"],
            "sim": ["模擬", "經營", "建造", "農場", "sim", "管理", "創造", "城市"],
            "horror": ["恐怖", "恐懼", "黑暗", "horror", "驚悚", "生存"],
            "puzzle": ["解謎", "拼圖", "邏輯", "puzzle", "謎題", "思考"]
        }

        for t, keywords in type_keywords.items():
            score = 0
            for kw in keywords:
                if kw in brief or kw in hint:
                    score += 1
            type_scores[t] = score

        # 取最高分，如果沒有匹配就隨機選
        best_type = max(type_scores, key=type_scores.get)
        if type_scores[best_type] == 0:
            import random
            best_type = random.choice(list(CONCEPT_TEMPLATES.keys()))

        # 從該類型取 3 個概念（如果不夠就補其他類型）
        concepts = list(CONCEPT_TEMPLATES.get(best_type, []))
        if len(concepts) < 3:
            for t in CONCEPT_TEMPLATES:
                if t != best_type and len(concepts) < 3:
                    concepts.append(CONCEPT_TEMPLATES[t][0])

        return concepts[:3]

    # ─── Phase 3: Core Loop Design ───

    def phase3_start(self, session: BrainstormSession) -> dict:
        session.phase = "core_loop"
        session.step = 1
        concept = session.concepts[session.selected_concept_index] if session.selected_concept_index >= 0 else {"title": "你的遊戲"}

        return {
            "phase": "core_loop",
            "step": 1,
            "title": "🔄 Phase 3: Core Loop Design",
            "subtitle": f"為「{concept.get('title', '你的遊戲')}」設計核心循環",
            "prompt": "**30 秒循環 — 玩家每一刻在做什麼？**\n\n描述玩家最頻繁的操作。例如：移動→瞄準→射擊→撿拾→移動...",
            "input_type": "text",
            "field": "loop_30s"
        }

    def phase3_step2(self, session: BrainstormSession, response: str) -> dict:
        session.core_loop["30s"] = response
        session.step = 2
        return {
            "phase": "core_loop",
            "step": 2,
            "prompt": "**5 分鐘循環 — 短期目標是什麼？**\n\n什麼讓玩家想「再來一局」？完成一個房間？打完一波敵人？解開一個謎題？",
            "input_type": "text",
            "field": "loop_5m"
        }

    def phase3_step3(self, session: BrainstormSession, response: str) -> dict:
        session.core_loop["5m"] = response
        session.step = 3
        return {
            "phase": "core_loop",
            "step": 3,
            "prompt": "**會話循環 (30-120 分鐘) — 完整遊戲會話長什麼樣？**\n\n自然的停止點在哪？玩家關掉遊戲時會想什麼？",
            "input_type": "text",
            "field": "loop_session"
        }

    def phase3_step4(self, session: BrainstormSession, response: str) -> dict:
        session.core_loop["session"] = response
        session.step = 4
        return {
            "phase": "core_loop",
            "step": 4,
            "prompt": "**進度循環 (天/週) — 玩家如何成長？**\n\n力量？知識？選項？故事？長期目標是什麼？遊戲何時算「完成」？",
            "input_type": "text",
            "field": "loop_progression"
        }

    def phase3_step5(self, session: BrainstormSession, response: str) -> dict:
        session.core_loop["progression"] = response
        session.step = 5
        return {
            "phase": "core_loop",
            "step": 5,
            "title": "🧠 玩家動機 (自我決定理論)",
            "prompt": "**自主性 (Autonomy)** — 玩家有多少有意義的選擇？",
            "input_type": "text",
            "field": "sdt_autonomy"
        }

    def phase3_step6(self, session: BrainstormSession, response: str) -> dict:
        session.sdt["autonomy"] = response
        session.step = 6
        return {
            "phase": "core_loop",
            "step": 6,
            "prompt": "**勝任感 (Competence)** — 玩家如何感受自己的技能成長？",
            "input_type": "text",
            "field": "sdt_competence"
        }

    def phase3_step7(self, session: BrainstormSession, response: str) -> dict:
        session.sdt["competence"] = response
        session.step = 7
        return {
            "phase": "core_loop",
            "step": 7,
            "prompt": "**關聯感 (Relatedness)** — 玩家如何感受連結（角色、其他玩家、世界）？",
            "input_type": "text",
            "field": "sdt_relatedness"
        }

    # ─── Phase 4: Pillars & Boundaries ───

    def phase4_start(self, session: BrainstormSession) -> dict:
        session.phase = "pillars"
        session.step = 1
        session.sdt["relatedness"] = session.sdt.get("relatedness", "")
        return {
            "phase": "pillars",
            "step": 1,
            "title": "🏛️ Phase 4: Pillars & Boundaries",
            "subtitle": "定義遊戲的核心支柱 — 這些柱子會在數百個決策中指引方向",
            "prompt": "**定義 3-5 個遊戲支柱。**\n\n每個支柱有一個名稱和一句話定義。好的支柱之間應該有張力 — 如果所有支柱都指向同一方向，它們就不夠強大。\n\n💡 範例（戰神 God of War）：\n- **親密視角**: 攝影機永遠不離開 Kratos\n- **利維坦之斧**: 所有戰鬥圍繞單一武器的多功能性\n- **父子關係**: 每個機制都反映 Atreus 與 Kratos 的關係",
            "input_type": "text",
            "field": "pillars"
        }

    def phase4_step2(self, session: BrainstormSession, response: str) -> dict:
        # 解析支柱
        lines = [l.strip() for l in response.split("\n") if l.strip()]
        pillars = []
        for line in lines:
            if ":" in line or "：" in line:
                separator = ":" if ":" in line else "："
                name, definition = line.split(separator, 1)
                pillars.append({"name": name.strip("- *"), "definition": definition.strip()})
            else:
                pillars.append({"name": line.strip("- *"), "definition": ""})

        session.pillars = pillars[:5]  # 最多 5 個
        session.step = 2

        return {
            "phase": "pillars",
            "step": 2,
            "prompt": "**定義 3+ 個反支柱 (Anti-Pillars) — 這個遊戲「不是」什麼。**\n\n反支柱防止最常見的範圍蔓延：「如果加了 X 不是很酷嗎...」但 X 不在核心視野內。\n\n💡 格式：「我們不會做 [X]，因為這會損害 [支柱]」",
            "input_type": "text",
            "field": "anti_pillars"
        }

    def phase4_step3(self, session: BrainstormSession, response: str) -> dict:
        session.anti_pillars = [l.strip("- *") for l in response.split("\n") if l.strip()]
        session.step = 3

        return {
            "phase": "pillars",
            "step": 3,
            "prompt": "**視覺方向** — 用一句話描述這款遊戲的視覺風格。\n\n例如：「極簡低多邊形 + 霓虹光效」、「手繪水彩 + 黑暗童話」、「像素藝術 + 現代燈光」",
            "input_type": "text",
            "field": "visual_direction"
        }

    # ─── Phase 5: Player Type Validation ───

    def phase5_start(self, session: BrainstormSession) -> dict:
        session.phase = "player_types"
        session.step = 1
        return {
            "phase": "player_types",
            "step": 1,
            "title": "👥 Phase 5: Player Type Validation",
            "prompt": "**誰會「愛上」這個遊戲？** 主要玩家類型是什麼？\n\n- 🏆 Achievers（成就者）：追求完成、收集、100%\n- 🧭 Explorers（探索者）：追求發現、秘密、世界深度\n- 👥 Socializers（社交者）：追求互動、合作、社群\n- ⚔️ Competitors（競爭者）：追求排名、PvP、勝利\n- 🎨 Creators（創造者）：追求建造、設計、表達",
            "input_type": "choice",
            "field": "primary_type",
            "options": [
                {"id": "achievers", "label": "🏆 成就者"},
                {"id": "explorers", "label": "🧭 探索者"},
                {"id": "socializers", "label": "👥 社交者"},
                {"id": "competitors", "label": "⚔️ 競爭者"},
                {"id": "creators", "label": "🎨 創造者"}
            ]
        }

    def phase5_step2(self, session: BrainstormSession, response: str) -> dict:
        session.player_type["primary"] = response
        session.step = 2
        return {
            "phase": "player_types",
            "step": 2,
            "prompt": "**還有誰可能會喜歡？** 次要受眾是什麼？",
            "input_type": "text",
            "field": "secondary_appeal"
        }

    def phase5_step3(self, session: BrainstormSession, response: str) -> dict:
        session.player_type["secondary"] = response
        session.step = 3
        return {
            "phase": "player_types",
            "step": 3,
            "prompt": "**這個遊戲「不是」給誰玩的？** 明確說出誰不會喜歡這遊戲，跟說出誰會喜歡一樣重要。",
            "input_type": "text",
            "field": "not_for"
        }

    def phase5_step4(self, session: BrainstormSession, response: str) -> dict:
        session.player_type["not_for"] = response
        session.step = 4
        return {
            "phase": "player_types",
            "step": 4,
            "prompt": "**市場參考** — 有成功服務類似玩家類型的遊戲嗎？從他們的受眾規模可以學到什麼？",
            "input_type": "text",
            "field": "market_reference"
        }

    # ─── Phase 6: Scope & Feasibility ───

    def phase6_start(self, session: BrainstormSession) -> dict:
        session.phase = "scope"
        session.step = 1
        return {
            "phase": "scope",
            "step": 1,
            "title": "📦 Phase 6: Scope & Feasibility",
            "prompt": "**目標平台是什麼？**",
            "input_type": "choice",
            "field": "platform",
            "options": [
                {"id": "pc", "label": "💻 PC (Steam / Epic)"},
                {"id": "mobile", "label": "📱 手機 (iOS / Android)"},
                {"id": "console", "label": "🎮 主機"},
                {"id": "web", "label": "🌐 網頁 / 瀏覽器"},
                {"id": "multi", "label": "🔄 多平台"}
            ]
        }

    def phase6_step2(self, session: BrainstormSession, response: str) -> dict:
        session.platform = response
        session.step = 2
        return {
            "phase": "scope",
            "step": 2,
            "prompt": "**你已經在使用哪個遊戲引擎？**",
            "input_type": "choice",
            "field": "engine",
            "options": [
                {"id": "godot", "label": "🤖 Godot"},
                {"id": "unity", "label": "🎯 Unity"},
                {"id": "unreal", "label": "🏰 Unreal Engine 5"},
                {"id": "undecided", "label": "🤔 尚未決定 — 幫我判斷"}
            ]
        }

    def phase6_step3(self, session: BrainstormSession, response: str) -> dict:
        session.engine = response
        session.step = 3
        return {
            "phase": "scope",
            "step": 3,
            "prompt": "**MVP 定義** — 測試「核心循環是否好玩」的最小可行產品是什麼？\n\n只包含必要的部分。一句話。",
            "input_type": "text",
            "field": "mvp"
        }

    def phase6_step4(self, session: BrainstormSession, response: str) -> dict:
        session.mvp = response
        session.step = 4
        return {
            "phase": "scope",
            "step": 4,
            "prompt": "**最大的風險是什麼？**\n\n考慮：技術風險（什麼可能無法實現？）、設計風險（什麼可能不好玩？）、市場風險（誰會買？）",
            "input_type": "text",
            "field": "risks"
        }

    def phase6_step5(self, session: BrainstormSession, response: str) -> dict:
        session.risks["raw"] = response
        session.step = 5
        return {
            "phase": "scope",
            "step": 5,
            "prompt": "**範圍層級** — 如果時間不夠，哪些功能可以砍？列出：\n\n- 🥇 必須有 (MVP)\n- 🥈 應該有 (v1.0)\n- 🥉 可以有 (如果時間允許)\n- ❌ 不會有 (明確排除)",
            "input_type": "text",
            "field": "scope_tiers"
        }

    # ─── Finalize: Generate game-concept.md ───

    def finalize(self, session: BrainstormSession) -> dict:
        """生成最終的 game-concept.md 內容"""
        concept = {}
        if session.selected_concept_index >= 0 and session.selected_concept_index < len(session.concepts):
            concept = session.concepts[session.selected_concept_index]

        # 載入模板
        template_path = Path(__file__).parent.parent / "templates" / "game-concept.md"
        if template_path.exists():
            template = template_path.read_text(encoding="utf-8")
        else:
            template = "# {game_title} — Game Concept Document\n\n{content}"

        # 填充數據
        pillars_text = "\n".join([
            f"- **{p.get('name', '')}**: {p.get('definition', '')}"
            for p in session.pillars
        ]) if session.pillars else "(待定義)"

        anti_text = "\n".join([
            f"- {ap}" for ap in session.anti_pillars
        ]) if session.anti_pillars else "(待定義)"

        scope_tiers = session.scope_tiers or "(待定義)"
        risks = session.risks.get("raw", "(待定義)")

        data = {
            "game_title": concept.get("title", "未命名遊戲"),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "session_id": session.id,
            "working_title": concept.get("title", "未命名遊戲"),
            "elevator_pitch": concept.get("pitch", ""),
            "core_verb": concept.get("verb", ""),
            "core_fantasy": concept.get("fantasy", ""),
            "unique_hook": concept.get("hook", ""),
            "genre": session.genre_hint or concept.get("mda", ""),
            "platform": session.platform,
            "engine": session.engine,
            "scope": concept.get("scope", ""),
            "game_pillars": pillars_text,
            "anti_pillars": anti_text,
            "visual_direction": session.visual_direction or "",
            "visual_rule": "",
            "visual_principles": "",
            "color_philosophy": "",
            "loop_30s": session.core_loop.get("30s", ""),
            "loop_5m": session.core_loop.get("5m", ""),
            "loop_session": session.core_loop.get("session", ""),
            "loop_progression": session.core_loop.get("progression", ""),
            "sdt_autonomy": session.sdt.get("autonomy", ""),
            "sdt_competence": session.sdt.get("competence", ""),
            "sdt_relatedness": session.sdt.get("relatedness", ""),
            "primary_type": session.player_type.get("primary", ""),
            "secondary_appeal": session.player_type.get("secondary", ""),
            "not_for": session.player_type.get("not_for", ""),
            "market_reference": session.player_type.get("market", ""),
            "mda_mechanics": "",
            "mda_dynamics": "",
            "mda_aesthetics": concept.get("mda", ""),
            "flow_goals": "",
            "flow_feedback": "",
            "flow_balance": "",
            "flow_immersion": "",
            "mvp": session.mvp,
            "scope_tiers": scope_tiers,
            "risk_tech": risks,
            "risk_design": risks,
            "risk_market": risks,
            "mitigation_tech": "",
            "mitigation_design": "",
            "mitigation_market": "",
            "art_pipeline": "",
            "content_scope": ""
        }

        # 簡單的模板替換
        for key, value in data.items():
            template = template.replace("{" + key + "}", str(value))

        session.phase = "complete"

        return {
            "phase": "complete",
            "title": "✅ Brainstorm 完成！",
            "game_title": concept.get("title", "未命名遊戲"),
            "elevator_pitch": concept.get("pitch", ""),
            "pillars": session.pillars,
            "primary_player_type": session.player_type.get("primary", ""),
            "engine": session.engine,
            "biggest_risk": risks,
            "document": template,
            "next_steps": [
                "1. /setup-engine — 設定引擎與版本參考文件",
                "2. /art-bible — 建立視覺風格規範（在寫 GDD 之前）",
                "3. /map-systems — 拆解概念為獨立系統",
                "4. /design-system — 為每個系統撰寫 GDD",
                "5. /create-architecture — 主架構藍圖",
                "6. /gate-check — 驗證是否準備好進入生產"
            ]
        }

    # ─── Main Router ───

    def handle_init(self, genre_hint: str = None) -> dict:
        """初始化 brainstorm 會話"""
        session = self.create_session(genre_hint)
        return {
            "session_id": session.id,
            **self.phase1_start(session)
        }

    def handle_response(self, session_id: str, field: str, value: str) -> dict:
        """處理使用者的回應，根據當前 phase/step 路由"""
        session = self.get_session(session_id)
        if not session:
            return {"error": "Session not found", "session_id": session_id}

        phase = session.phase
        step = session.step

        try:
            # Phase 1: Creative Discovery
            if phase == "discovery":
                if step == 1:
                    return {"session_id": session_id, **self.phase1_step2(session, value)}
                elif step == 2:
                    return {"session_id": session_id, **self.phase1_step3(session, value)}
                elif step == 3:
                    return {"session_id": session_id, **self.phase1_step4(session, value)}
                elif step == 4:
                    return {"session_id": session_id, **self.phase1_step5(session, value)}
                elif step == 5:
                    return {"session_id": session_id, **self.phase1_step6(session, value)}
                elif step == 6:
                    return {"session_id": session_id, **self.phase1_step7(session, value)}
                elif step == 7:
                    return {"session_id": session_id, **self.phase1_finalize(session, value)}
                elif step == 8:
                    if value == "confirm":
                        return {"session_id": session_id, **self.phase2_start(session)}
                    else:
                        return {"session_id": session_id, **self.phase1_step1(session)}

            # Phase 2: Concept Generation
            elif phase == "concept_generation":
                if value == "combine":
                    return {"session_id": session_id, "phase": "concept_generation", "step": 2,
                            "prompt": "描述你想融合哪些概念的元素：", "input_type": "text", "field": "combine_description"}
                elif value == "fresh":
                    session.genre_hint = None
                    return {"session_id": session_id, **self.phase2_start(session)}
                else:
                    try:
                        idx = int(value)
                        if 0 <= idx < len(session.concepts):
                            session.selected_concept_index = idx
                            return {"session_id": session_id, **self.phase3_start(session)}
                    except (ValueError, IndexError):
                        pass
                    session.selected_concept_index = 0
                    return {"session_id": session_id, **self.phase3_start(session)}

            # Phase 3: Core Loop
            elif phase == "core_loop":
                if step == 1:
                    return {"session_id": session_id, **self.phase3_step2(session, value)}
                elif step == 2:
                    return {"session_id": session_id, **self.phase3_step3(session, value)}
                elif step == 3:
                    return {"session_id": session_id, **self.phase3_step4(session, value)}
                elif step == 4:
                    return {"session_id": session_id, **self.phase3_step5(session, value)}
                elif step == 5:
                    return {"session_id": session_id, **self.phase3_step6(session, value)}
                elif step == 6:
                    return {"session_id": session_id, **self.phase3_step7(session, value)}
                elif step == 7:
                    return {"session_id": session_id, **self.phase4_start(session)}

            # Phase 4: Pillars
            elif phase == "pillars":
                if step == 1:
                    return {"session_id": session_id, **self.phase4_step2(session, value)}
                elif step == 2:
                    return {"session_id": session_id, **self.phase4_step3(session, value)}
                elif step == 3:
                    session.visual_direction = value
                    return {"session_id": session_id, **self.phase5_start(session)}

            # Phase 5: Player Types
            elif phase == "player_types":
                if step == 1:
                    return {"session_id": session_id, **self.phase5_step2(session, value)}
                elif step == 2:
                    return {"session_id": session_id, **self.phase5_step3(session, value)}
                elif step == 3:
                    return {"session_id": session_id, **self.phase5_step4(session, value)}
                elif step == 4:
                    return {"session_id": session_id, **self.phase6_start(session)}

            # Phase 6: Scope
            elif phase == "scope":
                if step == 1:
                    return {"session_id": session_id, **self.phase6_step2(session, value)}
                elif step == 2:
                    return {"session_id": session_id, **self.phase6_step3(session, value)}
                elif step == 3:
                    return {"session_id": session_id, **self.phase6_step4(session, value)}
                elif step == 4:
                    return {"session_id": session_id, **self.phase6_step5(session, value)}
                elif step == 5:
                    session.scope_tiers = value
                    return {"session_id": session_id, **self.finalize(session)}

            return {"error": f"Unknown step {step} in phase {phase}"}

        except Exception as e:
            return {"error": str(e), "session_id": session_id, "phase": phase, "step": step}


# 全域實例
brainstorm_skill = BrainstormSkill()
