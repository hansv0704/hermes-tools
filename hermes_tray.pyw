
"""Hermes Gateway 系統列小工具 — 桌面工作列從此乾淨"""
import os
import sys
import subprocess
import threading
import time
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

HERMES_HOME = os.path.expandvars(r"%LOCALAPPDATA%\hermes\hermes-agent")
VENV_PYTHON = os.path.join(HERMES_HOME, "venv", "Scripts", "pythonw.exe")
PROFILE = "alice"
PORT = 9120


# ── 圖示產生 ──────────────────────────────────────
def _make_icon(color: str) -> Image.Image:
    """產生 64x64 的 H 圖示，顏色代表狀態"""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = 12
    draw.rounded_rectangle([4, 4, 60, 60], radius=r, fill=color)
    # 畫 H
    draw.line([(18, 18), (18, 46)], fill="white", width=5)
    draw.line([(46, 18), (46, 46)], fill="white", width=5)
    draw.line([(18, 32), (46, 32)], fill="white", width=5)
    return img


ICON_RUNNING = _make_icon("#22c55e")  # 綠
ICON_STOPPED = _make_icon("#6b7280")  # 灰


# ── Gateway 控制 ──────────────────────────────────
def gateway_running() -> bool:
    try:
        r = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=3,
        )
        return f":{PORT}" in r.stdout and "LISTENING" in r.stdout
    except Exception:
        return False


def start_gateway():
    if gateway_running():
        return
    subprocess.Popen(
        [VENV_PYTHON, "-m", "hermes_cli.main", "gateway", "run", "--profile", PROFILE],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
    )


def stop_gateway():
    if not gateway_running():
        return
    subprocess.run(
        ["taskkill", "/f", "/fi", f"PID ne {os.getpid()}", "/im", "pythonw.exe"],
        capture_output=True,
    )
    subprocess.run(
        ["taskkill", "/f", "/im", "hermes.exe"],
        capture_output=True,
    )


# ── 系統列 ────────────────────────────────────────
def update_icon(icon: pystray.Icon):
    running = gateway_running()
    icon.icon = ICON_RUNNING if running else ICON_STOPPED
    return running


def on_click(icon: pystray.Icon, item):
    if item.text == "啟動 Gateway":
        start_gateway()
        time.sleep(2)
        update_icon(icon)
    elif item.text == "停止 Gateway":
        stop_gateway()
        time.sleep(1)
        update_icon(icon)
    elif item.text == "退出":
        icon.stop()


def make_menu(icon: pystray.Icon):
    running = gateway_running()
    status_text = "🟢 Gateway 執行中" if running else "⚫ Gateway 已停止"
    return pystray.Menu(
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("啟動 Gateway", on_click, enabled=not running),
        pystray.MenuItem("停止 Gateway", on_click, enabled=running),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", on_click),
    )


class TrayApp:
    def __init__(self):
        self.icon = pystray.Icon(
            "hermes_gateway",
            ICON_STOPPED,
            "Hermes Gateway",
            menu=make_menu(self),
        )
        # 定時更新圖示
        self._timer_running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def _poll(self):
        while self._timer_running:
            if self.icon.visible:
                self.icon.icon = (
                    ICON_RUNNING if gateway_running() else ICON_STOPPED
                )
                # 重建選單（更新啟用/停用狀態）
                self.icon.menu = make_menu(self)
            time.sleep(3)

    def run(self):
        self._thread.start()
        # 啟動時順便確保 gateway 在跑
        if not gateway_running():
            start_gateway()
            time.sleep(3)
        self.icon.run()

    def make_menu(self) -> pystray.Menu:
        return make_menu(self.icon)


if __name__ == "__main__":
    # 防止重複啟動
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "HermesGatewayTray")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(0, "Hermes Gateway 已經在系統列執行了", "Hermes", 0)
        sys.exit(0)

    TrayApp().run()
