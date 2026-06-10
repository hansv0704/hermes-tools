"""
Alice Game Studio — godot_bridge.py
移植自 CCGS Godot agents (5 個專家)
Godot CLI 橋接：版本偵測、headless 執行、讀寫 .gd/.tscn/project.godot

Phase 1.6 — Phase 1 最後模組
"""

import os
import re
import json
import glob
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


# ═══════════════════════════════════════════════════════════════
# Godot 引擎管理
# ═══════════════════════════════════════════════════════════════

class GodotBridge:
    """Godot CLI 橋接器 — 所有 Godot 操作的統一入口"""

    def __init__(self, godot_path: Optional[str] = None):
        self.godot_path = godot_path or self._auto_detect()
        self._version: Optional[str] = None
        self._project_dir: Optional[Path] = None

    # ── 偵測 ──

    @staticmethod
    def _auto_detect() -> Optional[str]:
        """自動偵測 Godot 執行檔（擴展搜尋範圍）"""
        search_paths = [
            # PATH
            "godot",
            "godot.exe",
            # 標準安裝
            "C:\\Program Files\\Godot\\Godot_v4.5-stable_win64.exe",
            "C:\\Program Files\\Godot\\Godot_v4.4-stable_win64.exe",
            "C:\\Program Files\\Godot\\Godot_v4.3-stable_win64.exe",
            "C:\\Program Files\\Godot\\Godot_v4.4-stable_win64_console.exe",
            # Steam 版
            "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Godot Engine\\godot.windows.opt.tools.64.exe",
            "D:\\SteamLibrary\\steamapps\\common\\Godot Engine\\godot.windows.opt.tools.64.exe",
            # Scoop / Chocolatey
            os.path.expandvars("%USERPROFILE%\\scoop\\apps\\godot\\current\\godot.exe"),
            os.path.expandvars("%USERPROFILE%\\scoop\\shims\\godot.exe"),
            # 直接下載版（常見路徑）
            os.path.expandvars("%USERPROFILE%\\Downloads\\Godot_v4.4-stable_win64.exe"),
            os.path.expandvars("%USERPROFILE%\\Downloads\\Godot_v4.3-stable_win64.exe"),
            os.path.expandvars("%USERPROFILE%\\Desktop\\Godot_v4.4-stable_win64.exe"),
            # 自訂 Program Files
            "D:\\Program Files\\Godot\\Godot_v4.4-stable_win64.exe",
            "D:\\Program Files\\Godot\\Godot_v4.3-stable_win64.exe",
            # E: 磁碟（外接 / 可攜式）
            "E:\\Godot_v4.5-stable_win64.exe",
            "E:\\Godot_v4.4-stable_win64.exe",
            "E:\\Godot_v4.3-stable_win64.exe",
            "E:\\Program Files\\Godot\\Godot_v4.5-stable_win64.exe",
            "E:\\Program Files\\Godot\\Godot_v4.4-stable_win64.exe",
            # Godot 4.x 通用搜尋 (any version in Godot dir)
        ]
        for p in search_paths:
            try:
                result = subprocess.run(
                    [p, "--version"], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    return p
            except Exception:
                continue
        # 第二輪：glob 搜尋 Program Files 下的 Godot 目錄
        return GodotBridge._search_godot_dir()

    @staticmethod
    def _search_godot_dir() -> Optional[str]:
        """在常見 Godot 目錄中 glob 搜尋任何版本"""
        search_dirs = [
            "C:\\Program Files\\Godot",
            "D:\\Program Files\\Godot",
            "E:\\Program Files\\Godot",
            "E:\\",
            os.path.expandvars("%LOCALAPPDATA%\\Programs\\Godot"),
        ]
        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            candidates = glob.glob(os.path.join(d, "Godot*.exe"))
            candidates += glob.glob(os.path.join(d, "godot*.exe"))
            for c in candidates:
                try:
                    result = subprocess.run(
                        [c, "--version"], capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        return c
                except Exception:
                    continue
        return None

    @staticmethod
    def search_disk() -> List[str]:
        """深度搜尋系統中所有可能的 Godot 安裝（回傳所有找到的路徑）"""
        found = []
        search_roots = [
            "C:\\Program Files\\Godot",
            "C:\\Program Files (x86)\\Steam\\steamapps\\common",
            "D:\\Program Files\\Godot",
            "D:\\SteamLibrary\\steamapps\\common",
            "E:\\Program Files\\Godot",
            "E:\\",
            os.path.expandvars("%LOCALAPPDATA%\\Programs\\Godot"),
            os.path.expandvars("%USERPROFILE%\\scoop\\apps"),
        ]
        for root in search_roots:
            if not os.path.isdir(root):
                continue
            for dirpath, _, filenames in os.walk(root):
                # 限制深度避免無限搜尋
                depth = dirpath.replace(root, "").count(os.sep)
                if depth > 4:
                    continue
                for fname in filenames:
                    if fname.lower().startswith("godot") and fname.lower().endswith(".exe"):
                        full = os.path.join(dirpath, fname)
                        if full not in found:
                            found.append(full)
        # 也檢查 PATH
        try:
            r = subprocess.run(["where", "godot"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                for line in r.stdout.strip().split('\n'):
                    line = line.strip()
                    if line and line not in found:
                        found.append(line)
        except Exception:
            pass
        return found

    @staticmethod
    def file_dialog() -> Optional[str]:
        """開啟 Windows 檔案選擇器讓主人直接點選 Godot 執行檔"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="請選擇 Godot 執行檔",
                filetypes=[
                    ("Godot 執行檔", "Godot*.exe;godot*.exe"),
                    ("所有執行檔", "*.exe"),
                    ("所有檔案", "*.*"),
                ],
                initialdir="E:\\",
            )
            root.destroy()
            return path if path else None
        except Exception:
            return None

    def set_path(self, godot_path: str) -> Dict[str, Any]:
        """手動設定 Godot 路徑並驗證（含 shell fallback 處理 E:\ 權限問題）"""
        # 前置驗證：路徑必須是存在的檔案
        if not os.path.isfile(godot_path):
            return {"success": False, "error": f"路徑不是有效檔案: {godot_path}"}

        # 方法 1: 直接執行
        try:
            result = subprocess.run(
                [godot_path, "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.godot_path = godot_path
                self._version = result.stdout.strip()
                return {"success": True, "path": godot_path, "version": self._version}
            else:
                return {"success": False, "error": f"Godot 回傳非零退出碼: {result.returncode}"}
        except PermissionError:
            pass  # → shell=True fallback（PermissionError 即 WinError 5 在 Python 3.3+ 的表現）
        except FileNotFoundError:
            return {"success": False, "error": f"找不到檔案: {godot_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

        # 方法 2: shell=True（處理可攜式 / 外接磁碟權限問題）
        try:
            result = subprocess.run(
                f"{shlex.quote(godot_path)} --version",
                capture_output=True, text=True, timeout=10, shell=True
            )
            if result.returncode == 0:
                self.godot_path = godot_path
                self._version = result.stdout.strip()
                return {"success": True, "path": godot_path, "version": self._version, "method": "shell"}
            else:
                return {
                    "success": False,
                    "error": f"Godot 回傳非零退出碼 (shell): {result.returncode}\nstderr: {result.stderr}",
                }
        except Exception as e:
            return {
                "success": False,
                "error": (
                    f"驗證失敗: {str(e)}\n"
                    f"💡 提示：E:\\ 或外接磁碟上的可攜式 Godot 可能需要以系統管理員身分執行 Game Studio"
                ),
            }

    def get_version(self) -> Optional[str]:
        """取得 Godot 版本"""
        if self.godot_path and not self._version:
            try:
                result = subprocess.run(
                    [self.godot_path, "--version"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    self._version = result.stdout.strip()
            except Exception:
                self._version = None
        return self._version

    # ── 專案操作 ──

    def open_project(self, project_dir: str) -> Dict[str, Any]:
        """設定當前 Godot 專案路徑並讀取 project.godot"""
        project_path = Path(project_dir)
        if not project_path.exists():
            return {"success": False, "error": f"目錄不存在: {project_dir}"}

        godot_file = project_path / "project.godot"
        if not godot_file.exists():
            return {"success": False, "error": "此目錄不是 Godot 專案 (缺少 project.godot)"}

        self._project_dir = project_path
        settings = self._parse_project_godot(godot_file)
        return {"success": True, "project_dir": str(project_path), "settings": settings}

    def _parse_project_godot(self, path: Path) -> Dict[str, str]:
        """解析 project.godot 設定檔"""
        settings = {}
        try:
            content = path.read_text(encoding="utf-8")
            for line in content.split("\n"):
                line = line.strip()
                if "=" in line and not line.startswith(";"):
                    key, _, value = line.partition("=")
                    settings[key.strip()] = value.strip().strip('"')
        except Exception:
            pass
        return settings

    # ── Headless 執行 ──

    def run_script(self, script_path: str, args: List[str] = None) -> Dict[str, Any]:
        """在 headless 模式下執行 GDScript（移植自 CCGS godot-specialist）"""
        if not self._project_dir:
            return {"success": False, "error": "尚未設定專案。請先呼叫 open_project()"}

        script_file = self._project_dir / script_path
        if not script_file.exists():
            return {"success": False, "error": f"腳本不存在: {script_path}"}

        cmd = [
            self.godot_path,
            "--headless",
            "--path", str(self._project_dir),
            "--script", str(script_file),
        ]
        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(self._project_dir))
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "執行超時 (60s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_editor_command(self, command: str) -> Dict[str, Any]:
        """在 headless 模式下執行 Godot editor 命令"""
        if not self._project_dir:
            return {"success": False, "error": "尚未設定專案"}

        cmd = [
            self.godot_path,
            "--headless",
            "--path", str(self._project_dir),
            "--editor",
            command,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(self._project_dir))
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 匯出建置 ──

    def export_project(self, export_preset: str, output_path: str) -> Dict[str, Any]:
        """匯出專案（移植自 CCGS release-manager）"""
        if not self._project_dir:
            return {"success": False, "error": "尚未設定專案"}

        cmd = [
            self.godot_path,
            "--headless",
            "--path", str(self._project_dir),
            "--export-release", export_preset, output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(self._project_dir))
            return {
                "success": result.returncode == 0 and os.path.exists(output_path),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "output_path": output_path,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_export_presets(self) -> List[str]:
        """列出所有匯出預設"""
        if not self._project_dir:
            return []
        export_file = self._project_dir / "export_presets.cfg"
        if not export_file.exists():
            return []
        presets = []
        content = export_file.read_text(encoding="utf-8")
        for match in re.finditer(r'\[preset\.\d+\.options\]\nname="(.+)"', content):
            presets.append(match.group(1))
        return presets

    # ── 檔案讀寫 ──

    def read_gdscript(self, relative_path: str) -> Dict[str, Any]:
        """讀取 GDScript 檔案內容（返回類別/函式/信號結構）"""
        if not self._project_dir:
            return {"success": False, "error": "尚未設定專案"}
        file_path = self._project_dir / relative_path
        if not file_path.exists():
            return {"success": False, "error": f"檔案不存在: {relative_path}"}

        content = file_path.read_text(encoding="utf-8")
        return {
            "success": True,
            "path": str(file_path),
            "content": content,
            "analysis": self._analyze_gdscript(content),
        }

    def write_gdscript(self, relative_path: str, content: str) -> Dict[str, Any]:
        """寫入 GDScript 檔案"""
        if not self._project_dir:
            return {"success": False, "error": "尚未設定專案"}
        file_path = self._project_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            file_path.write_text(content, encoding="utf-8")
            return {"success": True, "path": str(file_path), "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _analyze_gdscript(self, content: str) -> Dict[str, Any]:
        """分析 GDScript 結構"""
        analysis = {
            "extends": None,
            "class_name": None,
            "signals": [],
            "consts": [],
            "vars": [],
            "funcs": [],
            "line_count": len(content.split("\n")),
        }
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("extends "):
                analysis["extends"] = line.replace("extends ", "").strip()
            elif line.startswith("class_name "):
                analysis["class_name"] = line.replace("class_name ", "").strip()
            elif line.startswith("signal "):
                analysis["signals"].append(line.replace("signal ", "").strip())
            elif line.startswith("const "):
                analysis["consts"].append(line.replace("const ", "").strip())
            elif line.startswith("var "):
                analysis["vars"].append(line.replace("var ", "").strip().rstrip(":"))
            elif line.startswith("func "):
                func_name = line.replace("func ", "").split("(")[0].strip()
                analysis["funcs"].append(func_name)
        return analysis

    def read_scene(self, relative_path: str) -> Dict[str, Any]:
        """讀取 .tscn 場景檔案"""
        if not self._project_dir:
            return {"success": False, "error": "尚未設定專案"}
        file_path = self._project_dir / relative_path
        if not file_path.exists():
            return {"success": False, "error": f"場景不存在: {relative_path}"}

        content = file_path.read_text(encoding="utf-8")
        return {
            "success": True,
            "path": str(file_path),
            "content": content,
            "analysis": self._analyze_scene(content),
        }

    def _analyze_scene(self, content: str) -> Dict[str, Any]:
        """分析 .tscn 場景結構 (CCGS Godot scene parser)"""
        nodes = []
        resources = []
        current_section = None

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("[node"):
                current_section = "node"
                match = re.search(r'name="(.+?)"', line)
                type_match = re.search(r'type="(.+?)"', line)
                parent_match = re.search(r'parent="(.+?)"', line)
                nodes.append({
                    "name": match.group(1) if match else "Unknown",
                    "type": type_match.group(1) if type_match else "Node",
                    "parent": parent_match.group(1) if parent_match else None,
                })
            elif line.startswith("[resource"):
                current_section = "resource"
                match = re.search(r'type="(.+?)"', line)
                path_match = re.search(r'path="(.+?)"', line)
                resources.append({
                    "type": match.group(1) if match else "Resource",
                    "path": path_match.group(1) if path_match else None,
                })

        return {
            "node_count": len(nodes),
            "resource_count": len(resources),
            "nodes": [n["name"] for n in nodes],
            "node_types": list(set(n["type"] for n in nodes)),
        }

    def read_project_structure(self) -> Dict[str, Any]:
        """讀取專案結構（所有 .gd + .tscn 檔案清單）"""
        if not self._project_dir:
            return {"success": False, "error": "尚未設定專案"}

        gd_scripts = []
        scenes = []
        resources = []

        for dirpath, dirnames, filenames in os.walk(self._project_dir):
            # 跳過隱藏目錄
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
            rel_dir = Path(dirpath).relative_to(self._project_dir)
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                rel_path = str(rel_dir / fname)
                if ext == ".gd":
                    gd_scripts.append(rel_path)
                elif ext in (".tscn", ".scn"):
                    scenes.append(rel_path)
                elif ext == ".tres":
                    resources.append(rel_path)

        return {
            "success": True,
            "project_dir": str(self._project_dir),
            "scripts": {"count": len(gd_scripts), "files": sorted(gd_scripts)},
            "scenes": {"count": len(scenes), "files": sorted(scenes)},
            "resources": {"count": len(resources), "files": sorted(resources)},
        }


    # ── 健康檢查與重連 ──

    def health_check(self) -> Dict[str, Any]:
        """檢查 Godot 是否可正常執行，以及當前連線狀態"""
        result = {
            "connected": False,
            "godot_path": self.godot_path,
            "version": self._version,
            "project_dir": str(self._project_dir) if self._project_dir else None,
            "godot_alive": False,
            "project_open": self._project_dir is not None,
        }
        if not self.godot_path:
            result["error"] = "尚未設定 Godot 路徑"
            return result

        # 測試 Godot 是否可執行
        try:
            r = subprocess.run(
                [self.godot_path, "--version"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                result["godot_alive"] = True
                result["version"] = r.stdout.strip()
                self._version = r.stdout.strip()
                result["connected"] = True
            else:
                result["error"] = f"Godot 回傳非零退出碼: {r.returncode}"
        except PermissionError:
            # shell=True fallback
            try:
                r = subprocess.run(
                    f"{shlex.quote(self.godot_path)} --version",
                    capture_output=True, text=True, timeout=10, shell=True
                )
                if r.returncode == 0:
                    result["godot_alive"] = True
                    result["version"] = r.stdout.strip()
                    self._version = r.stdout.strip()
                    result["connected"] = True
                else:
                    result["error"] = f"Godot shell 回傳非零: {r.returncode}"
            except Exception as e2:
                result["error"] = str(e2)
        except FileNotFoundError:
            result["error"] = f"Godot 執行檔不存在: {self.godot_path}"
        except Exception as e:
            result["error"] = str(e)

        # 驗證專案目錄仍存在
        if self._project_dir and not self._project_dir.exists():
            result["project_open"] = False
            result["error"] = f"專案目錄不存在: {self._project_dir}"
            self._project_dir = None

        return result

    def reconnect(self, godot_path: Optional[str] = None) -> Dict[str, Any]:
        """重新連接 Godot，可選指定新路徑。保留已開啟的專案資訊"""
        if godot_path:
            set_result = self.set_path(godot_path)
            if not set_result.get("success"):
                return {"success": False, "error": set_result.get("error", "設定路徑失敗"), "set_path_result": set_result}

        # 如果沒有路徑，嘗試自動偵測
        if not self.godot_path:
            detected = self._auto_detect()
            if not detected:
                return {"success": False, "error": "無法自動偵測 Godot，請手動設定路徑"}
            self.godot_path = detected

        # 驗證 Godot
        try:
            r = subprocess.run(
                [self.godot_path, "--version"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode != 0:
                # shell fallback
                r2 = subprocess.run(
                    f"{shlex.quote(self.godot_path)} --version",
                    capture_output=True, text=True, timeout=10, shell=True
                )
                if r2.returncode != 0:
                    return {"success": False, "error": f"Godot 無法執行: {r2.stderr}"}
                self._version = r2.stdout.strip()
            else:
                self._version = r.stdout.strip()
        except Exception as e:
            return {"success": False, "error": str(e)}

        # 如果之前有開啟的專案，重新打開
        project_reopened = False
        if self._project_dir and self._project_dir.exists():
            godot_file = self._project_dir / "project.godot"
            if godot_file.exists():
                project_reopened = True

        return {
            "success": True,
            "godot_path": self.godot_path,
            "version": self._version,
            "project_dir": str(self._project_dir) if self._project_dir else None,
            "project_reopened": project_reopened,
        }

    def get_project_info(self) -> Dict[str, Any]:
        """取得當前專案的完整資訊（結構 + 統計）"""
        if not self._project_dir:
            return {"success": False, "error": "尚未開啟專案"}

        structure = self.read_project_structure()
        if not structure.get("success"):
            return structure

        return {
            "success": True,
            "project_dir": str(self._project_dir),
            "godot_path": self.godot_path,
            "version": self._version,
            "scripts": structure.get("scripts", {}),
            "scenes": structure.get("scenes", {}),
            "resources": structure.get("resources", {}),
            "total_files": (
                structure.get("scripts", {}).get("count", 0) +
                structure.get("scenes", {}).get("count", 0) +
                structure.get("resources", {}).get("count", 0)
            ),
        }

    def list_files(self, subdir: str = "") -> Dict[str, Any]:
        """列出專案中指定子目錄的檔案（支援 .gd / .tscn / .tres 過濾）"""
        if not self._project_dir:
            return {"success": False, "error": "尚未開啟專案"}

        target_dir = self._project_dir / subdir if subdir else self._project_dir
        if not target_dir.exists():
            return {"success": False, "error": f"目錄不存在: {subdir}"}

        files = []
        dirs = []
        try:
            for item in sorted(target_dir.iterdir()):
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                rel = str(item.relative_to(self._project_dir)).replace("\\", "/")
                if item.is_dir():
                    dirs.append({"name": item.name, "path": rel, "type": "dir"})
                elif item.suffix.lower() in (".gd", ".tscn", ".tres", ".gdshader", ".cfg", ".json", ".md", ".txt"):
                    files.append({
                        "name": item.name,
                        "path": rel,
                        "type": "file",
                        "ext": item.suffix.lower(),
                        "size": item.stat().st_size,
                    })
        except Exception as e:
            return {"success": False, "error": str(e)}

        return {
            "success": True,
            "subdir": subdir,
            "dirs": dirs,
            "files": files,
        }


# ═══════════════════════════════════════════════════════════════
# 便捷函數（供 API 呼叫）
# ═══════════════════════════════════════════════════════════════

_global_bridge: Optional[GodotBridge] = None


def get_bridge(godot_path: Optional[str] = None) -> GodotBridge:
    """取得或建立全域 GodotBridge 實例"""
    global _global_bridge
    if _global_bridge is None or godot_path:
        _global_bridge = GodotBridge(godot_path)
    return _global_bridge


def detect_and_report(use_dialog: bool = False) -> Dict[str, Any]:
    """偵測 Godot 並回報完整資訊。use_dialog=True 時會開啟檔案選擇器"""
    bridge = GodotBridge()
    if use_dialog or bridge.godot_path is None:
        picked = GodotBridge.file_dialog()
        if picked:
            result = bridge.set_path(picked)
            if not result["success"]:
                return {"found": False, "path": picked, "error": result["error"]}
    version = bridge.get_version()
    return {
        "found": bridge.godot_path is not None,
        "path": bridge.godot_path,
        "version": version,
        "major_version": _parse_major(version) if version else None,
    }


def _parse_major(version_str: str) -> Optional[int]:
    match = re.search(r"(\d+)\.(\d+)", version_str)
    if match:
        return int(match.group(1))
    return None
