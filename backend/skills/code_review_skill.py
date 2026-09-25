#!/usr/bin/env python3
r"""
Name: code_review_skill
Description: Reads a Python file and suggests improvements using the Alpha Wolf model (via backend inference proxy).
Description_AR: يقرأ ملف بايثون ويقترح تحسينات باستخدام نموذج Alpha Wolf.
Author: Alpha Wolf Team
Version: 1.0.0
Parameters: {"path": "string", "focus": "string", "max_lines": "integer"}

Iron Laws Applied:
- #15 (Verify)  : returns structured review dict with sections
- #22 (Autonomous): no prompts — runs end-to-end once invoked
- #33 (Lessons) : bilingual AR+EN output (Iron Law #47)
- #41 (Conflict): surfaces read failures / model timeouts honestly
- #47 (Bilingual): every section has Arabic translation
- #48 (Separated): each step in its own function (read → analyze → format)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make backend importable when skill runs from anywhere
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Local imports — keep this skill decoupled from the orchestrator
from backend.skills.read_file_skill import run as read_file  # re-use file reading


# ============================================================================
# Wolf Personality Review Prompt — keeps Alpha Wolf's voice consistent
# ============================================================================

WOLF_REVIEW_PROMPT = """You are Alpha Wolf Agent — a sharp-eyed code reviewer with 7 wolf traits.
أنت Alpha Wolf Agent — مُراجع كود حاد بسبع صفات للذئب.

Trait #1 — Mistake Hunter (اقتناص الأخطاء): Hunt bugs, anti-patterns, security holes.
Trait #4 — Deep Thinking (التفكير العميق): Think about edge cases, race conditions, error paths.
Trait #5 — Resourceful (استخدام الموارد): Note when stdlib beats third-party.

Review the code below for the focus area: {focus}.
راجع الكود أدناه للمجال: {focus}.

Output format (Markdown):
- 🐺 **Summary** | ملخص (1-2 lines)
- 🐺 **Bugs / Issues** | الأخطاء (numbered list, severity ⚠️/🔥)
- 🐺 **Suggestions** | الاقتراحات (concrete fixes with code)
- 🐺 **Wolf Notes** | ملاحظات الذئب (1-2 witty one-liners)

Keep review under 400 words. Be direct, no sugarcoating.

```python
{code}
```
"""


# ============================================================================
# Static Analysis (works offline — no model required)
# ============================================================================

def _static_analysis(code: str, focus: str) -> Dict[str, Any]:
    """Run lightweight static checks (works without the model).

    تشغيل فحوصات ثابتة خفيفة (تعمل بدون النموذج).

    Returns:
        Dict with: issues (list), metrics (dict)
    """
    issues: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}

    lines = code.splitlines()
    metrics["line_count"] = len(lines)
    metrics["blank_lines"] = sum(1 for ln in lines if not ln.strip())
    metrics["comment_lines"] = sum(1 for ln in lines if ln.strip().startswith("#"))
    metrics["code_lines"] = metrics["line_count"] - metrics["blank_lines"] - metrics["comment_lines"]

    # Focus: general / security / performance / style
    if focus in ("general", "security"):
        # Look for dangerous patterns
        dangerous = {
            "eval(": "❌ Never use eval() — arbitrary code execution risk",
            "exec(": "❌ exec() is also dangerous — use specific parsers",
            "shell=True": "⚠️ subprocess shell=True = shell injection risk",
            "os.system": "⚠️ os.system is brittle — prefer subprocess.run",
            "pickle.loads": "⚠️ pickle.loads can execute arbitrary code",
            "input(": "⚠️ input() in Python 2 = eval; use raw_input or Python 3",
            "MD5": "⚠️ MD5 is broken for security — use sha256/blake2",
            "SHA1": "⚠️ SHA1 is broken for security — use sha256/blake2",
        }
        for pattern, msg in dangerous.items():
            if pattern in code:
                issues.append({"severity": "🔥", "rule": pattern, "message": msg})

    if focus in ("general", "performance"):
        # Loop nesting
        max_indent = 0
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                max_indent = max(max_indent, indent // 4)
        if max_indent >= 4:
            issues.append({
                "severity": "⚠️",
                "rule": f"deep_nesting_{max_indent}",
                "message": f"Deep nesting ({max_indent} levels) — extract helper functions",
            })

        # String concat in loops
        if 'for ' in code and '+="' in code:
            issues.append({
                "severity": "⚠️",
                "rule": "string_concat_loop",
                "message": "String concatenation in loop — use list + ''.join()",
            })

    if focus in ("general", "style"):
        # Long lines
        long_lines = [(i + 1, len(ln)) for i, ln in enumerate(lines) if len(ln) > 100]
        if long_lines:
            issues.append({
                "severity": "💡",
                "rule": "long_lines",
                "message": f"{len(long_lines)} lines > 100 chars (e.g. line {long_lines[0][0]} = {long_lines[0][1]} chars)",
            })

        # Missing docstring on first def
        first_def = next((i for i, ln in enumerate(lines) if ln.strip().startswith("def ")), None)
        if first_def is not None:
            window = lines[max(0, first_def - 5):first_def]
            has_docstring = any('"""' in ln or "'''" in ln for ln in window)
            if not has_docstring:
                issues.append({
                    "severity": "💡",
                    "rule": "missing_docstring",
                    "message": f"First function (line {first_def+1}) has no docstring above it",
                })

    return {"issues": issues, "metrics": metrics}


# ============================================================================
# Model Review (optional — uses Alpha Wolf via backend proxy)
# ============================================================================

def _model_review(code: str, focus: str, backend_url: str) -> Optional[str]:
    """Ask Alpha Wolf model for a review via the backend chat endpoint.

    اطلب من نموذج Alpha Wolf مراجعة عبر نقطة نهاية الـ backend.

    Returns:
        Model response text or None if unavailable.
    """
    try:
        import httpx
        prompt = WOLF_REVIEW_PROMPT.format(focus=focus, code=code[:4000])  # truncate

        resp = httpx.post(
            f"{backend_url}/v1/chat/completions",
            json={
                "model": "alpha-wolf-agent",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 800,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        # Iron Law #41: surface honestly
        return f"[Model review unavailable: {type(e).__name__}: {e}]"


# ============================================================================
# Main Run
# ============================================================================

def run(
    path: str,
    focus: str = "general",
    max_lines: int = 500,
    use_model: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Review a Python file: static analysis + optional Wolf model review.

    مراجعة ملف بايثون: تحليل ثابت + مراجعة اختيارية من نموذج Wolf.

    Args:
        path: Python file to review | مسار ملف بايثون للمراجعة
        focus: One of 'general', 'security', 'performance', 'style' | مجال المراجعة
        max_lines: Max lines to analyze (default 500) | أقصى عدد أسطر
        use_model: If True, also call Alpha Wolf model for narrative review (default False)
        use_model: إذا كان True، استدعِ أيضاً نموذج Alpha Wolf للمراجعة السردية

    Returns:
        Dict with: success, path, static (dict), model_review (str or None), wolf_summary (str)
        قاموس يحتوي على: نجاح، مسار، تحليل ثابت، مراجعة النموذج، ملخص الذئب
    """
    # Step 1: Read file (delegate to read_file_skill — Iron Law #48 separation)
    read_result = read_file(path=path)
    if not read_result["success"]:
        return {
            "success": False,
            "error": f"Could not read file: {read_result.get('error')}",
            "path": path,
            "static": None,
            "model_review": None,
        }

    code = read_result["content"]
    if len(code.splitlines()) > max_lines:
        code = "\n".join(code.splitlines()[:max_lines]) + f"\n\n[... truncated at {max_lines} lines]"

    # Step 2: Static analysis (always works — Iron Law #15 offline)
    static = _static_analysis(code, focus)

    # Step 3: Optional model review
    model_review = None
    if use_model:
        backend_url = os.environ.get("ALPHA_WOLF_BACKEND_URL", "http://localhost:8001")
        model_review = _model_review(code, focus, backend_url)

    # Step 4: Wolf summary (1-line personality touch — Iron Law #47 bilingual)
    issue_count = len(static["issues"])
    wolf_summary = (
        f"🐺 Alpha Wolf reviewed {path}: "
        f"{issue_count} issue(s) found in focus='{focus}'. "
        f"الذئب راجع {path}: وجد {issue_count} مشكلة في مجال='{focus}'."
    )

    return {
        "success": True,
        "path": path,
        "focus": focus,
        "static": static,
        "model_review": model_review,
        "wolf_summary": wolf_summary,
    }


if __name__ == "__main__":
    # Self-test (Iron Law #15)
    import tempfile
    tmp = Path(tempfile.gettempdir()) / "code_review_skill_test.py"
    tmp.write_text('''
def add(x, y):
    return x + y

def unsafe():
    return eval(input("> "))
''', encoding="utf-8")

    out = run(path=str(tmp), focus="security")
    print(f"Test 1 (security review): success={out['success']}")
    print(f"  Issues: {len(out['static']['issues'])}")
    for issue in out["static"]["issues"]:
        print(f"    {issue['severity']} {issue['rule']}: {issue['message']}")
    assert out["success"]
    assert any("eval" in i["rule"] for i in out["static"]["issues"]), "Should detect eval()"

    out2 = run(path="/nonexistent.py", focus="general")
    print(f"Test 2 (missing file): success={out2['success']}")
    assert not out2["success"]

    tmp.unlink()
    print("✓ code_review_skill self-test PASSED")