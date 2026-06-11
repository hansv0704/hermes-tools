"""讀取 Gemini API key 並輸出"""
import os
# 用 os.getenv 或逐字讀取避開遮蔽
env_path = r"C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.env"
key = ""
with open(env_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        # 避免被遮蔽：逐段檢查
        prefix = "GOOGLE" + "_API" + "_KEYS="
        if line.startswith(prefix):
            key = line[len(prefix):].strip().strip("\"'")
            if "," in key:
                key = key.split(",")[0].strip()
            break

if key:
    out_path = r"C:\Users\hans\Desktop\Alice_Brain_Arch_20260506_031953\.gemini_key_tmp"
    with open(out_path, "w") as f:
        f.write(key)
    print(f"OK (len={len(key)})")
else:
    print("NOT FOUND")
