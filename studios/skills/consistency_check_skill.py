"""
Alice Game Studio — /consistency-check Skill
Phase 2.5: 掃描所有 GDD 的矛盾與未定義參照
移植自 CCGS consistency-check：矛盾偵測 + 未定義參照掃描
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Set
import re

_sessions: Dict[str, 'ConsistencyCheckSession'] = {}

# ── 矛盾類型定義 ──
CONTRADICTION_TYPES = {
    "value_conflict": {"name": "數值矛盾", "severity": "high", "icon": "🔴"},
    "state_conflict": {"name": "狀態矛盾", "severity": "high", "icon": "🔴"},
    "logic_conflict": {"name": "邏輯矛盾", "severity": "critical", "icon": "💀"},
    "timing_conflict": {"name": "時序矛盾", "severity": "medium", "icon": "🟡"},
    "scope_conflict": {"name": "範圍矛盾", "severity": "medium", "icon": "🟡"},
    "terminology_conflict": {"name": "術語矛盾", "severity": "low", "icon": "🟢"},
    "undefined_ref": {"name": "未定義參照", "severity": "high", "icon": "🔴"},
    "duplicate_def": {"name": "重複定義", "severity": "medium", "icon": "🟡"},
}

# ── 矛盾偵測規則 ──
CONTRADICTION_RULES = [
    # (正則, 類型, 描述)
    (r'(\w+)\s*[=＝]\s*(\d+).*?\n.*?\1\s*[=＝]\s*(\d+)', "value_conflict", "同一變數在不同位置有不同數值"),
    (r'永遠|總是|絕不|never|always', "logic_conflict", "絕對性詞彙 — 檢查是否有例外情況未處理"),
    (r'同時.*?(但|然而|可是|不過)', "logic_conflict", "同時出現但/然而 — 可能有邏輯矛盾"),
    (r'(所有|全部|all).*?除了', "logic_conflict", "全稱 + 例外 — 檢查例外是否完備"),
    (r'(\w+狀態).*?(\w+狀態)', "state_conflict", "多個狀態名稱 — 檢查是否有衝突"),
    (r'第[一二三]階段.*?第[一二三]階段', "timing_conflict", "多個階段描述 — 檢查時序"),
    (r'最低.*?(\d+).*?最高.*?(\d+)', "value_conflict", "範圍邊界 — 檢查 min ≤ max"),
]


class ConsistencyCheckSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = "init"
        self.gdd_content: str = ""
        self.gdd_path: str = ""
        self.reference_content: str = ""  # game-concept.md 或跨系統參考
        self.contradictions: List[Dict] = []
        self.undefined_refs: List[Dict] = []
        self.duplicate_defs: List[Dict] = []
        self.total_issues: int = 0
        self.severity_counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        self.report: str = ""
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


class ConsistencyCheckSkill:
    """/consistency-check 核心邏輯"""

    def handle_init(self, gdd_path: str = "", gdd_content: str = "", reference_path: str = "") -> dict:
        import uuid
        session_id = str(uuid.uuid4())[:8]
        session = ConsistencyCheckSession(session_id)
        session.state = "loading"

        if gdd_path:
            session.gdd_path = gdd_path
            try:
                session.gdd_content = Path(gdd_path).read_text(encoding='utf-8')
                session.state = "analyzing"
            except:
                pass

        if gdd_content and not session.gdd_content:
            session.gdd_content = gdd_content
            session.state = "analyzing"

        if reference_path:
            try:
                session.reference_content = Path(reference_path).read_text(encoding='utf-8')
            except:
                pass

        _sessions[session_id] = session

        if session.state == "analyzing":
            return self._run_check(session)
        else:
            return {
                "session_id": session_id,
                "state": "awaiting_content",
                "question": {
                    "id": "gdd_input",
                    "text": "請提供要檢查的 GDD 文件路徑或內容。也可以提供參考文件（如 game-concept.md）的路徑。",
                    "example": "GDD_戰鬥系統.md | game-concept.md"
                }
            }

    def handle_response(self, session_id: str, field: str, value: str) -> dict:
        session = _sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.state == "awaiting_content":
            parts = [p.strip() for p in value.split("|")]
            # 第一個是 GDD，第二個是參考
            gdd_input = parts[0]
            ref_input = parts[1] if len(parts) > 1 else ""

            # 嘗試讀取
            for input_val, is_ref in [(gdd_input, False), (ref_input, True)]:
                if not input_val:
                    continue
                try:
                    content = Path(input_val).read_text(encoding='utf-8')
                    if is_ref:
                        session.reference_content = content
                    else:
                        session.gdd_content = content
                        session.gdd_path = input_val
                except:
                    if is_ref:
                        session.reference_content = input_val
                    else:
                        session.gdd_content = input_val

            session.state = "analyzing"
            session.updated_at = datetime.now().isoformat()
            return self._run_check(session)

        return {"error": "Unknown state"}

    def _run_check(self, session: ConsistencyCheckSession) -> dict:
        content = session.gdd_content
        ref_content = session.reference_content

        contradictions = []
        undefined_refs = []
        duplicate_defs = []

        # ── 規則偵測 ──
        lines = content.split("\n")
        for i, line in enumerate(lines):
            for pattern, ctype, desc in CONTRADICTION_RULES:
                matches = re.findall(pattern, line, re.IGNORECASE)
                if matches:
                    for match in matches:
                        if isinstance(match, tuple):
                            match_str = " vs ".join(str(m) for m in match)
                        else:
                            match_str = str(match)

                        if ctype not in ["value_conflict", "state_conflict"] or len(match_str) > 5:
                            contradictions.append({
                                "type": ctype,
                                "type_name": CONTRADICTION_TYPES[ctype]["name"],
                                "severity": CONTRADICTION_TYPES[ctype]["severity"],
                                "icon": CONTRADICTION_TYPES[ctype]["icon"],
                                "line": i + 1,
                                "content": line.strip()[:120],
                                "match": match_str[:80],
                                "rule": desc,
                            })

        # ── 未定義參照偵測 ──
        # 找「如 XXX 所述」「參見 XXX」「XXX 定義」等
        ref_patterns = [
            (r'(?:如|參見|參考|詳見|見)\s*[「《](.+?)[」》]', "文件參照"),
            (r'(?:使用|調用|呼叫|觸發)\s*[「《]?(.+?(?:系統|模組|功能))[」》]?', "系統參照"),
            (r'[「「](.+?)[」」]', "引號參照"),
        ]

        for pattern, ref_type in ref_patterns:
            for m in re.finditer(pattern, content):
                ref_name = m.group(1).strip()
                if ref_name and len(ref_name) > 1:
                    # 檢查是否在本文件或參考文件中定義
                    found_in_doc = ref_name.lower() in content.lower()

                    if ref_type == "文件參照":
                        undefined_refs.append({
                            "ref_name": ref_name,
                            "type": ref_type,
                            "line": content[:m.start()].count('\n') + 1,
                            "defined": False,  # 無法驗證外部文件
                            "detail": f"參照到外部文件: {ref_name}，無法驗證是否存在",
                        })
                    elif ref_type == "系統參照":
                        if not found_in_doc and (not ref_content or ref_name.lower() not in ref_content.lower()):
                            undefined_refs.append({
                                "ref_name": ref_name,
                                "type": ref_type,
                                "line": content[:m.start()].count('\n') + 1,
                                "defined": found_in_doc,
                                "detail": f"參照的系統未在本文件或參考文件中找到定義: {ref_name}",
                            })
                    elif ref_type == "引號參照":
                        # 檢查引號內容是否為專有名詞
                        if ref_name not in content.replace(ref_name, "", 1):
                            pass  # 只出現一次且無定義

        # ── 重複定義偵測 ──
        # 找重複的 ## 標題
        headers = re.findall(r'^##\s+(.+?)$', content, re.MULTILINE)
        seen_headers = {}
        for h in headers:
            h_clean = h.strip().lower()
            if h_clean in seen_headers:
                duplicate_defs.append({
                    "name": h.strip(),
                    "first_line": seen_headers[h_clean],
                    "second_line": "N/A",
                    "detail": f"標題 '{h.strip()}' 在文件中出現多次",
                })
            else:
                seen_headers[h_clean] = 0  # placeholder

        # ── 與參考文件比對 ──
        if ref_content:
            # 檢查 GDD 中的系統名稱是否在 concept 中提到
            gdd_systems = re.findall(r'##\s+(.+?(?:系統|System))', content, re.IGNORECASE)
            for sys in gdd_systems:
                if sys.lower() not in ref_content.lower():
                    contradictions.append({
                        "type": "scope_conflict",
                        "type_name": "範圍矛盾",
                        "severity": "medium",
                        "icon": "🟡",
                        "line": 0,
                        "content": f"系統 '{sys}'",
                        "match": sys,
                        "rule": f"GDD 中的系統 '{sys}' 在 concept 文件中未提及",
                    })

            # 檢查 concept 中的支柱是否在 GDD 中體現
            pillars = re.findall(r'[🎯🏛️].*?(?:支柱|pillar).*?[：:]\s*(.+?)(?:\n|$)', ref_content)
            for pillar in pillars:
                if pillar.strip().lower() not in content.lower():
                    contradictions.append({
                        "type": "logic_conflict",
                        "type_name": "邏輯矛盾",
                        "severity": "medium",
                        "icon": "🟡",
                        "line": 0,
                        "content": f"支柱: {pillar.strip()}",
                        "match": pillar.strip(),
                        "rule": f"concept 中的支柱 '{pillar.strip()}' 在 GDD 中未體現",
                    })

        # ── 彙總 ──
        session.contradictions = contradictions
        session.undefined_refs = undefined_refs
        session.duplicate_defs = duplicate_defs
        session.total_issues = len(contradictions) + len(undefined_refs) + len(duplicate_defs)

        for c in contradictions:
            sev = c.get("severity", "low")
            if sev in session.severity_counts:
                session.severity_counts[sev] += 1

        session.state = "complete"
        session.updated_at = datetime.now().isoformat()

        session.report = self._generate_report(session)

        return {
            "session_id": session.session_id,
            "state": "complete",
            "total_issues": session.total_issues,
            "contradictions_count": len(contradictions),
            "undefined_refs_count": len(undefined_refs),
            "duplicate_defs_count": len(duplicate_defs),
            "severity_counts": session.severity_counts,
            "contradictions": contradictions[:20],
            "undefined_refs": undefined_refs[:20],
            "duplicate_defs": duplicate_defs[:20],
            "report": session.report,
        }

    def _generate_report(self, session: ConsistencyCheckSession) -> str:
        lines = []
        path_display = session.gdd_path or "（貼上內容）"
        lines.append(f"# 🔍 一致性檢查報告\n")
        lines.append(f"**檢查時間**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**檢查文件**: {path_display}")
        lines.append(f"**問題總數**: {session.total_issues}\n")

        # 嚴重度摘要
        lines.append("## 📊 嚴重度摘要\n")
        lines.append("| 嚴重度 | 數量 |")
        lines.append("|:--|:--|")
        for sev, count in session.severity_counts.items():
            icon = {"critical": "💀", "high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
            if count > 0:
                lines.append(f"| {icon} {sev} | {count} |")

        # 矛盾清單
        if session.contradictions:
            lines.append(f"\n## 🔴 矛盾 ({len(session.contradictions)})\n")
            for c in session.contradictions[:15]:
                lines.append(f"### {c['icon']} {c['type_name']} (第{c['line']}行)")
                lines.append(f"> {c['content']}")
                lines.append(f"**規則**: {c['rule']}")
                if c['match']:
                    lines.append(f"**匹配**: `{c['match']}`")
                lines.append("")

        # 未定義參照
        if session.undefined_refs:
            lines.append(f"\n## 🔗 未定義參照 ({len(session.undefined_refs)})\n")
            for r in session.undefined_refs[:10]:
                lines.append(f"- [{r['type']}] `{r['ref_name']}` (第{r['line']}行): {r['detail']}")

        # 重複定義
        if session.duplicate_defs:
            lines.append(f"\n## 🔄 重複定義 ({len(session.duplicate_defs)})\n")
            for d in session.duplicate_defs:
                lines.append(f"- `{d['name']}`: {d['detail']}")

        # 總結
        lines.append(f"\n## 🏁 總結\n")
        if session.total_issues == 0:
            lines.append("✅ 未發現任何矛盾、未定義參照或重複定義。文件一致性良好！")
        elif session.severity_counts.get("critical", 0) > 0:
            lines.append(f"💀 發現 {session.severity_counts['critical']} 個嚴重矛盾，建議立即修正後再繼續。")
        elif session.severity_counts.get("high", 0) > 0:
            lines.append(f"🔴 發現 {session.severity_counts['high']} 個高度問題，建議在繼續前修正。")
        else:
            lines.append(f"🟡 發現 {session.total_issues} 個低/中度問題，可以在後續迭代中修正。")

        return "\n".join(lines)

    def get_session(self, session_id: str) -> Optional[ConsistencyCheckSession]:
        return _sessions.get(session_id)


consistency_check_skill = ConsistencyCheckSkill()
