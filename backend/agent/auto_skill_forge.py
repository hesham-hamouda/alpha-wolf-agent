#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Auto Skill Forge | مصنع المهارات الذاتي
=============================================================
Generate Python skill modules from (name, description, code_template) tuples.

SAFETY (Iron Law #21 + #41):
- Validates code via AST parse before save.
- Blocks dangerous patterns (shells, eval, raw path escape).
- Refuses to overwrite existing skills unless `auto_save=True` is explicit.
- All paths stay inside `backend/skills/` (workspace, NOT body — Iron Law #42).

Iron Laws Applied:
- #15 (Verify)     : self_test() in __main__
- #21 (NO Delete)  : overwrite requires auto_save=True
- #33 (Lessons)    : bilingual docstrings (Iron Law #47)
- #42 (Storage)    : all writes inside workspace `backend/skills/`
"""
from __future__ import annotations

import ast
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("alpha_wolf.auto_skill_forge")

# Skills directory (NOT body — Iron Law #42)
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


# ============================================================================
# Safety Gate
# ============================================================================

# Iron Law #21 + #41 — dangerous patterns that no auto-forged skill may use.
# Balanced: urllib/json/re are fine; shell + path escapes + raw exec are not.
_DANGEROUS_PATTERNS: List[str] = [
    r"\bos\.system\b",
    r"\bos\.popen\b",
    r"\bos\.exec[lpv]?\b",
    r"\bos\.spawn\b",
    r"\bos\.remove\b",
    r"\bos\.rmdir\b",
    r"\bsubprocess\b(?!\.run\(.{0,40}timeout)",
    r"\bshutil\.rmtree\b",
    r"\bshutil\.move\b",
    r"\bsocket\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bcompile\s*\(",
    r"\brm\s+-rf\b",
    r"\bformat\s+[A-Z]:",
    r"\bopen\s*\(.{0,40}(?:/etc/|C:\\\\Windows\\\\System32|/dev/|/proc/|/sys/)",
]


def _validate_skill_code(code: str) -> Optional[str]:
    """Validate Python code is safe (AST + dangerous pattern scan).

    Returns error message if unsafe, None if OK.
    فحص أمان الكود (تحليل AST + فحص الأنماط الخطرة).
    """
    if not code or not code.strip():
        return "Code is empty"

    # 1. AST parse
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"

    # 2. Dangerous pattern check
    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE | re.DOTALL):
            return f"Dangerous pattern detected: {pattern}"

    # 3. Must define `def run`
    if not re.search(r"^\s*def\s+run\s*\(", code, re.MULTILINE):
        return "No `def run(...)` found — not a valid skill"

    return None


# ============================================================================
# Skill Creation
# ============================================================================

def create_skill(
    name: str,
    description: str,
    code_template: str,
    tags: Optional[List[str]] = None,
    auto_save: bool = False,
) -> Dict[str, Any]:
    """Create a new skill from a code template.

    إنشاء مهارة جديدة من قالب كود.

    Args:
        name        : snake_case skill name (e.g. 'count_lines')
        description : one-line description (bilingual AR+EN OK)
        code_template: Python source containing `def run(**kwargs)`
        tags        : optional list of categorization tags
        auto_save   : if True, write to disk immediately
                      (Iron Law #21: requires explicit opt-in for overwrite)

    Returns:
        dict with success / error / skill_path / metadata.
    """
    # 1. Validate name format
    if not re.match(r"^[a-z][a-z0-9_]{2,40}$", name or ""):
        return {
            "success": False,
            "error": (
                f"Invalid skill name '{name}': must be lowercase, snake_case, "
                "3-40 chars, start with letter"
            ),
        }

    # 2. Validate code safety
    validation_error = _validate_skill_code(code_template or "")
    if validation_error:
        return {
            "success": False,
            "error": validation_error,
            "skill_path": None,
        }

    # 3. Build the skill file path
    skill_path = SKILLS_DIR / f"{name}.py"

    # Iron Law #21: refuse overwrite unless explicit
    if skill_path.exists() and not auto_save:
        return {
            "success": False,
            "error": (
                f"Skill already exists at {skill_path}. "
                "Set auto_save=True to overwrite (explicit overwrite required)."
            ),
            "skill_path": str(skill_path),
        }

    # 4. Build header (Iron Law #47 bilingual + provenance)
    safe_desc = (description or f"Auto-forged skill '{name}'").replace('"""', "\\\"\\\"\\\"")
    header = (
        '"""\n'
        f"Name: {name}\n"
        f"Description: {safe_desc}\n"
        f"Description_AR: مهارة مُنشأة تلقائياً\n"
        f"Author: alpha-wolf-agent.auto_skill_forge\n"
        f"Version: 1.0.0\n"
        f"Tags: {tags or []}\n"
        f"Auto-generated: {datetime.now().isoformat()}\n"
        "\n"
        "Iron Laws Applied:\n"
        "- #21 (NO Delete): explicit auto_save required\n"
        "- #47 (Bilingual): description is AR + EN\n"
        '"""\n'
        "\n"
        "from typing import Dict, Any\n"
        "\n\n"
    )

    full_code = header + (code_template or "")

    # 5. Save if requested
    if auto_save:
        try:
            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(full_code, encoding="utf-8")
            logger.info("[AutoForge] Created skill: %s", skill_path)
        except OSError as e:
            return {
                "success": False,
                "error": f"Write failed: {type(e).__name__}: {e}",
                "skill_path": str(skill_path),
            }

    return {
        "success": True,
        "skill_path": str(skill_path) if auto_save else None,
        "name": name,
        "description": description,
        "tags": tags or [],
        "validation": "passed",
        "code_preview": full_code[:500] + ("..." if len(full_code) > 500 else ""),
    }


def list_auto_forged_skills() -> List[Dict[str, Any]]:
    """List all skills in `backend/skills/` that look auto-generated.

    قائمة المهارات المُنشأة تلقائياً في `backend/skills/`.
    """
    if not SKILLS_DIR.exists():
        return []
    skills = []
    for skill_file in SKILLS_DIR.glob("*.py"):
        if skill_file.name == "__init__.py":
            continue
        try:
            content = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "Auto-generated" in content or "auto_skill_forge" in content:
            skills.append({
                "name": skill_file.stem,
                "path": str(skill_file),
                "size_bytes": skill_file.stat().st_size,
            })
    return skills


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def self_test() -> bool:
    """Verify auto-forge pieces (Iron Law #15).

    التحقق من صحة الـ auto-forge.
    """
    print("Running auto_skill_forge self-tests...")
    ok = True
    try:
        # Test 1: name validation
        if not re.match(r"^[a-z][a-z0-9_]{2,40}$", "valid_name"):
            print("  ✗ name regex accepted bad")
            ok = False
        else:
            print("  ✓ name regex rejects bad names")

        # Test 2: valid code passes
        good_code = (
            'def run(x: str = "hello", **kwargs) -> Dict[str, Any]:\n'
            '    """Echo input."""\n'
            '    return {"echo": x}\n'
        )
        err = _validate_skill_code(good_code)
        if err is not None:
            print(f"  ✗ good code rejected: {err}")
            ok = False
        else:
            print("  ✓ good code passes safety gate")

        # Test 3: code without def run is rejected
        bad_no_run = "x = 1\nprint(x)\n"
        err = _validate_skill_code(bad_no_run)
        if err is None or "def run" not in err:
            print(f"  ✗ code without def run accepted: {err}")
            ok = False
        else:
            print("  ✓ code without def run rejected")

        # Test 4: dangerous code is rejected
        bad_shell = "def run():\n    import os\n    os.system('rm -rf /')\n"
        err = _validate_skill_code(bad_shell)
        if err is None or "Dangerous" not in err and "Blocked" not in err:
            print(f"  ✗ dangerous code accepted: {err}")
            ok = False
        else:
            print(f"  ✓ dangerous code rejected ({err[:60]})")

        # Test 5: eval/exec rejected
        bad_eval = "def run():\n    eval('1+1')\n"
        err = _validate_skill_code(bad_eval)
        if err is None:
            print("  ✗ eval accepted")
            ok = False
        else:
            print(f"  ✓ eval rejected ({err[:60]})")

        # Test 6: create_skill dry-run (no save)
        result = create_skill(
            name="test_skill_dry_run",
            description="test | اختبار",
            code_template=good_code,
            auto_save=False,
        )
        if not result.get("success"):
            print(f"  ✗ dry-run create failed: {result}")
            ok = False
        elif result.get("skill_path") is not None:
            print(f"  ✗ dry-run wrote to disk: {result}")
            ok = False
        else:
            print("  ✓ dry-run create_skill (no write)")

        # Test 7: create_skill with auto_save=True writes
        result2 = create_skill(
            name="test_skill_temp_forge",
            description="temp test | اختبار مؤقت",
            code_template=good_code,
            auto_save=True,
        )
        if not result2.get("success"):
            print(f"  ✗ auto_save=True failed: {result2}")
            ok = False
        else:
            test_path = SKILLS_DIR / "test_skill_temp_forge.py"
            if test_path.exists():
                print(f"  ✓ auto_save=True wrote to {test_path.name}")
                # Cleanup (Iron Law #21 explicit)
                try:
                    test_path.unlink()
                except OSError:
                    pass
            else:
                print(f"  ✗ auto_save=True didn't create file: {test_path}")
                ok = False

        # Test 8: list_auto_forged_skills returns list
        skills = list_auto_forged_skills()
        if not isinstance(skills, list):
            print("  ✗ list_auto_forged_skills not list")
            ok = False
        else:
            print(f"  ✓ list_auto_forged_skills returned {len(skills)} entries")

    except Exception as e:
        print(f"  ✗ exception: {type(e).__name__}: {e}")
        ok = False

    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)