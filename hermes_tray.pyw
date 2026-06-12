
"""Hermes Gateway 系統列小工具 v3 — 精準殺，不波及 agent session"""
import os, sys, subprocess, threading, time
import pystray
from PIL import Image, ImageDraw

HERMES_HOME = os.path.expandvars(r"%LOCALAPPDATA%\hermes\hermes-agent")
VENV_PYTHONW = os.path.join(HERMES_HOME, "venv", "Scripts", "pythonw.exe")
PROFILE = "alice"
PORT = 9120


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
ICON_RESTART = _make_icon("#f59e0b")


def _get_port_pid() -> str:
    """找出佔用 port 的 PID"""
    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=3)
        for line in r.stdout.splitlines():
            if f":{PORT}" in line and "LISTENING" in line:
                return line.strip().split()[-1]
    except Exception:
        pass
    return ""


def gateway_running() -> bool:
    return bool(_get_port_pid())


def _kill_gateway_ony():
    """只殺佔用 port 9120 的那一個行程，不波及 agent session"""
    pid = _get_port_pid()
    if pid:
        subprocess.run(["taskkill", "/f", "/pid", pid], capture_output=True)
        time.sleep(1)


def start_gateway():
    if gateway_running():
        return  # 已經在跑就不重複開
    subprocess.Popen(
        [VENV_PYTHONW, "-m", "hermes_cli.main", "gateway", "run", "--profile", PROFILE],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def stop_gateway():
    _kill_gateway_ony()


def restart_gateway():
    _kill_gateway_ony()
    time.sleep(2)
    start_gateway()


def on_click(icon: pystray.Icon, item):
    action = str(item)
    if "啟動" in action:
        icon.icon = ICON_RESTART
        start_gateway()
        time.sleep(3)
    elif "停止" in action:
        stop_gateway()
        time.sleep(1)
    elif "重新啟動" in action:
        icon.icon = ICON_RESTART
        restart_gateway()
        time.sleep(3)
    elif "離開" in action:
        icon.stop()
        return
    icon.icon = ICON_RUNNING if gateway_running() else ICON_STOPPED
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


class TrayApp:
    def __init__(self):
        self.icon = pystray.Icon("hermes_gateway", ICON_STOPPED, "Hermes Gateway", menu=build_menu())
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
