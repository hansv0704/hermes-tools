#!/usr/bin/env python3
"""Gateway watchdog — 每 5 分鐘檢查，掛掉就重啟"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime

HERMES = r"C:\Users\User\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
LOG_FILE = Path.home() / "AppData" / "Local" / "hermes" / "profiles" / "alice" / "logs" / "gateway_watchdog.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# 檢查 gateway
r = subprocess.run(
    [HERMES, "-p", "alice", "gateway", "status"],
    capture_output=True, text=True, timeout=15
)

if "running" in r.stdout.lower():
    # 活著，安靜
    sys.exit(0)

# 掛了 → 重啟
log("Gateway 掛了，重新啟動...")
r2 = subprocess.run(
    [HERMES, "-p", "alice", "gateway", "run"],
    capture_output=True, text=True, timeout=30
)
log(f"Gateway 重啟結果: {r2.stdout.strip() or r2.stderr.strip() or 'OK'}")
