"""
Alice Game Studio — project_stage_detect_skill.py
移植自 CCGS project-stage-detect SKILL.md
全專案審計 + Phase 判定 + 差距報告

Phase 1.5
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


# ═══════════════════════════════════════════════════════════════
# CCGS 7 Phase Gate 定義
# ═══════════════════════════════════════════════════════════════

PHASE_GATES = {
    1: {
        "name": "Concept",
        "slug": "concept",
        "icon": "💡",
        "required_files": [],
        "indicators": {
            "game_concept": {"paths": ["**/game-concept.md", "**/concept.md"], "type": "file"},
        },
        "gate_criteria": "至少要有 game-concept.md 或同等概念文件",
    },
    2: {
        "name": "Systems Design",
        "slug": "systems-design",
        "icon": "📐",
        "required_files": [],
        "indicators": {
            "gdd_docs": {"paths": ["design/gdd/**/*.md", "**/gdd/**/*.md"], "type": "glob"},
            "system_map": {"paths": ["**/system-map.md", "**/systems.md"], "type": "file"},
        },
        "gate_criteria": "至少一個 GDD 文件 + 系統清單",
    },
    3: {
        "name": "Technical Setup",
        "slug": "technical-setup",
        "icon": "🔧",
        "required_files": [],
        "indicators": {
            "adr_docs": {"paths": ["docs/architecture/**/*.md", "**/adr/**/*.md"], "type": "glob"},
            "architecture": {"paths": ["**/architecture.md", "**/ARCHITECTURE.md"], "type": "file"},
            "control_manifest": {"paths": ["**/control-manifest.md"], "type": "file"},
        },
        "gate_criteria": "至少一個 ADR + 架構文件",
    },
    4: {
        "name": "Pre-Production",
        "slug": "pre-production",
        "icon": "🏗️",
        "required_files": [],
        "indicators": {
            "epics": {"paths": ["**/epics/**/*.md", "**/epic-*.md"], "type": "glob"},
            "stories": {"paths": ["**/stories/**/*.md", "**/story-*.md"], "type": "glob"},
            "ux_spec": {"paths": ["**/ux-spec.md", "**/ux-design.md"], "type": "file"},
            "prototypes": {"paths": ["prototypes/**/*.gd", "prototypes/**/*.tscn"], "type": "glob"},
        },
        "gate_criteria": "Epic + Story + UX 規格 + 至少一個原型",
    },
    5: {
        "name": "Production",
        "slug": "production",
        "icon": "⚙️",
        "required_files": [],
        "indicators": {
            "source_code": {"paths": ["src/**/*.gd", "src/**/*.cs"], "type": "glob"},
            "scenes": {"paths": ["assets/scenes/**/*.tscn"], "type": "glob"},
            "sprint_docs": {"paths": ["**/sprint-*.md"], "type": "glob"},
        },
        "gate_criteria": "原始碼 + 場景 + Sprint 文件",
    },
    6: {
        "name": "Polish",
        "slug": "polish",
        "icon": "✨",
        "required_files": [],
        "indicators": {
            "playtest_reports": {"paths": ["**/playtest-*.md"], "type": "glob"},
            "perf_reports": {"paths": ["**/perf-*.md", "**/performance-*.md"], "type": "glob"},
        },
        "gate_criteria": "至少 3 次無人引導試玩報告 + 效能分析",
    },
    7: {
        "name": "Release",
        "slug": "release",
        "icon": "🚀",
        "required_files": [],
        "indicators": {
            "release_checklist": {"paths": ["**/release-checklist.md"], "type": "file"},
            "changelog": {"paths": ["**/CHANGELOG.md", "**/changelog.md"], "type": "file"},
            "build": {"paths": ["export/**/*.exe", "export/**/*.apk", "build/**/*.exe"], "type": "glob"},
        },
        "gate_criteria": "發布清單 + 變更日誌 + 建置產出",
    },
}


def deep_scan_project(project_dir: str) -> Dict[str, Any]:
    """深層掃描專案，移植自 CCGS project-stage-detect"""
    root = Path(project_dir)
    if not root.exists():
        return {
            "status": "error",
            "message": f"專案目錄不存在: {project_dir}",
            "exists": False,
        }

    # ── 基本資訊 ──
    info = {
        "status": "success",
        "exists": True,
        "project_dir": str(root),
        "project_name": root.name,
        "scanned_at": datetime.now().isoformat(),
    }

    # ── 引擎偵測 ──
    info["engine"] = _detect_engine(root)

    # ── 檔案統計 ──
    info["file_stats"] = _count_files(root)

    # ── Phase 指標掃描 ──
    phase_indicators = {}
    for phase_id, gate in PHASE_GATES.items():
        indicators = {}
        for key, config in gate["indicators"].items():
            if config["type"] == "file":
                found = _find_files(root, config["paths"], mode="first")
                indicators[key] = {
                    "found": found is not None,
                    "path": str(found.relative_to(root)) if found else None,
                }
            elif config["type"] == "glob":
                found = _find_files(root, config["paths"], mode="all")
                indicators[key] = {
                    "found": len(found) > 0,
                    "count": len(found),
                    "paths": [str(f.relative_to(root)) for f in found[:10]],
                }
        phase_indicators[phase_id] = indicators

    info["phase_indicators"] = phase_indicators

    # ── 判定當前 Phase ──
    info["detected_phase"] = _determine_phase(phase_indicators)

    # ── 差距報告 ──
    info["gap_report"] = _generate_gap_report(phase_indicators, info["detected_phase"])

    # ── 下一步建議 ──
    info["next_steps"] = _generate_next_steps(info["detected_phase"], phase_indicators)

    return info


def _detect_engine(root: Path) -> Dict[str, Any]:
    """偵測遊戲引擎"""
    engine = {"type": "unknown", "version": None}

    # Godot
    project_godot = root / "project.godot"
    if project_godot.exists():
        engine["type"] = "Godot"
        content = project_godot.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r'config/version\s*=\s*"(.+)"', content)
        if match:
            engine["version"] = match.group(1)
        match_name = re.search(r'config/name\s*=\s*"(.+)"', content)
        if match_name:
            engine["project_name"] = match_name.group(1)

    # Unity
    for unity_dir in root.glob("**/ProjectSettings"):
        if unity_dir.is_dir():
            engine["type"] = "Unity"
            version_file = unity_dir / "ProjectVersion.txt"
            if version_file.exists():
                engine["version"] = version_file.read_text(encoding="utf-8").strip().split(":")[-1].strip()
            break

    # Unreal
    for uproject in root.glob("*.uproject"):
        engine["type"] = "Unreal"
        engine["project_file"] = str(uproject.relative_to(root))
        break

    return engine


def _count_files(root: Path) -> Dict[str, int]:
    """統計各類型檔案數量"""
    counts = {
        "total_files": 0,
        "total_dirs": 0,
        "gdscript": 0,
        "scenes": 0,
        "markdown": 0,
        "python": 0,
        "json": 0,
        "textures": 0,
        "audio": 0,
        "shaders": 0,
        "other": 0,
    }

    extensions = {
        "gdscript": [".gd"],
        "scenes": [".tscn", ".scn"],
        "markdown": [".md", ".mdx"],
        "python": [".py"],
        "json": [".json"],
        "textures": [".png", ".jpg", ".jpeg", ".bmp", ".tga", ".svg", ".webp"],
        "audio": [".wav", ".mp3", ".ogg", ".flac"],
        "shaders": [".gdshader", ".shader", ".glsl"],
    }

    for dirpath, dirnames, filenames in os.walk(root):
        # 跳過隱藏目錄和暫存
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        counts["total_dirs"] += 1
        for fname in filenames:
            counts["total_files"] += 1
            ext = os.path.splitext(fname)[1].lower()
            matched = False
            for cat, exts in extensions.items():
                if ext in exts:
                    counts[cat] += 1
                    matched = True
                    break
            if not matched:
                counts["other"] += 1

    counts["total_dirs"] -= 1  # 根目錄不算
    return counts


def _find_files(root: Path, patterns: List[str], mode: str = "first") -> Any:
    """尋找符合模式的檔案"""
    results = []
    for pattern in patterns:
        matches = list(root.glob(pattern))
        for m in matches:
            if m.is_file() and m not in results:
                results.append(m)

    if mode == "first":
        return results[0] if results else None
    return results


def _determine_phase(indicators: Dict[int, Dict]) -> int:
    """基於指標判定當前 Phase（反向：從最高 Phase 往下找）"""
    for phase_id in range(7, 0, -1):
        gate = PHASE_GATES[phase_id]
        phase_indicators = indicators.get(phase_id, {})

        if not gate["indicators"]:
            continue

        # 至少一項指標有內容
        any_found = any(
            v.get("found", False) or v.get("count", 0) > 0
            for v in phase_indicators.values()
        )
        if any_found:
            return phase_id

    return 1  # 預設 Phase 1


def _generate_gap_report(indicators: Dict[int, Dict], current_phase: int) -> Dict[str, Any]:
    """產生差距報告：從當前 Phase 到下一個 Phase 還缺什麼"""
    gaps = {}
    total_missing = 0

    # 檢查當前 Phase 的完成度
    current_gate = PHASE_GATES.get(current_phase, {})
    current_indicators = indicators.get(current_phase, {})
    current_missing = []
    for key, config in current_gate.get("indicators", {}).items():
        ind = current_indicators.get(key, {})
        if not ind.get("found", False):
            current_missing.append({
                "indicator": key,
                "description": f"缺少 {key}",
                "paths": config.get("paths", []),
            })
            total_missing += 1

    # 檢查下一個 Phase
    next_phase = min(current_phase + 1, 7)
    next_gate = PHASE_GATES.get(next_phase, {})
    next_indicators = indicators.get(next_phase, {})
    next_missing = []
    for key, config in next_gate.get("indicators", {}).items():
        ind = next_indicators.get(key, {})
        if not ind.get("found", False):
            next_missing.append({
                "indicator": key,
                "description": f"缺少 {key}（Phase {next_phase} 需求）",
                "paths": config.get("paths", []),
            })
            total_missing += 1

    gaps = {
        "current_phase": current_phase,
        "current_phase_name": PHASE_GATES[current_phase]["name"],
        "current_completion": _calc_completion(current_indicators, current_gate),
        "current_missing": current_missing,
        "next_phase": next_phase,
        "next_phase_name": PHASE_GATES[next_phase]["name"],
        "next_missing": next_missing,
        "total_missing": total_missing,
        "ready_for_next": len(next_missing) == 0 and len(current_missing) == 0,
    }

    return gaps


def _calc_completion(indicators: Dict, gate: Dict) -> float:
    """計算 Phase 完成度 (0-100%)"""
    if not gate.get("indicators"):
        return 100.0
    total = len(gate["indicators"])
    found = sum(1 for v in indicators.values() if v.get("found", False))
    return round(found / total * 100, 1)


def _generate_next_steps(current_phase: int, indicators: Dict[int, Dict]) -> List[str]:
    """產生下一步建議（移植自 CCGS）"""
    steps = []

    phase_actions = {
        1: [
            "執行 /brainstorm 來發想遊戲概念",
            "產出 game-concept.md",
            "執行 /setup-engine 來初始化 Godot 專案",
        ],
        2: [
            "執行 /map-systems 來拆解系統",
            "執行 /design-system 來撰寫 GDD",
            "執行 /design-review 來審查設計",
        ],
        3: [
            "執行 /create-architecture 來設計技術架構",
            "執行 /architecture-decision 來寫 ADR",
            "執行 /art-bible 來定義美術風格",
        ],
        4: [
            "執行 /create-epics 來建立 Epic",
            "執行 /create-stories 來建立 Story",
            "執行 /ux-design 來設計 UX",
            "執行 /prototype 來驗證核心機制",
        ],
        5: [
            "執行 /dev-story 來實現 Story",
            "執行 /code-review 來審查程式碼",
            "執行 /sprint-status 來追蹤進度",
        ],
        6: [
            "執行 /perf-profile 來分析效能",
            "執行 /playtest-report 來產出試玩報告",
            "執行 /asset-audit 來審計資產",
        ],
        7: [
            "執行 /release-checklist 來最終檢查",
            "執行 /launch-checklist 來準備上線",
            "執行 /changelog 來產出變更日誌",
        ],
    }

    steps = phase_actions.get(current_phase, phase_actions[1])

    # 如果當前 Phase 完成度高，也加入下一個 Phase 的步驟
    gate = PHASE_GATES[current_phase]
    current_indicators = indicators.get(current_phase, {})
    completion = _calc_completion(current_indicators, gate)
    if completion >= 80 and current_phase < 7:
        steps.append(f"📈 當前 Phase 完成度 {completion}%，可以準備進入 Phase {current_phase+1}")
        steps.extend(phase_actions.get(current_phase + 1, [])[:2])

    return steps


def get_project_overview(result: Dict[str, Any]) -> str:
    """產生人類可讀的專案概覽（CCGS 報告格式）"""
    if not result.get("exists"):
        return f"❌ 專案目錄不存在: {result.get('project_dir')}"

    lines = [
        "=" * 50,
        f"  📊 {result['project_name']} — 專案階段報告",
        "=" * 50,
        "",
        f"🔍 掃描時間: {result.get('scanned_at', 'N/A')}",
        f"🎮 引擎: {result['engine']['type']} {result['engine'].get('version', '')}",
        "",
        "📁 檔案統計:",
    ]

    fs = result.get("file_stats", {})
    lines.append(f"   總檔案: {fs.get('total_files', 0)}")
    lines.append(f"   總目錄: {fs.get('total_dirs', 0)}")
    if fs.get("gdscript", 0):
        lines.append(f"   GDScript: {fs['gdscript']}")
    if fs.get("scenes", 0):
        lines.append(f"   場景: {fs['scenes']}")
    if fs.get("markdown", 0):
        lines.append(f"   文件: {fs['markdown']}")

    lines.append("")
    lines.append(f"📍 判定 Phase: {result['detected_phase']} — {PHASE_GATES[result['detected_phase']]['name']}")

    gap = result.get("gap_report", {})
    lines.append(f"   完成度: {gap.get('current_completion', 0)}%")
    if gap.get("ready_for_next"):
        lines.append("   ✅ 準備就緒，可進入下一階段！")
    else:
        lines.append(f"   ⚠️ 尚有 {gap.get('total_missing', 0)} 項缺失")

    missing = gap.get("current_missing", []) + gap.get("next_missing", [])
    if missing:
        lines.append("")
        lines.append("❌ 缺失項目:")
        for m in missing[:5]:
            lines.append(f"   - {m['description']}")

    lines.append("")
    lines.append("📋 建議下一步:")
    for step in result.get("next_steps", [])[:5]:
        lines.append(f"   → {step}")

    return "\n".join(lines)
