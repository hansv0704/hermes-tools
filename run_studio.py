import sys
import os
import time
import webbrowser
from pathlib import Path

# 確保能匯入 skills 資料夾
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

try:
    from skills.live_code_studio_skill import _start_server
    
    if __name__ == "__main__":
        # ── 關閉模式 ──
        if len(sys.argv) > 1 and sys.argv[1] == "--stop":
            print("========================================")
            print("   關閉 Live Code Studio")
            print("========================================")
            import socket, subprocess
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            port_occupied = sock.connect_ex(('127.0.0.1', 5001)) == 0
            sock.close()
            
            if not port_occupied:
                print("\n✅ LCS 未運行，無需關閉。")
                input("\n按任意鍵結束...")
                sys.exit(0)
            
            # 找出佔用 port 5001 的 PID
            try:
                result = subprocess.run(
                    ["netstat", "-ano"], capture_output=True, text=True, timeout=10
                )
                pid = None
                for line in result.stdout.splitlines():
                    if "127.0.0.1:5001" in line or ":5001" in line:
                        parts = line.strip().split()
                        pid = parts[-1]
                        break
                
                if pid and pid != "0":
                    print(f"\n🔍 找到 LCS 進程 PID: {pid}")
                    kill_result = subprocess.run(
                        ["taskkill", "/PID", pid, "/F"],
                        capture_output=True, text=True, timeout=10
                    )
                    print(f"📋 {kill_result.stdout.strip()}")
                    print("\n✅ Live Code Studio 已關閉。")
                else:
                    print("\n⚠️ Port 5001 被佔用但無法識別進程。")
            except Exception as e:
                print(f"\n❌ 關閉失敗: {e}")
            
            input("\n按任意鍵結束...")
            sys.exit(0)
        
        # ── 啟動模式 ──
        print("========================================")
        print("   Live Code Studio v4.0 (獨立進程版)")
        print("========================================")
        print(f"工作目錄: {BASE_DIR}")
        
        # 先檢查 port 5001 是否已被佔用
        import socket, urllib.request
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        port_occupied = sock.connect_ex(('127.0.0.1', 5001)) == 0
        sock.close()
        
        if port_occupied:
            try:
                req = urllib.request.Request("http://localhost:5001/api/tree")
                resp = urllib.request.urlopen(req, timeout=3)
                if resp.status == 200:
                    print("\n✅ Live Code Studio 已在運行中！")
                    print("🌐 正在為您開啟瀏覽器分頁...")
                    webbrowser.open("http://localhost:5001")
                    print("\n提示: 此視窗可安全關閉，不影響已運行的 LCS 服務。")
                    print("\n💡 若要關閉 LCS，請執行「關閉LiveCodeStudio.bat」")
                    input("\n按任意鍵結束...")
                    sys.exit(0)
            except:
                pass
        
        # 啟動伺服器
        success, result = _start_server(force=True)
        
        if success:
            print(f"\n✅ 啟動成功！")
            print(f"🔗 網址: {result}")
            
            print("🌐 正在為您開啟瀏覽器分頁...")
            webbrowser.open(result)
            
            print("\n提示: 此視窗為獨立運行，Alice 重啟不會影響此服務。")
            print("按 Ctrl+C 可關閉此伺服器。")
            print("💡 或執行「關閉LiveCodeStudio.bat」強制關閉。")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 正在關閉 Live Code Studio...")
        else:
            print(f"\n❌ 啟動失敗: {result}")
            input("\n按任意鍵結束...")

except ImportError as e:
    print(f"❌ 匯入失敗: {e}")
    print("請確保 run_studio.py 放在 Alice 專案根目錄下。")
    input("\n按任意鍵結束...")
