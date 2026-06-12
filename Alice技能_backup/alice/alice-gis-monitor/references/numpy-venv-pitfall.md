# Numpy Venv 崩潰陷阱

## 症狀

在 Hermes venv 內執行任何依賴 matplotlib 的 Python 腳本時，報錯：

```
AttributeError: module 'numpy._globals' has no attribute '_signature_descriptor'
```

這發生在 `import matplotlib` → `import numpy` → `from numpy._core._multiarray_umath import ...` 的鏈式匯入過程中。

## 原因

Hermes venv 內的 numpy 版本升級後，C extension ABI 與 Python 層的 `_globals` 模組不相容。`_signature_descriptor` 是 numpy 2.x 新增的屬性，舊的編譯版本不認得。

## 修復

```bash
pip install --force-reinstall numpy
```

`--force-reinstall` 是必要的，因為 pip 會跳過「已安裝」的版本，但問題出在 C extension 與純 Python 套件元資料不匹配。

## 影響範圍

- matplotlib 完全無法匯入
- 所有依賴 matplotlib 的程式（含 GIS watchdog 繪圖）全部崩潰
- 不會影響純文字的 Python 腳本

## 觸發條件

- Hermes 或其依賴更新後
- numpy 被其他套件的依賴解析重新安裝後
- 從備份還原 venv 後

## 發生記錄

- 2026-06-11: Hermes venv 內 numpy 2.4.6 崩潰，修復後 watchdog v2.2 成功啟動
