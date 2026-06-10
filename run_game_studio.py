"""
Alice Game Studio — 啟動腳本 (仿 run_studio.py)
獨立進程，不依賴 Alice 重啟

用法:
    python run_game_studio.py           # 啟動
    python run_game_studio.py --stop    # 關閉
"""

import sys
import os
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

if __name__ == "__main__":
    PORT = 5003

    # ── 關閉模式 ──
    if len(sys.argv) > 1 and sys.argv[1] == "--stop":
        print("=" * 40)
        print("   關閉 Alice Game Studio")
        print("=" * 40)
        import socket, subprocess

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        port_occupied = sock.connect_ex(('127.0.0.1', PORT)) == 0
        sock.close()

        if not port_occupied:
            print("\n✅ Game Studio 未運行，無需關閉。")
            input("\n按任意鍵結束...")
            sys.exit(0)

        try:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=10
            )
            pid = None
            for line in result.stdout.splitlines():
                if f"127.0.0.1:{PORT}" in line or f":{PORT}" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    break
            if pid and pid != "0":
                print(f"\n🔍 找到 Game Studio 進程 PID: {pid}")
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                               capture_output=True, text=True, timeout=10)
                print("✅ Alice Game Studio 已關閉。")
            else:
                print(f"\n⚠️ Port {PORT} 被佔用但無法識別進程。")
        except Exception as e:
            print(f"\n❌ 關閉失敗: {e}")

        input("\n按任意鍵結束...")
        sys.exit(0)

    # ── 啟動模式 ──
    print("=" * 40)
    print("   Alice Game Studio v1.0 Phase 1")
    print("=" * 40)
    print(f"工作目錄: {BASE_DIR}")

    # 檢查 port
    import socket, urllib.request
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    port_occupied = sock.connect_ex(('127.0.0.1', PORT)) == 0
    sock.close()

    if port_occupied:
        try:
            req = urllib.request.Request(f"http://localhost:{PORT}/api/health")
            resp = urllib.request.urlopen(req, timeout=3)
            if resp.status == 200:
                print("\n✅ Game Studio 已在運行中！")
                print("🌐 正在為您開啟瀏覽器分頁...")
                webbrowser.open(f"http://localhost:{PORT}")
                print("\n提示: 此視窗可安全關閉。")
                print("💡 若要關閉: python run_game_studio.py --stop")
                input("\n按任意鍵結束...")
                sys.exit(0)
        except:
            pass

    # 啟動
    from studios.studio_manager import start_game_studio
    success, result = start_game_studio(port=PORT)

    if success:
        print(f"\n✅ 啟動成功！")
        print(f"🔗 網址: {result}")

        print("\n提示: 此視窗為獨立運行。按 Ctrl+C 可關閉。")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 正在關閉 Alice Game Studio...")
    else:
        print(f"\n❌ 啟動失敗: {result}")
        input("\n按任意鍵結束...")
