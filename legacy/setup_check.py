"""
Alice 環境檢查腳本 v1.0
- 檢查 Python 版本
- 檢查 pip 可用性
- 自動安裝缺失的套件
- 檢查關鍵檔案完整性
- 檢查磁碟空間
- 支援隨身硬碟遷移場景
"""

import sys
import subprocess
import os
import importlib
import re
import shutil

# ── 顏色支援 ──
_has_color = False
try:
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    _has_color = True
except Exception:
    pass

GREEN = "\033[92m" if _has_color else ""
RED = "\033[91m" if _has_color else ""
YELLOW = "\033[93m" if _has_color else ""
CYAN = "\033[96m" if _has_color else ""
BOLD = "\033[1m" if _has_color else ""
RESET = "\033[0m" if _has_color else ""

PASS = f"{GREEN}✅{RESET}"
FAIL = f"{RED}❌{RESET}"
WARN = f"{YELLOW}⚠️{RESET}"
INFO = f"{CYAN}📌{RESET}"

# ── 關鍵檔案清單 ──
CRITICAL_FILES = [
    ("main.py", "主程式入口"),
    (".env", "環境變數設定"),
    ("requirements.txt", "依賴清單"),
]

OPTIONAL_FILES = [
    ("credentials.json", "Google API 憑證"),
    ("token.json", "Google Token"),
]

REQUIRED_DIRS = [
    ("skills/", "技能目錄"),
    ("engines/", "引擎目錄"),
    ("memory/", "記憶目錄"),
    ("templates/", "模板目錄"),
    ("data/", "資料目錄"),
]


def parse_requirement(line: str) -> tuple:
    """解析 requirement 行 → (套件名, import 名)"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # 移除版本條件和 extra
    cleaned = re.split(r"[<>=!~;\[]", line)[0].strip()
    if not cleaned:
        return None

    # 處理常見的 import 名 vs pip 名差異
    mapping = {
        # --- pip 名 ≠ import 名 ---
        "python-telegram-bot": "telegram",
        "google-genai": "google.genai",
        "python-dotenv": "dotenv",
        "scikit-learn": "sklearn",
        "google-api-python-client": "googleapiclient",
        "google-auth-httplib2": "google.auth",
        "google-auth-oauthlib": "google.auth",
        "edge-tts": "edge_tts",
        "pillow": "PIL",
        "ddgs": "duckduckgo_search",
        "pywin32": "win32api",
        "beautifulsoup4": "bs4",
        "faiss-cpu": "faiss",
        "APScheduler": "apscheduler",
        "PyAutoGUI": "pyautogui",
        "PyGetWindow": "pygetwindow",
        "PyMsgBox": "pymsgbox",
        "PyRect": "pyrect",
        "PyScreeze": "pyscreeze",
        "PyJWT": "jwt",
        "RapidFuzz": "rapidfuzz",
        "MouseInfo": "mouseinfo",
        "python-dateutil": "dateutil",
        "python-docx": "docx",
        "python-engineio": "engineio",
        "python-socketio": "socketio",
        "python-pptx": "pptx",
        "python-slugify": "slugify",
        "google-ai-generativelanguage": "google.ai.generativelanguage",
        "google-api-core": "google.api_core",
        "google-generativeai": "google.generativeai",
        "googleapis-common-protos": "google.api_core",
        "googlesearch-python": "googlesearch",
        "grpcio": "grpc",
        "grpcio-status": "grpc_status",
        "Jinja2": "jinja2",
        "MarkupSafe": "markupsafe",
        "Werkzeug": "werkzeug",
        "proto-plus": "proto",
        "protobuf": "google.protobuf",
        "pywin32-ctypes": "win32ctypes",
        "rpds-py": "rpds",
        "markdown-it-py": "markdown_it",
        "Flask-SocketIO": "flask_socketio",
        "Flask-Cors": "flask_cors",
        "gevent-websocket": "geventwebsocket",
        "pycryptodome": "Crypto",
        "PyYAML": "yaml",
        "websocket-client": "websocket",
        "python-multipart": "multipart",
        "qdrant-client": "qdrant_client",
        # --- pip 名 ≈ import 名 (fallback 給 replace("-","_")) ---
        "mcp": "mcp",
        "googlesearch": "googlesearch",
        "pynput": "pynput",
        "pyautogui": "pyautogui",
        "pygetwindow": "pygetwindow",
        "jieba": "jieba",
        "yfinance": "yfinance",
        "duckdb": "duckdb",
        "openai": "openai",
        "flask": "flask",
        "watchdog": "watchdog",
        "Eel": "eel",
        "Pygments": "pygments",
        "fonttools": "fonttools",
        "aiofiles": "aiofiles",
        "cryptography": "cryptography",
    }

    import_name = mapping.get(cleaned, cleaned.replace("-", "_"))
    return (cleaned, import_name)


def _is_installed(pip_name: str, import_name: str) -> bool:
    """雙重驗證套件是否已安裝：先嘗試 import，失敗則查 metadata"""
    try:
        importlib.import_module(import_name.split(".")[0])
        return True
    except (ImportError, ModuleNotFoundError):
        pass
    try:
        from importlib.metadata import distribution
        distribution(pip_name)
        return True
    except Exception:
        pass
    return False


def check_python():
    """檢查 Python 版本"""
    print(f"\n{BOLD}═══ Python 版本檢查 ═══{RESET}")
    ver = sys.version_info
    ver_str = f"{ver.major}.{ver.minor}.{ver.micro}"
    if ver >= (3, 11):
        print(f"  {PASS} Python {ver_str} (>= 3.11 符合)")
        return True
    elif ver >= (3, 9):
        print(f"  {WARN} Python {ver_str} (< 3.11，可能部分功能異常)")
        return True
    else:
        print(f"  {FAIL} Python {ver_str} (< 3.9，無法執行 Alice！)")
        return False


def check_pip():
    """檢查 pip 可用性"""
    print(f"\n{BOLD}═══ pip 檢查 ═══{RESET}")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, check=True
        )
        print(f"  {PASS} pip 可用")
        return True
    except Exception:
        print(f"  {FAIL} pip 無法使用")
        return False


def check_dependencies(requirements_path="requirements.txt", auto_install=True):
    """檢查依賴套件，可選自動安裝"""
    print(f"\n{BOLD}═══ 依賴套件檢查 ═══{RESET}")

    if not os.path.exists(requirements_path):
        print(f"  {FAIL} {requirements_path} 不存在！")
        return False

    with open(requirements_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    missing = []
    ok = []

    for line in lines:
        parsed = parse_requirement(line)
        if not parsed:
            continue
        pip_name, import_name = parsed
        try:
            if _is_installed(pip_name, import_name):
                ok.append(pip_name)
            else:
                missing.append((pip_name, import_name))
        except Exception:
            ok.append(pip_name)

    print(f"  {INFO} 已安裝: {len(ok)} 個")
    for pkg in ok:
        print(f"     {PASS} {pkg}")

    if not missing:
        print(f"\n  {PASS} 所有 {len(ok)} 個依賴套件已就緒")
        return True

    print(f"\n  {WARN} 缺失: {len(missing)} 個")
    for pip_name, import_name in missing:
        print(f"     {FAIL} {pip_name}")

    if auto_install:
        print(f"\n  {INFO} 自動安裝缺失套件...")
        failed = []
        for pip_name, import_name in missing:
            print(f"     📦 安裝 {pip_name}...", end=" ")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pip_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                # 驗證
                if _is_installed(pip_name, import_name):
                    print(f"{PASS}")
                else:
                    print(f"{FAIL} (匯入驗證失敗)")
                    failed.append(pip_name)
            except subprocess.CalledProcessError:
                print(f"{FAIL}")
                failed.append(pip_name)

        if failed:
            print(f"\n  {FAIL} {len(failed)} 個套件安裝失敗: {', '.join(failed)}")
            print(f"  {INFO} 請手動執行: pip install -r {requirements_path}")
            return False
        else:
            print(f"\n  {PASS} 全部安裝成功")
            return True
    else:
        print(f"\n  {INFO} 請執行: pip install -r {requirements_path}")
        return False


def check_files():
    """檢查關鍵檔案"""
    print(f"\n{BOLD}═══ 關鍵檔案檢查 ═══{RESET}")

    all_ok = True

    for filename, desc in CRITICAL_FILES:
        if os.path.exists(filename):
            print(f"  {PASS} {filename} ({desc})")
        else:
            print(f"  {FAIL} {filename} ({desc}) — 必要！")
            all_ok = False

    for filename, desc in OPTIONAL_FILES:
        if os.path.exists(filename):
            print(f"  {PASS} {filename} ({desc})")
        else:
            print(f"  {WARN} {filename} ({desc}) — 選填，可能部分功能受限")

    return all_ok


def check_dirs():
    """檢查目錄結構"""
    print(f"\n{BOLD}═══ 目錄結構檢查 ═══{RESET}")

    all_ok = True
    for dirname, desc in REQUIRED_DIRS:
        if os.path.isdir(dirname):
            print(f"  {PASS} {dirname} ({desc})")
        else:
            print(f"  {WARN} {dirname} ({desc}) — 目錄不存在，將自動建立")
            try:
                os.makedirs(dirname, exist_ok=True)
                print(f"     → 已建立 {dirname}")
            except Exception:
                print(f"     {FAIL} 無法建立目錄")
                all_ok = False

    return all_ok


def check_disk_space():
    """檢查磁碟空間"""
    print(f"\n{BOLD}═══ 磁碟空間檢查 ═══{RESET}")

    try:
        current_dir = os.path.abspath(".")
        # Windows: 取得磁碟代號
        if os.name == "nt":
            drive = os.path.splitdrive(current_dir)[0] + "\\"
        else:
            drive = "/"

        usage = shutil.disk_usage(drive)
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)

        print(f"  {INFO} 磁碟: {drive} ({total_gb:.0f} GB)")
        print(f"  {INFO} 可用空間: {free_gb:.1f} GB")

        if free_gb < 1:
            print(f"  {FAIL} 可用空間 < 1GB，可能影響運行")
            return False
        elif free_gb < 5:
            print(f"  {WARN} 可用空間 < 5GB，建議清理")
        else:
            print(f"  {PASS} 空間充裕")

        return True
    except Exception as e:
        print(f"  {WARN} 無法檢查: {e}")
        return True  # 不阻擋


def check_ollama():
    """檢查 Ollama 本體 + nomic-embed-text 模型（記憶系統向量化引擎）"""
    print(f"\n{BOLD}═══ Ollama 記憶引擎檢查 ═══{RESET}")

    # 1. 檢查 ollama 命令是否可用
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            ver = result.stdout.strip()
            print(f"  {PASS} Ollama 已安裝: {ver}")
        else:
            print(f"  {FAIL} Ollama 未安裝或無法執行")
            print(f"  {INFO} 請從 https://ollama.com/download 下載安裝")
            return False
    except FileNotFoundError:
        print(f"  {FAIL} Ollama 未安裝（找不到 ollama 命令）")
        print(f"  {INFO} 請從 https://ollama.com/download 下載安裝")
        return False
    except Exception as e:
        print(f"  {FAIL} Ollama 檢查失敗: {e}")
        return False

    # 2. 檢查 nomic-embed-text 模型
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=15
        )
        if "nomic-embed-text" in result.stdout:
            print(f"  {PASS} nomic-embed-text 模型已就緒 (768d 向量)")
        else:
            print(f"  {WARN} nomic-embed-text 模型未下載 (約 274MB)")
            print(f"  {INFO} 自動下載中...")
            dl = subprocess.run(
                ["ollama", "pull", "nomic-embed-text"],
                capture_output=True, text=True, timeout=300
            )
            if dl.returncode == 0:
                print(f"  {PASS} nomic-embed-text 模型下載完成")
            else:
                print(f"  {FAIL} 模型下載失敗: {dl.stderr.strip()[:200] if dl.stderr else '未知錯誤'}")
                print(f"  {INFO} 請手動執行: ollama pull nomic-embed-text")
                return False
    except Exception as e:
        print(f"  {FAIL} 模型檢查失敗: {e}")
        return False

    return True


def sync_requirements(output_path="requirements.txt"):
    """自動更新 requirements.txt — 每次檢查通過後執行 pip freeze"""
    print(f"\n{BOLD}═══ 同步依賴清單 ═══{RESET}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=True
        )
        current_packages = result.stdout.strip()
        package_count = len(current_packages.split("\n")) if current_packages else 0

        # 讀取現有檔案
        old_content = ""
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                old_content = f.read().strip()

        if old_content == current_packages:
            print(f"  {PASS} requirements.txt 已是最新 ({package_count} 個套件)")
            return True

        # 寫入新內容
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(current_packages + "\n")

        old_count = len(old_content.split("\n")) if old_content else 0
        print(f"  {PASS} requirements.txt 已更新: {old_count} → {package_count} 個套件")
        return True

    except subprocess.CalledProcessError as e:
        print(f"  {FAIL} pip freeze 失敗: {e}")
        return False
    except IOError as e:
        print(f"  {FAIL} 寫入 {output_path} 失敗: {e}")
        return False


def detect_portable_drive():
    """偵測是否在隨身硬碟上運行"""
    current = os.path.abspath(".")
    if os.name == "nt":
        drive = os.path.splitdrive(current)[0]
        # 簡單偵測：路徑中是否包含非標準磁碟
        print(f"\n{BOLD}═══ 運行環境 ═══{RESET}")
        print(f"  {INFO} 當前路徑: {current}")
        print(f"  {INFO} 磁碟代號: {drive}")

        # 檢查是否在常見的固定磁碟上
        fixed_drives = ["C:", "D:", "E:"]
        drive_upper = drive.upper() + ":"
        if drive_upper not in fixed_drives or "USB" in current.upper() or "隨身" in current:
            print(f"  {INFO} 偵測到可攜式儲存裝置 (隨身碟/外接硬碟)")
            return True
        else:
            print(f"  {INFO} 一般固定磁碟")
            return False
    return False


def run_full_check(requirements_path="requirements.txt", auto_install=True):
    """執行完整環境檢查"""
    print(f"{BOLD}{CYAN}")
    print("╔══════════════════════════════════╗")
    print("║     Alice 環境檢查 v1.0         ║")
    print("╚══════════════════════════════════╝")
    print(f"{RESET}")

    is_portable = detect_portable_drive()

    checks = [
        ("Python 版本", check_python()),
        ("pip 可用性", check_pip()),
        ("Ollama 記憶引擎", check_ollama()),
        ("依賴套件", check_dependencies(requirements_path, auto_install)),
        ("關鍵檔案", check_files()),
        ("目錄結構", check_dirs()),
        ("磁碟空間", check_disk_space()),
    ]

    all_passed = all(result for _, result in checks)

    print(f"\n{BOLD}{'═══' * 12}{RESET}")
    print(f"{BOLD}檢查總結:{RESET}")
    for name, result in checks:
        icon = PASS if result else FAIL
        print(f"  {icon} {name}")

    if all_passed:
        # ✨ 自動同步 requirements.txt
        sync_requirements(requirements_path)

        print(f"\n  {PASS} {BOLD}{GREEN}環境檢查全數通過！Alice 可以啟動。{RESET}")
        if is_portable:
            print(f"  {INFO} 檢測到隨身碟模式，所有依賴已就緒。")
    else:
        print(f"\n  {FAIL} {BOLD}{RED}部分檢查失敗，請修正後再試。{RESET}")

    return all_passed


if __name__ == "__main__":
    # 從命令列參數決定是否自動安裝
    auto = "--no-install" not in sys.argv
    req_file = "requirements.txt"

    # 允許指定 requirements 檔案路徑
    for i, arg in enumerate(sys.argv):
        if arg == "--requirements" and i + 1 < len(sys.argv):
            req_file = sys.argv[i + 1]

    success = run_full_check(requirements_path=req_file, auto_install=auto)

    if not success:
        print(f"\n{RED}請修正上述問題後重新執行。{RESET}")
        print(f"若需跳過自動安裝: python setup_check.py --no-install")

    sys.exit(0 if success else 1)
