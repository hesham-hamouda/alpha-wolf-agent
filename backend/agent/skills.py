#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Skill Loader | مُحمِّل المهارات
====================================================
Runtime-installable skill system.

A skill is a Python file in backend/skills/ with a run(**kwargs) function.
Skills can be:
- Built-in (shipped with backend/skills/)
- Installed at runtime via /v1/install_skill (URL or local file)

Each skill has a YAML manifest at the top (between SKILL_META markers)
or as docstring metadata.

Iron Laws Applied:
- #15 (Verify)        : Self-test included
- #22 (Autonomous)    : No prompts — execute immediately
- #33 (Lessons)       : Bilingual AR+EN docstrings (Iron Law #47)
- #41 (Conflict)      : Errors include diagnostic context
- #42 (Storage)       : Skills in workspace, not body
- #47 (Bilingual)     : Every public function has Arabic translation
"""
from __future__ import annotations

import importlib.util
import json
import logging
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("alpha_wolf.skills")


# ============================================================================
# Skill Metadata
# ============================================================================

@dataclass
class SkillMetadata:
    """Metadata for a single skill.

    البيانات الوصفية لمهارة واحدة.
    """
    name: str
    description: str
    description_ar: str = ""
    author: str = ""
    version: str = "0.1.0"
    parameters: Dict[str, Any] = field(default_factory=dict)
    path: str = ""
    installed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "description_ar": self.description_ar,
            "author": self.author,
            "version": self.version,
            "parameters": self.parameters,
            "path": self.path,
            "installed_at": self.installed_at,
        }


# ============================================================================
# Skill Loading
# ============================================================================

def _skills_dir() -> Path:
    """Path to backend/skills directory.

    مسار مجلد المهارات.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    skills_dir = backend_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def _parse_metadata(docstring: str) -> Dict[str, Any]:
    """Parse skill metadata from docstring.

    تحليل البيانات الوصفية من docstring.

    Looks for patterns like:
        Name: my_skill
        Description: Does something
        Description_AR: يفعل شيئاً
        Author: someone
        Version: 1.0.0
        Parameters: {key: type, ...}
    """
    meta = {}
    if not docstring:
        return meta

    # Pattern: "Key: Value" at start of line
    pattern = re.compile(r"^\s*([A-Za-z_]+)\s*:\s*(.+)$", re.MULTILINE)
    for match in pattern.finditer(docstring):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        # Map to our internal keys
        key_map = {
            "name": "name",
            "description": "description",
            "description_ar": "description_ar",
            "description_ar": "description_ar",
            "author": "author",
            "version": "version",
            "parameters": "parameters",
        }
        normalized = key_map.get(key, key)
        meta[normalized] = value

    # Try to parse parameters as JSON
    if "parameters" in meta:
        try:
            meta["parameters"] = json.loads(meta["parameters"])
        except json.JSONDecodeError:
            # Keep as string, will be invalid
            pass

    return meta


def _load_skill_from_file(skill_path: Path) -> Optional[SkillMetadata]:
    """Load a single skill from a Python file.

    تحميل مهارة واحدة من ملف بايثون.

    The skill file must have:
    - A module-level docstring with metadata (Name, Description, etc.)
    - An async or sync `run(**kwargs)` function
    """
    if not skill_path.exists() or skill_path.suffix != ".py":
        return None
    if skill_path.name.startswith("_") or skill_path.name == "__init__.py":
        return None

    try:
        # Read source for metadata extraction
        source = skill_path.read_text(encoding="utf-8")

        # Extract docstring (between """ or ''' at top of file)
        # Iron Law #41: support `r"""..."""` raw string prefix (used by most Python files)
        doc_match = re.search(r'(?:^|\n)r?"""\n?(.*?)"""', source, re.DOTALL)
        if not doc_match:
            doc_match = re.search(r"(?:^|\n)r?'''\n?(.*?)'''", source, re.DOTALL)
        docstring = doc_match.group(1) if doc_match else ""
        meta = _parse_metadata(docstring)

        # Fall back to filename
        name = meta.get("name") or skill_path.stem

        return SkillMetadata(
            name=name,
            description=meta.get("description", f"Skill from {skill_path.name}"),
            description_ar=meta.get("description_ar", ""),
            author=meta.get("author", ""),
            version=meta.get("version", "0.1.0"),
            parameters=meta.get("parameters", {}),
            path=str(skill_path),
            installed_at=skill_path.stat().st_mtime.__class__.__name__ and "",  # placeholder
        )
    except Exception as e:
        logger.error(f"Failed to load skill metadata from {skill_path}: {e}")
        return None


def list_skills() -> List[SkillMetadata]:
    """List all installed skills.

    عرض جميع المهارات المثبتة.

    Reads from backend/skills/*.py and returns metadata for each.
    """
    skills = []
    for path in sorted(_skills_dir().glob("*.py")):
        meta = _load_skill_from_file(path)
        if meta:
            skills.append(meta)
    return skills


def get_skill(name: str) -> Optional[SkillMetadata]:
    """Get a skill by name.

    الحصول على مهارة بالاسم.
    """
    for skill in list_skills():
        if skill.name == name:
            return skill
    return None


def run_skill(skill_name: str, **kwargs: Any) -> Dict[str, Any]:
    """Execute a skill by name with arguments.

    تنفيذ مهارة بالاسم مع الوسائط.

    Iron Law #41: Errors include full context.
    """
    skill_path = _skills_dir() / f"{skill_name}.py"
    if not skill_path.exists():
        return {
            "success": False,
            "error": f"Skill not found: {skill_name} | المهارة غير موجودة",
            "available": [s.name for s in list_skills()],
        }

    try:
        # Import the skill as a module
        spec = importlib.util.spec_from_file_location(f"skill_{skill_name}", skill_path)
        if spec is None or spec.loader is None:
            return {"success": False, "error": f"Cannot load skill spec: {skill_name}"}

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"skill_{skill_name}"] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "run"):
            return {"success": False, "error": f"Skill {skill_name} has no `run` function"}

        # Execute run() — handle both sync and async
        import asyncio
        run_func = module.run
        if asyncio.iscoroutinefunction(run_func):
            result = asyncio.run(run_func(**kwargs))
        else:
            result = run_func(**kwargs)

        return {
            "success": True,
            "skill": skill_name,
            "result": result,
            "kwargs": kwargs,
        }
    except Exception as e:
        logger.error(f"Skill execution failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Skill execution failed: {type(e).__name__}: {e}",
            "skill": skill_name,
            "kwargs": kwargs,
        }


def install_skill_from_file(source_path: str, target_name: Optional[str] = None) -> Dict[str, Any]:
    """Install a skill from a local Python file.

    تثبيت مهارة من ملف بايثون محلي.

    Copies the file to backend/skills/ and verifies it has a run() function.
    """
    src = Path(source_path)
    if not src.exists():
        return {"success": False, "error": f"Source file not found: {source_path}"}

    target_name = target_name or src.stem
    target = _skills_dir() / f"{target_name}.py"

    if target.exists():
        return {"success": False, "error": f"Skill {target_name} already exists. Use a different name."}

    # Validate the file has a run() function before copying
    source_text = src.read_text(encoding="utf-8")
    if "def run" not in source_text:
        return {"success": False, "error": "Source file has no `run()` function — not a valid skill"}

    # Copy file
    target.write_text(source_text, encoding="utf-8")

    # Verify by importing
    meta = _load_skill_from_file(target)
    if not meta:
        target.unlink()
        return {"success": False, "error": "Failed to load skill metadata after copy"}

    return {
        "success": True,
        "skill": target_name,
        "installed_path": str(target),
        "metadata": meta.to_dict(),
    }


def install_skill_from_url(url: str, target_name: Optional[str] = None) -> Dict[str, Any]:
    """Install a skill from a URL.

    تثبيت مهارة من رابط URL.

    Downloads the Python file, validates it, and saves to backend/skills/.
    """
    import urllib.request
    import urllib.parse

    try:
        # Determine target name from URL if not provided
        if not target_name:
            parsed = urllib.parse.urlparse(url)
            target_name = Path(parsed.path).stem or "downloaded_skill"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AlphaWolfAgent/0.1 (skill installer)"},
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            source_text = resp.read().decode("utf-8", errors="replace")

        # Validate
        if "def run" not in source_text:
            return {"success": False, "error": "Downloaded file has no `run()` function — not a valid skill"}

        # Save to temp file then install
        target = _skills_dir() / f"{target_name}.py"
        if target.exists():
            return {"success": False, "error": f"Skill {target_name} already exists"}

        target.write_text(source_text, encoding="utf-8")

        meta = _load_skill_from_file(target)
        if not meta:
            target.unlink()
            return {"success": False, "error": "Failed to load skill metadata after download"}

        return {
            "success": True,
            "skill": target_name,
            "installed_path": str(target),
            "source_url": url,
            "metadata": meta.to_dict(),
        }
    except Exception as e:
        return {"success": False, "error": f"Download failed: {type(e).__name__}: {e}"}


def uninstall_skill(name: str) -> Dict[str, Any]:
    """Uninstall a skill.

    إزالة مهارة.

    Iron Law #21: This is explicit user action, not a routine deletion.
    """
    target = _skills_dir() / f"{name}.py"
    if not target.exists():
        return {"success": False, "error": f"Skill {name} not found"}

    target.unlink()
    # Remove from sys.modules if loaded
    sys.modules.pop(f"skill_{name}", None)
    return {"success": True, "skill": name, "uninstalled": True}


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify skill loader works.

    التحقق من أن مُحمِّل المهارات يعمل.
    """
    print("Running skill self-tests...")
    print("تشغيل اختبارات المهارات الذاتية...")

    passed = 0
    failed = 0

    try:
        # Test 1: List skills (should find example_skill.py)
        skills = list_skills()
        if any(s.name == "example_skill" for s in skills):
            passed += 1
            print(f"  ✓ list_skills found {len(skills)} skills (incl example_skill)")
        else:
            failed += 1
            print(f"  ✗ example_skill not found in {[s.name for s in skills]}")

        # Test 2: Run example_skill
        result = run_skill("example_skill", name="Wolf")
        if result["success"] and "Wolf" in str(result.get("result", "")):
            passed += 1
            print(f"  ✓ run_skill works: {result['result']}")
        else:
            failed += 1
            print(f"  ✗ run_skill: {result}")

        # Test 3: get_skill
        meta = get_skill("example_skill")
        if meta and meta.name == "example_skill":
            passed += 1
            print(f"  ✓ get_skill: {meta.description[:50]}")
        else:
            failed += 1
            print(f"  ✗ get_skill: {meta}")

        # Test 4: Install from file (test skill)
        test_skill = _skills_dir() / "test_temp_skill.py"
        test_skill.write_text('''
def run(x: int, y: int) -> int:
    """Name: test_temp_skill
    Description: Add two numbers | يجمع رقمين
    """
    return x + y
''')

        install_result = install_skill_from_file(str(test_skill), target_name="test_temp_skill_2")
        if install_result["success"]:
            passed += 1
            print(f"  ✓ install_skill_from_file: {install_result['skill']}")
        else:
            failed += 1
            print(f"  ✗ install: {install_result['error']}")

        # Test 5: Run the installed skill
        run_result = run_skill("test_temp_skill_2", x=3, y=4)
        if run_result["success"] and run_result["result"] == 7:
            passed += 1
            print(f"  ✓ installed skill runs: 3+4={run_result['result']}")
        else:
            failed += 1
            print(f"  ✗ installed run: {run_result}")

        # Test 6: Uninstall
        un_result = uninstall_skill("test_temp_skill_2")
        if un_result["success"]:
            passed += 1
            print(f"  ✓ uninstall_skill: {un_result['skill']}")
        else:
            failed += 1
            print(f"  ✗ uninstall: {un_result}")

        # Cleanup
        if test_skill.exists():
            test_skill.unlink()

    except Exception as e:
        failed += 1
        print(f"  ✗ exception: {type(e).__name__}: {e}")

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()
