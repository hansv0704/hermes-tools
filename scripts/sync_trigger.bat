@echo off
REM B端記憶同步 — 由 Windows Task Scheduler 觸發，不經過 Hermes Gateway
set HERMES_WORKSPACE=C:\Users\User\Desktop\Hermes工具區
set PYTHONIOENCODING=utf-8
"C:\Users\User\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe" "C:\Users\User\AppData\Local\hermes\profiles\alice\scripts\sync_memory_bidirectional.py"
