"""
精準編輯技能 (Precision Editor Skill)
提供 replace_in_file 與 apply_diff 兩個精準檔案編輯工具。
避免全檔覆寫，大幅降低 Token 消耗與誤刪風險。
"""

import os
import re
import difflib
from skills.base_skill import BaseSkill


class PrecisionEditorSkill(BaseSkill):
    def __init__(self, agent=None):
        super().__init__(agent)
        self._name = "precision_editor_skill"

    @property
    def name(self) -> str:
        return self._name

    def get_tool_declarations(self):
        return [
            {
                "name": "replace_in_file",
                "description": "【精準編輯】在檔案中精準替換第一處匹配的字串。僅修改目標區塊，不影響其他內容。類似 Aider 的 search/replace 機制。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "目標檔案路徑"},
                        "old_string": {"type": "string", "description": "要被替換的原始字串（必須完全精準匹配，含縮排與換行）"},
                        "new_string": {"type": "string", "description": "替換後的新字串"}
                    },
                    "required": ["file_path", "old_string", "new_string"]
                }
            },
            {
                "name": "apply_diff",
                "description": "【差異補丁】將 Unified Diff 格式的補丁打入目標檔案。適合多處修改、區塊搬移等複雜操作。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "目標檔案路徑"},
                        "diff_content": {"type": "string", "description": "Unified Diff 格式的補丁內容"}
                    },
                    "required": ["file_path", "diff_content"]
                }
            }
        ]

    def execute(self, tool_name, params, context=None, **kwargs):
        if tool_name == "replace_in_file":
            return self._replace_in_file(
                params.get("file_path", ""),
                params.get("old_string", ""),
                params.get("new_string", "")
            )
        elif tool_name == "apply_diff":
            return self._apply_diff(
                params.get("file_path", ""),
                params.get("diff_content", "")
            )
        else:
            return {"status": "error", "message": f"未知工具: {tool_name}"}

    # ─── replace_in_file ────────────────────────────────────────

    def _replace_in_file(self, file_path: str, old_string: str, new_string: str) -> dict:
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"❌ 檔案不存在: {file_path}"}

        if not old_string:
            return {"status": "error", "message": "❌ old_string 不可為空"}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return {"status": "error", "message": f"❌ 讀取檔案失敗: {e}"}

        # 計算 old_string 出現次數
        count = content.count(old_string)
        if count == 0:
            return {
                "status": "error",
                "message": f"❌ 在檔案中找不到 old_string（0 次匹配）。請用 view_source_code 確認當前內容後重試。",
                "hint": "old_string 必須完全精準匹配，包含縮排、換行、標點符號。"
            }
        if count > 1:
            return {
                "status": "error",
                "message": f"❌ old_string 在檔案中出現 {count} 次（非唯一匹配）。請提供更長的上下文使其唯一。",
                "count": count
            }

        original_len = len(content)
        new_content = content.replace(old_string, new_string, 1)
        new_len = len(new_content)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return {"status": "error", "message": f"❌ 寫入檔案失敗: {e}"}

        return {
            "status": "success",
            "message": f"✅ 精準替換完成！",
            "file_path": file_path,
            "original_chars": original_len,
            "new_chars": new_len,
            "diff_chars": new_len - original_len,
            "matched_count": 1
        }

    # ─── apply_diff ──────────────────────────────────────────────

    def _apply_diff(self, file_path: str, diff_content: str) -> dict:
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"❌ 檔案不存在: {file_path}"}

        if not diff_content.strip():
            return {"status": "error", "message": "❌ diff_content 不可為空"}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()
        except Exception as e:
            return {"status": "error", "message": f"❌ 讀取檔案失敗: {e}"}

        original_len = sum(len(l) for l in original_lines)

        try:
            # 解析 diff，過濾掉非標準行
            diff_lines = diff_content.splitlines(keepends=True)
            # 過濾掉可能的垃圾行（如 ```diff 標記）
            cleaned_diff = []
            for line in diff_lines:
                if line.startswith(("--- ", "+++ ", "@@ ", "+", "-", " ")) or line == "\n":
                    cleaned_diff.append(line)

            patched = list(difflib.restore(
                difflib.unified_diff([], []),  # dummy
                1
            ))

            # 改用手動打入補丁
            patched_lines = self._manual_patch(original_lines, cleaned_diff)
            if patched_lines is None:
                return {"status": "error", "message": "❌ 補丁打入失敗：上下文不匹配，請確認檔案當前內容與 diff 基準一致。"}

        except Exception as e:
            return {"status": "error", "message": f"❌ diff 解析失敗: {e}"}

        new_content = "".join(patched_lines)
        new_len = len(new_content)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return {"status": "error", "message": f"❌ 寫入檔案失敗: {e}"}

        return {
            "status": "success",
            "message": f"✅ 差異補丁打入完成！",
            "file_path": file_path,
            "original_chars": original_len,
            "new_chars": new_len,
            "diff_chars": new_len - original_len,
            "hunks_applied": sum(1 for l in cleaned_diff if l.startswith("@@"))
        }

    def _manual_patch(self, original_lines, diff_lines):
        """手動打入 Unified Diff 補丁"""
        result = list(original_lines)
        hunk_info = None
        src_line = dst_line = 0

        for line in diff_lines:
            if line.startswith("@@"):
                # 解析 hunk header: @@ -src,count +dst,count @@
                match = re.match(r"@@ -(\d+),?\d* \+(\d+),?\d* @@", line)
                if match:
                    src_line = int(match.group(1)) - 1  # 0-indexed
                    dst_line = int(match.group(2)) - 1
                hunk_info = {"src": src_line, "dst": dst_line}
            elif hunk_info is not None:
                if line.startswith(" "):
                    dst_line += 1
                elif line.startswith("-"):
                    if src_line < len(result):
                        del result[src_line]
                    # 不增加 dst_line
                elif line.startswith("+"):
                    result.insert(dst_line, line[1:])
                    dst_line += 1
                    src_line += 1

        return result
