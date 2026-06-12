import sys, os, time, webbrowser
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

try:
    from skills.live_code_studio_skill import _start_server
    
    if __name__ == "__main__":
        daemon_mode = "--daemon" in sys.argv
        
        if daemon_mode:
            log_path = BASE_DIR / "logs" / "lcs_daemon.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(str(log_path), "a", encoding="utf-8")
            sys.stdout = log_file
            sys.stderr = log_file
            print(f"\n=== LCS v5.3 daemon {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        
        if len(sys.argv) > 1 and sys.argv[1] == "--stop":
            import socket, subprocess
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            if sock.connect_ex(('127.0.0.1', 5001)) != 0:
                sock.close()
                print("✅ LCS 未運行"); sys.exit(0)
            sock.close()
            try:
                result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10)
                for line in result.stdout.splitlines():
                    if ":5001" in line:
                        pid = line.strip().split()[-1]
                        if pid != "0":
                            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
                            print(f"✅ 已關閉 PID {pid}")
                            sys.exit(0)
            except Exception as e:
                print(f"❌ {e}")
            sys.exit(0)
        
        import socket, urllib.request
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        if sock.connect_ex(('127.0.0.1', 5001)) == 0:
            sock.close()
            try:
                urllib.request.urlopen("http://localhost:5001/api/tree", timeout=3)
                print("✅ 已在運行中" if not daemon_mode else "")
                if not daemon_mode: webbrowser.open("http://localhost:5001")
                sys.exit(0)
            except: pass
        sock.close()
        
        success, result = _start_server(force=True)
        if success:
            print(f"✅ http://localhost:5001" if not daemon_mode else "")
            if not daemon_mode: webbrowser.open(result)
            try:
                while True: time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 關閉中...")
        else:
            print(f"❌ {result}")

except ImportError as e:
    print(f"❌ {e}")
