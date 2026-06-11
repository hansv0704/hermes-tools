"""
Alice Game Studio — setup_engine_skill.py
移植自 CCGS setup-engine SKILL.md
Godot 專注：引擎偵測 + 專案 scaffold + 命名規範 + 效能預算

Phase 1.4
"""

import os
import json
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


# ═══════════════════════════════════════════════════════════════
# GODOT 偵測
# ═══════════════════════════════════════════════════════════════

GODOT_SEARCH_PATHS = [
    "C:\\Program Files\\Godot",
    "C:\\Program Files (x86)\\Godot",
    "C:\\Godot",
    os.path.expanduser("~\\Godot"),
    os.path.expanduser("~\\AppData\\Local\\Godot"),
    "D:\\Godot",
    "E:\\Godot",
]

GODOT_EXE_NAMES = [
    "Godot_v4.5-stable_win64.exe",
    "Godot_v4.4-stable_win64.exe",
    "Godot_v4.3-stable_win64.exe",
    "Godot_v4.2-stable_win64.exe",
    "Godot_v4.5-stable_win64_console.exe",
    "Godot_v4.4-stable_win64_console.exe",
    "godot.exe",
    "godot.windows.opt.tools.64.exe",
]


def detect_godot() -> Dict[str, Any]:
    """掃描系統，尋找 Godot 安裝"""
    result = {
        "found": False,
        "paths": [],
        "versions": [],
        "recommended": None,
    }

    # 1. 搜尋已知路徑
    for search_path in GODOT_SEARCH_PATHS:
        sp = Path(search_path)
        if sp.exists():
            for exe_name in GODOT_EXE_NAMES:
                exe_path = sp / exe_name
                if exe_path.exists():
                    result["paths"].append(str(exe_path))

    # 2. 用 where 搜尋
    try:
        where_result = subprocess.run(
            ["where", "godot"], capture_output=True, text=True, timeout=10
        )
        if where_result.returncode == 0:
            for line in where_result.stdout.strip().split("\n"):
                line = line.strip()
                if line and line not in result["paths"]:
                    result["paths"].append(line)
    except Exception:
        pass

    # 3. 檢查 PATH 中的 godot
    try:
        version_result = subprocess.run(
            ["godot", "--version"], capture_output=True, text=True, timeout=10
        )
        if version_result.returncode == 0:
            ver = version_result.stdout.strip()
            result["versions"].append({"path": "PATH/godot", "version": ver})
    except Exception:
        pass

    # 4. 對每個找到的路徑嘗試取版本
    for p in result["paths"]:
        try:
            ver = subprocess.run(
                [p, "--version"], capture_output=True, text=True, timeout=10
            )
            if ver.returncode == 0:
                v = ver.stdout.strip()
                result["versions"].append({"path": p, "version": v})
        except Exception:
            pass

    if result["paths"]:
        result["found"] = True
        # 推薦最新版本
        latest = None
        latest_ver = (0, 0, 0)
        for v in result["versions"]:
            match = re.search(r"(\d+)\.(\d+)\.(\d+)", v.get("version", ""))
            if match:
                ver_tuple = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                if ver_tuple > latest_ver:
                    latest_ver = ver_tuple
                    latest = v["path"]
        result["recommended"] = latest or result["paths"][0]

    return result


# ═══════════════════════════════════════════════════════════════
# 專案 SCAFFOLD
# ═══════════════════════════════════════════════════════════════

# 移植自 CCGS setup-engine 的標準目錄結構 (Godot 版)
CCGS_STANDARD_STRUCTURE = {
    "src": {
        "description": "原始碼",
        "subdirs": [
            "gameplay",      # 遊戲玩法邏輯
            "core",           # 引擎核心
            "ai",             # AI / 行為樹
            "network",        # 網路
            "tools",          # 開發工具
            "ui",             # 使用者介面
            "audio",          # 音效
            "vfx",            # 視覺特效
            "systems",        # 系統（存檔、成就等）
            "resources",      # 資源載入
        ],
    },
    "assets": {
        "description": "遊戲資產",
        "subdirs": [
            "sprites",
            "textures",
            "models",
            "animations",
            "sounds/music",
            "sounds/sfx",
            "fonts",
            "shaders",
            "scenes/levels",
            "scenes/ui",
            "scenes/characters",
            "scenes/props",
            "data",           # JSON/CSV 遊戲數據
        ],
    },
    "design": {
        "description": "設計文件",
        "subdirs": [
            "gdd",            # Game Design Documents
            "concept-art",
            "references",
            "wireframes",
        ],
    },
    "docs": {
        "description": "技術文件",
        "subdirs": [
            "architecture",  # ADR
            "api",
            "manuals",
        ],
    },
    "tests": {
        "description": "測試",
        "subdirs": [
            "unit",
            "integration",
            "performance",
        ],
    },
    "prototypes": {
        "description": "原型",
        "subdirs": [],
    },
}

GODOT_GITIGNORE = """# Godot 4.x
.godot/
*.translation
*.import

# 匯出
export/
build/

# VS Code
.vscode/
*.code-workspace

# Python (Alice 相關)
__pycache__/
*.pyc
.env
venv/

# 系統
Thumbs.db
.DS_Store
*.tmp
*.log

# 專案
*.blend1
*.blend2
"""

GODOT_PROJECT_TEMPLATE = """; Godot project settings — Generated by Alice Game Studio
; CCGS Phase 1.4 setup-engine

[application]
config/name="{project_name}"
config/description="{project_description}"
config/version="0.1.0"
run/main_scene=""

[rendering]
environment/default_clear_color=Color(0.1, 0.1, 0.15, 1)

[display]
window/size/viewport_width=1920
window/size/viewport_height=1080
window/stretch/mode="canvas_items"

[physics]
common/physics_ticks_per_second=60

[input]
; 在此定義輸入映射

[editor_plugins]
enabled=PackedStringArray()
"""

# 移植自 CCGS 的命名規範 + rules/
NAMING_CONVENTIONS = {
    "files": {
        "GDScript": "snake_case.gd",
        "Scenes": "snake_case.tscn",
        "Resources": "snake_case.tres",
        "Textures": "snake_case.png",
        "Audio": "snake_case.ogg",
    },
    "code": {
        "classes": "PascalCase",
        "functions": "snake_case()",
        "variables": "snake_case",
        "constants": "UPPER_SNAKE_CASE",
        "signals": "snake_case",
        "enums": "PascalCase",
    },
    "scenes": {
        "root_node": "場景名稱 PascalCase",
        "child_nodes": "snake_case 或 PascalCase",
        "unique_nodes": "以 % 前綴標記",
    },
    "directories": "snake_case（無空格、無特殊字元）",
}

# 移植自 CCGS 的效能預算 (Godot 版)
PERFORMANCE_BUDGET = {
    "target_fps": {
        "desktop": 60,
        "mobile": 30,
        "web": 60,
    },
    "memory": {
        "texture_total_mb": 512,
        "audio_total_mb": 128,
        "scene_max_mb": 64,
    },
    "draw_calls": {
        "max_per_frame": 2000,
        "target_per_frame": 500,
    },
    "physics": {
        "max_bodies": 200,
        "ticks_per_second": 60,
    },
    "script": {
        "max_lines_per_file": 500,
        "max_functions_per_file": 30,
    },
}


def scaffold_project(project_dir: str, project_name: str, project_description: str = "") -> Dict[str, Any]:
    """建立 CCGS 標準 Godot 專案 scaffold"""
    root = Path(project_dir)
    created = []
    skipped = []
    errors = []

    # 建立頂層目錄
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"success": False, "error": f"無法建立專案目錄: {e}"}

    # 建立 CCGS 標準結構
    for top_dir, config in CCGS_STANDARD_STRUCTURE.items():
        top_path = root / top_dir
        try:
            top_path.mkdir(exist_ok=True)
            created.append(str(top_path))
        except Exception as e:
            errors.append(f"{top_dir}: {e}")
            continue

        for sub in config.get("subdirs", []):
            sub_path = top_path / sub
            try:
                sub_path.mkdir(parents=True, exist_ok=True)
                created.append(str(sub_path))
            except Exception as e:
                errors.append(f"{sub}: {e}")

    # 建立 .gitignore
    gitignore_path = root / ".gitignore"
    try:
        gitignore_path.write_text(GODOT_GITIGNORE, encoding="utf-8")
        created.append(str(gitignore_path))
    except Exception as e:
        errors.append(f".gitignore: {e}")

    # 建立 project.godot
    project_godot_path = root / "project.godot"
    try:
        content = GODOT_PROJECT_TEMPLATE.format(
            project_name=project_name,
            project_description=project_description or f"{project_name} — 使用 Alice Game Studio 建立",
        )
        project_godot_path.write_text(content, encoding="utf-8")
        created.append(str(project_godot_path))
    except Exception as e:
        errors.append(f"project.godot: {e}")

    # 建立第一個 .gd 腳本（main.gd，位於 src/）
    main_gd_path = root / "src" / "main.gd"
    try:
        main_gd_path.parent.mkdir(parents=True, exist_ok=True)
        main_gd = f'''extends Node

# {project_name}
# 由 Alice Game Studio (CCGS Phase 1.4) 生成

func _ready() -> void:
\tprint("{project_name} 啟動成功！")
\tpass

func _process(delta: float) -> void:
\tpass
'''
        main_gd_path.write_text(main_gd, encoding="utf-8")
        created.append(str(main_gd_path))
    except Exception as e:
        errors.append(f"main.gd: {e}")

    return {
        "success": len(errors) == 0,
        "project_dir": str(root),
        "created_count": len(created),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


def get_engine_setup_summary(godot_info: Dict, scaffold_result: Dict) -> Dict[str, Any]:
    """產生 CCGS setup-engine 完整摘要"""
    return {
        "engine": {
            "type": "Godot",
            "found": godot_info.get("found", False),
            "installations": godot_info.get("versions", []),
            "recommended": godot_info.get("recommended"),
        },
        "scaffold": scaffold_result,
        "naming_conventions": NAMING_CONVENTIONS,
        "performance_budget": PERFORMANCE_BUDGET,
        "next_steps": [
            "在 Godot 中開啟 project.godot",
            "執行 /map-systems 來拆解遊戲系統",
            "執行 /design-system 來撰寫 GDD",
            "執行 /create-architecture 來設計技術架構",
        ],
    }
