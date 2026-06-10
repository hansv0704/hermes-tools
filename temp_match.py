import pandas as pd
import os

file_path = r"D:\114年警戒值計畫-20250122T074919Z-001\114年警戒值計畫\降雨重現期分析-20250122T080139Z-001\降雨重現期分析\降雨重現期分析\奕超已完成之重現期_更改1.xlsx"

try:
    # 讀取數據
    xls = pd.ExcelFile(file_path)
    df_target = pd.read_excel(xls, sheet_name='工作表1 (2)')
    df_source = pd.read_excel(xls, sheet_name='水保局全省災害資料')

    # 清洗列名
    df_target.columns = [str(c).strip() for c in df_target.columns]
    df_source.columns = [str(c).strip() for c in df_source.columns]

    # 建立配對 Key
    df_target['_match_key'] = df_target['發生地點'].astype(str).str.strip() + "_" + df_target['事件'].astype(str).str.strip()
    df_source['_match_key'] = df_source['溪流名稱或編號'].astype(str).str.strip() + "_" + df_source['觸發事件'].astype(str).str.strip()

    # 提取崩塌面積
    area_col = '崩塌面積(ha)'
    df_source_sub = df_source[['_match_key', area_col]].copy()
    df_source_sub[area_col] = pd.to_numeric(df_source_sub[area_col], errors='coerce')
    df_source_sub = df_source_sub.dropna(subset=[area_col])
    
    # 去重，取最大值
    df_source_sub = df_source_sub.groupby('_match_key')[area_col].max().reset_index()

    # 合併
    df_result = pd.merge(df_target, df_source_sub, on='_match_key', how='left')
    
    # 處理 "無紀錄"
    df_result[area_col] = df_result[area_col].fillna("無紀錄")
    
    # 移除暫存 Key
    df_result = df_result.drop(columns=['_match_key'])

    # 寫入作業區
    # 由於檔案可能開啟中，我們嘗試使用 openpyxl 寫入特定分頁
    with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df_result.to_excel(writer, sheet_name='作業區', index=False)

    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
