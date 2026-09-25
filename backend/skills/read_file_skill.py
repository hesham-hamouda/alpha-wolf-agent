#!/usr/bin/env python3
r"""
Name: read_file_skill
Description: Wraps the read_file tool — reads any file under safe directories.
Description_AR: يلتف حول أداة قراءة الملفات — يقرأ أي ملف داخل المجلدات الآمنة.
Author: Alpha Wolf Team
Version: 1.0.0
Parameters: {"path": "string", "max_size_kb": "integer"}

Iron Laws Applied:
- #15 (Verify)  : returns ToolResult shape, no exceptions escape
- #22 (Autonomous): no prompts — execute immediately
- #33 (Lessons) : bilingual AR+EN docstrings (Iron Law #47)
- #47 (Bilingual): every function has Arabic translation
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

# Make backend importable when skill runs from anywhere
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.agent import tools  # uses _read_file_impl via execute_tool


def run(path: str, max_size_kb: int = 512, **kwargs: Any) -> Dict[str, Any]:
    """Read a file as text. Returns dict with content or error.

    قراءة ملف كنص. يُرجع قاموس يحتوي على المحتوى أو رسالة الخطأ.

    Args:
        path: Absolute or workspace-relative file path | مسار الملف (مطلق أو نسبي)
        max_size_kb: Max file size in KB (default 512) | أقصى حجم بالكيلوبايت

    Returns:
        Dict with keys: success (bool), content (str), size_kb (float), path (str)
        قاموس بمفاتيح: نجاح، محتوى، حجم، مسار
    """
    result = tools.execute_tool("read_file", {"path": path, "max_size_kb": max_size_kb})

    if not result.success:
        return {
            "success": False,
            "error": result.error,
            "path": path,
        }

    return {
        "success": True,
        "path": result.output.get("path", path),
        "content": result.output.get("content", ""),
        "size_kb": result.output.get("size_kb", 0),
    }


if __name__ == "__main__":
    # Self-test (Iron Law #15)
    import tempfile
    tmp = Path(tempfile.gettempdir()) / "read_file_skill_test.txt"
    tmp.write_text("Hello from read_file_skill!", encoding="utf-8")
    out = run(path=str(tmp))
    print(f"Test 1 (read existing): {out}")
    assert out["success"], f"Should succeed: {out}"
    assert "Hello" in out["content"]

    out2 = run(path="/nonexistent/path/file.txt")
    print(f"Test 2 (read missing): {out2}")
    assert not out2["success"], "Should fail"

    tmp.unlink()
    print("✓ read_file_skill self-test PASSED")