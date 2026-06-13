#!/usr/bin/env python3
"""雙向同步：先 pull → 再 push"""
import subprocess
import sys
from pathlib import Path

PYTHONW = r"C:\Users\User\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
script_dir = Path(__file__).parent
sync_script = script_dir / "sync_memory_github.py"

# Windows: 隱藏 subprocess 視窗
if sys.platform == "win32":
    SI = subprocess.STARTUPINFO()
    SI.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    SI.wShowWindow = subprocess.SW_HIDE
else:
    SI = None

# Step 1: pull
r1 = subprocess.run(
    [PYTHONW, str(sync_script), "pull"],
    capture_output=True, text=True, timeout=60,
    startupinfo=SI
)
if r1.stdout:
    print(r1.stdout.strip())

# Step 2: push
r2 = subprocess.run(
    [PYTHONW, str(sync_script), "push"],
    capture_output=True, text=True, timeout=60,
    startupinfo=SI
)
if r2.stdout:
    print(r2.stdout.strip())

# push 失敗通常是無 token，只關心 pull
sys.exit(0 if r1.returncode == 0 else 1)
