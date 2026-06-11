#!/usr/bin/env python3
"""雙向同步：先 pull（含版本覆蓋）→ 再 push 本地新記憶上 GitHub"""
import subprocess
import sys
from pathlib import Path

script_dir = Path(__file__).parent
sync_script = script_dir / "sync_memory_github.py"

# Step 1: pull（含 .version 覆蓋機制）
r1 = subprocess.run(
    [sys.executable, str(sync_script), "pull"],
    capture_output=True, text=True, timeout=60
)
if r1.stdout:
    print(r1.stdout.strip())

# Step 2: push 本地新記憶上去
r2 = subprocess.run(
    [sys.executable, str(sync_script), "push"],
    capture_output=True, text=True, timeout=60
)
if r2.stdout:
    print(r2.stdout.strip())

sys.exit(0 if r1.returncode == 0 and r2.returncode == 0 else 1)
