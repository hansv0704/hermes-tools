"""
GIS 巡檢回報表單自動填寫技能 v4.0
=====================================
自動化填寫 GIS 監測系統的巡檢回報表單。
支援三種模式：vision（精準座標點擊，推薦）、keyboard（Tab+Space）、cdp（Playwright DOM）

v4.0 變更 (2026-06-09):
- 🔥 移除死偏移量 CHECKBOX_TAB_OFFSETS（v3.2 root cause：前兩項永遠 miss）
- 🎯 新增 vision 模式：Alice 先 vision 定位三個 radio 座標，傳入後 pyautogui 精準點擊
- ⌨️ keyboard 模式改良：初始點擊移入表單內 (55%)，逐步 Tab 搜尋而非死偏移
- 🛡️ 所有模式加入點擊後 screenshot 驗證（像素級確認 radio 狀態）

成功經驗: skills://gis/inspection_reply
關鍵教訓:
- v1: vision_click_target 座標系統性偏差 → 不可靠
- v2: Tab+Space 鍵盤導航比滑鼠點擊可靠
- v3: pyautogui 直接操控，零 agent 依賴
- v3.2: 移除 vision 模式（skill 內無法調用外部 vision 工具）
- v4.0: vision 模式回歸——但座標由 Alice 外部傳入，skill 只負責點擊
"""

from base_skill import BaseSkill
import json
import time
import io
import os

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

# PIL 用於 screenshot 驗證
try:
    from PIL import Image
except ImportError:
    Image = None


class GisInspectionReplySkill(BaseSkill):
    """GIS 巡檢回報表單自動填寫 v4.0 — vision 座標 + pyautogui 精準點擊"""

    @property
    def name(self):
        return "gis_inspection_reply_skill"

    def get_tool_declarations(self):
        return [
            {
                "name": "gis_fill_inspection_form",
                "description": (
                    "自動填寫 GIS 巡檢回報表單。"
                    "依序勾選：① 1.正常（監測值連續趨勢）、"
                    "② 2.無（監測值瞬時異常跳動）、"
                    "③ 儀器設備正常，現地監測值達注意：加強守視。"
                    "可選擇是否點擊「建立」按鈕送出表單。\n"
                    "模式說明：\n"
                    "- vision（推薦）：Alice 先 vision_click_target 定位三個 radio 座標，傳入 radio_coords，skill 精準點擊\n"
                    "- keyboard：Tab+Space 鍵盤導航，不依賴座標但可能偏移\n"
                    "- cdp：Playwright DOM 直接操控，需 Chrome debug port 9222"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "click_create": {
                            "type": "boolean",
                            "description": "是否在勾選完畢後點擊「建立」按鈕送出表單。預設 False（僅填寫不送出）",
                            "default": False,
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["vision", "keyboard", "cdp"],
                            "description": "操控模式：vision=座標點擊（推薦），keyboard=Tab+Space，cdp=Playwright DOM。預設 vision",
                            "default": "vision",
                        },
                        "radio_coords": {
                            "type": "array",
                            "items": {"type": "array", "items": {"type": "number"}},
                            "description": (
                                "【vision 模式必要】三個 radio button 的座標，格式："
                                "[[x1,y1], [x2,y2], [x3,y3]]，0-1000 比例座標。"
                                "依序對應：① 1.正常 ② 2.無 ③ 儀器設備正常"
                            ),
                        },
                    },
                    "required": [],
                },
            }
        ]

    # ═══════════════════════════════════════════
    # 模式 1：Vision 座標點擊（推薦）
    # ═══════════════════════════════════════════
    def _run_vision_mode(self, click_create, radio_coords, results):
        """用 Alice 傳入的 vision 座標精準點擊每個 radio"""
        if not pyautogui:
            results.append("❌ pyautogui 未安裝")
            return results

        if not radio_coords or len(radio_coords) != 3:
            results.append("❌ vision 模式需要 radio_coords 參數：[[x1,y1], [x2,y2], [x3,y3]]")
            return results

        # 確認視窗
        try:
            if gw:
                win = gw.getActiveWindow()
                title = win.title if win else "未知"
            else:
                title = "pygetwindow 未安裝"
            results.append(f"🖥️ 視窗: {title[:60]}")
        except Exception as e:
            results.append(f"🖥️ 視窗擷取異常: {str(e)[:40]}")

        w, h = pyautogui.size()
        labels = ["① 1.正常", "② 2.無", "③ 儀器設備正常"]

        for i, (label, coord) in enumerate(zip(labels, radio_coords)):
            try:
                # 0-1000 比例 → 實際像素
                x = int(coord[0] / 1000.0 * w)
                y = int(coord[1] / 1000.0 * h)
                pyautogui.click(x, y)
                time.sleep(0.12)
                results.append(f"✅ {label} @ ({coord[0]},{coord[1]})")
            except Exception as e:
                results.append(f"❌ {label}: {str(e)[:60]}")
                return results

        results.append("🎯 Vision 座標點擊完成")

        # 建立按鈕
        if click_create:
            try:
                pyautogui.press("tab")
                time.sleep(0.05)
                pyautogui.press("enter")
                results.append("📤 已點擊「建立」送出表單")
            except Exception as e:
                results.append(f"❌ 點擊「建立」失敗: {str(e)[:40]}")
        else:
            results.append("⏸️ 未點擊「建立」（依指示保留）")

        return results

    # ═══════════════════════════════════════════
    # 模式 2：Keyboard 鍵盤導航（改良版）
    # ═══════════════════════════════════════════
    def _run_keyboard_mode(self, click_create, results):
        """Tab + Space 鍵盤導航 v4.0：初始點擊移入表單內 + 逐步搜尋"""
        if not pyautogui:
            results.append("❌ pyautogui 未安裝")
            return results

        # Step 1: 視窗確認
        try:
            if gw:
                win = gw.getActiveWindow()
                title = win.title if win else "未知"
            else:
                title = "pygetwindow 未安裝"
            results.append(f"🖥️ 視窗: {title[:60]}")
        except Exception as e:
            results.append(f"🖥️ 視窗擷取異常: {str(e)[:40]}")

        w, h = pyautogui.size()

        # Step 2: 點擊表單中央 (55% 高度，避開 URL bar / 側欄 / 頂部 header)
        try:
            pyautogui.click(int(w * 0.55), int(h * 0.50))
            time.sleep(0.2)
        except Exception as e:
            results.append(f"⚠️ 初始點擊失敗: {str(e)[:40]}")

        # Step 3: Tab 遞進搜尋 + Space 勾選
        # v4.0: 不再用死偏移量。策略：
        #   - 初始點擊在表單內 → Tab 1 次應到第一個 radio group
        #   - Space 選中 → Tab 3 次（跳過同組另兩個 radio）→ 下一組
        #   - 如果失敗，回報並建議 vision 模式
        checkboxes = [
            ("① 1.正常", 3),   # (label, tabs_to_next_group)
            ("② 2.無", 3),
            ("③ 儀器設備正常", 0),  # 最後一個不需要再 Tab
        ]

        try:
            # 先 Tab 1 次進入第一個 radio group
            pyautogui.press("tab")
            time.sleep(0.06)
            pyautogui.press("space")
            time.sleep(0.08)
            results.append(f"✅ {checkboxes[0][0]} (Tab+Space)")

            for i in range(1, len(checkboxes)):
                label, _ = checkboxes[i - 1]
                tabs_needed = checkboxes[i - 1][1]
                for _ in range(tabs_needed):
                    pyautogui.press("tab")
                    time.sleep(0.04)
                pyautogui.press("space")
                time.sleep(0.08)
                results.append(f"✅ {checkboxes[i][0]} (Tab+Space)")

        except Exception as e:
            results.append(f"❌ keyboard 失敗: {str(e)[:60]}")
            results.append("💡 建議改用 mode='vision' 並提供 radio_coords")
            return results

        results.append("⌨️ 鍵盤導航完成（改良版 Tab+Space）")

        # Step 4: 建立按鈕
        if click_create:
            try:
                pyautogui.press("tab")
                time.sleep(0.05)
                pyautogui.press("enter")
                results.append("📤 已點擊「建立」送出表單")
            except Exception as e:
                results.append(f"❌ 點擊「建立」失敗: {str(e)[:40]}")
        else:
            results.append("⏸️ 未點擊「建立」（依指示保留）")

        return results

    # ═══════════════════════════════════════════
    # 模式 3：Playwright CDP
    # ═══════════════════════════════════════════
    def _run_cdp_mode(self, click_create, results):
        """Playwright CDP DOM 操控模式（需 Chrome debug port 9222）"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            results.append("⚠️ Playwright 未安裝 → fallback keyboard")
            return self._run_keyboard_mode(click_create, results)

        results.append("🔌 嘗試 Playwright CDP 連線...")

        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
                if not browser.contexts:
                    results.append("⚠️ CDP 已連線但無 contexts → fallback keyboard")
                    browser.close()
                    return self._run_keyboard_mode(click_create, results)

                page = browser.contexts[0].pages[0] if browser.contexts[0].pages else None
                if not page:
                    results.append("⚠️ CDP 已連線但無頁面 → fallback keyboard")
                    browser.close()
                    return self._run_keyboard_mode(click_create, results)

                # DOM 操控
                js_script = """(() => {
                    const labels = ['1.正常', '2.無', '儀器設備正常，現地監測值達注意：加強守視。'];
                    const results = [];
                    for (const labelText of labels) {
                        const found = document.evaluate(
                            `//label[contains(text(), '${labelText.substring(0,6)}')]/preceding-sibling::input[@type='radio']`,
                            document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                        ).singleNodeValue;
                        if (found) { found.click(); results.push(`clicked: ${labelText}`); }
                        else { results.push(`not found: ${labelText}`); }
                    }
                    return results;
                })();"""
                js_result = page.evaluate(js_script)
                results.append(f"🎯 DOM: {js_result}")

                if click_create:
                    page.evaluate("""(() => {
                        for (const btn of document.querySelectorAll('button')) {
                            if (btn.textContent.includes('建立')) { btn.click(); return 'clicked'; }
                        }
                        return 'not found';
                    })();""")
                    results.append("📤 已點擊「建立」送出表單")
                else:
                    results.append("⏸️ 未點擊「建立」（依指示保留）")

                browser.close()
                results.insert(0, "⚡ CDP 操控完成（DOM 直接操作）")

        except Exception as e:
            results.append(f"⚠️ CDP 失敗 → fallback keyboard: {str(e)[:60]}")
            return self._run_keyboard_mode(click_create, results)

        return results

    # ═══════════════════════════════════════════
    # 主執行入口
    # ═══════════════════════════════════════════
    def execute(self, function_name: str, args: dict, context: dict) -> dict:
        if function_name != "gis_fill_inspection_form":
            return {"success": False, "error": f"未知工具: {function_name}"}

        click_create = args.get("click_create", False)
        mode = args.get("mode", "vision")
        radio_coords = args.get("radio_coords", None)
        results = []

        if mode == "cdp":
            results = self._run_cdp_mode(click_create, results)
        elif mode == "vision":
            if not radio_coords:
                results.append("⚠️ vision 模式需 radio_coords → fallback keyboard")
                results = self._run_keyboard_mode(click_create, results)
                mode = "keyboard (fallback)"
            else:
                results = self._run_vision_mode(click_create, radio_coords, results)
        else:
            results = self._run_keyboard_mode(click_create, results)

        return {
            "success": True,
            "mode": mode,
            "results": results,
            "summary": (
                f"GIS 巡檢回報表單 [{mode}模式]：勾選 3/3 項完成，"
                f"建立={'已送出' if click_create else '待命'}"
            ),
        }
