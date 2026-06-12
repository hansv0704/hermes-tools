
"""Hermes Gateway 系統列小工具 v2 — 桌面工作列從此乾淨"""
import os
import sys
import subprocess
import threading
import time

import pystray
from PIL import Image, ImageDraw

HERMES_HOME = os.path.expandvars(r"%LOCALAPPDATA%\hermes\hermes-agent")
VENV_PYTHONW = os.path.join(HERMES_HOME, "venv", "Scripts", "pythonw.exe")
PROFILE = "alice"
PORT = 9120


# ── 圖示產生 ──────────────────────────────────────
def _make_icon(color: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=color)
    draw.line([(18, 18), (18, 46)], fill="white", width=5)
    draw.line([(46, 18), (46, 46)], fill="white", width=5)
    draw.line([(18, 32), (46, 32)], fill="white", width=5)
    return img

ICON_RUNNING = _make_icon("#22c55e")
ICON_STOPPED = _make_icon("#6b7280")
ICON_RESTART = _make_icon("#f59e0b")  # 黃 = 重啟中


# ── Gateway 控制 ──────────────────────────────────
def gateway_running() -> bool:
    try:
        r = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=3
        )
        return f":{PORT}" in r.stdout and "LISTENING" in r.stdout
    except Exception:
        return False


def _kill_all_gateways():
    """殺光所有 gateway 相關行程（python + hermes + pythonw），除了自己"""
    my_pid = str(os.getpid())
    # 先殺後端行程
    for name in ["python.exe", "pythonw.exe", "hermes.exe"]:
        subprocess.run(
            ["taskkill", "/f", "/fi", f"PID ne {my_pid}", "/im", name],
            capture_output=True,
        )


def start_gateway():
    _kill_all_gateways()
    time.sleep(2)
    subprocess.Popen(
        [VENV_PYTHONW, "-m", "hermes_cli.main", "gateway", "run", "--profile", PROFILE],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def stop_gateway():
    _kill_all_gateways()


# ── 系統列選單 ────────────────────────────────────
def on_click(icon: pystray.Icon, item):
    action = str(item)
    if "啟動" in action:
        icon.icon = ICON_RESTART
        start_gateway()
        time.sleep(3)
        icon.icon = ICON_RUNNING if gateway_running() else ICON_STOPPED
    elif "停止" in action:
        stop_gateway()
        time.sleep(1)
        icon.icon = ICON_STOPPED
    elif "重新啟動" in action:
        icon.icon = ICON_RESTART
        stop_gateway()
        time.sleep(1)
        start_gateway()
        time.sleep(3)
        icon.icon = ICON_RUNNING if gateway_running() else ICON_STOPPED
    elif "離開" in action:
        icon.stop()
    # 重建選單
    if icon.visible:
        icon.menu = build_menu()


def build_menu():
    running = gateway_running()
    status = "🟢 Gateway 執行中" if running else "⚫ Gateway 已停止"
    return pystray.Menu(
        pystray.MenuItem(status, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("重新啟動 Gateway", on_click),
        pystray.MenuItem("停止 Gateway", on_click, enabled=running),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("離開", on_click),
    )


# ── 主程式 ────────────────────────────────────────
class TrayApp:
    def __init__(self):
        self.icon = pystray.Icon(
            "hermes_gateway",
            ICON_STOPPED,
            "Hermes Gateway",
            menu=build_menu(),
        )
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def _poll(self):
        while self._running:
            if self.icon.visible:
                self.icon.icon = ICON_RUNNING if gateway_running() else ICON_STOPPED
                self.icon.menu = build_menu()
            time.sleep(3)

    def run(self):
        self._thread.start()
        # 啟動時：如果沒有 gateway 在跑就自動啟動
        if not gateway_running():
            self.icon.icon = ICON_RESTART
            start_gateway()
            time.sleep(3)
        self.icon.icon = ICON_RUNNING if gateway_running() else ICON_STOPPED
        self.icon.menu = build_menu()
        self.icon.run()


if __name__ == "__main__":
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "HermesGatewayTray")
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(0, "Hermes Gateway 已經在系統列執行了", "Hermes", 0)
        sys.exit(0)
    TrayApp().run()
