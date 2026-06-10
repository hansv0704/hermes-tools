"""
Gemini Vision Bridge v1.0
- 截圖 → Gemini Flash 分析 → 回傳文字給主模型
- 截圖存於 screenshots/ 目錄
- 自動清理 7 天前的舊截圖
"""
import os, sys, base64, time
from pathlib import Path
from datetime import datetime, timedelta

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

def cleanup_old(days=7):
    """清理 N 天前的舊截圖"""
    cutoff = time.time() - days * 86400
    for f in SCREENSHOT_DIR.glob("*.png"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            print(f"  Cleaned: {f.name}")

def capture_and_analyze(prompt="用繁體中文簡短描述這個網頁截圖的內容"):
    """截圖並用 Gemini Flash 分析"""
    import pyautogui
    from google import genai

    # 讀取 API key
    key = ""
    for ep in [
        Path(os.path.expandvars(r"%USERPROFILE%")) / "Desktop" / "Alice_Brain_Arch_20260506_031953" / ".env",
        Path(os.path.expandvars(r"%LOCALAPPDATA%")) / "hermes" / ".env",
    ]:
        try:
            for line in open(ep, encoding="utf-8"):
                if "GOOGLE" in line and "API_KEYS" in line:
                    key = line.split("=", 1)[1].strip().split(",")[0].strip('"\'').strip()
                    break
        except: pass
        if key: break

    if not key:
        return "ERROR: 找不到 Gemini API key"
    # 截圖（用 PIL 直接抓，比 pyautogui 穩定）
    from PIL import ImageGrab
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ss_path = SCREENSHOT_DIR / f"ss_{timestamp}.png"
    ImageGrab.grab().save(str(ss_path))

    # Gemini 分析
    client = genai.Client(api_key=key)
    with open(ss_path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, {"inline_data": {"mime_type": "image/png", "data": img}}]
    )

    # 清理舊檔
    cleanup_old()

    return f"[截圖: {ss_path.name}]\n{resp.text}"

if __name__ == "__main__":
    cleanup_old()
    prompt = sys.argv[1] if len(sys.argv) > 1 else "用繁體中文簡短描述這個網頁截圖的內容"
    print(capture_and_analyze(prompt))
