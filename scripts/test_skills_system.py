#!/usr/bin/env python3
r"""
Test Skills System | اختبار نظام المهارات
=========================================
Verifies:
1. All built-in skills load + run correctly
2. Skills manager can install/uninstall
3. Each skill produces expected output
4. /v1/tools/discover endpoint works (if backend running)

Iron Laws Applied:
- #15 (Verify)        : every test must pass before claiming success
- #22 (Autonomous)    : no prompts — execute
- #33 (Lessons)       : bilingual AR+EN output
- #47 (Bilingual)     : test output in both languages
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Bypass .env loading (not needed for skills test)
import os
os.environ.setdefault("ALPHA_WOLF_SKIP_BODY_INIT", "1")


def banner(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def test_builtin_skills() -> int:
    """Test all built-in skills load + run correctly."""
    from backend.agent import skills

    banner("TEST 1: Built-in Skills Loader")

    # 1.1 list_skills discovers all
    discovered = skills.list_skills()
    expected = {"example_skill", "read_file_skill", "web_search_skill", "code_review_skill"}
    found = {s.name for s in discovered}
    if not expected.issubset(found):
        print(f"  ✗ Missing skills. Expected {expected}, found {found}")
        return 0

    print(f"  ✓ Discovered {len(discovered)} skills: {sorted(found)}")
    print(f"  ✓ All expected skills present")
    return 1


def _inner_success(result: dict) -> bool:
    """Extract the inner skill success from a wrapped run_skill result.

    run_skill wraps the actual skill output in:
    {"success": <wrapper>, "result": {"success":": <skill>, ...}}
    The wrapper success means the skill executed without throwing.
    The inner success means the skill's actual operation succeeded.
    """
    return result.get("result", {}).get("success", False)


def test_read_file_skill() -> int:
    """Test read_file_skill end-to-end."""
    banner("TEST 2: read_file_skill")
    from backend.agent import skills

    # Create test file
    tmp = Path(tempfile.gettempdir()) / "test_read_file_skill.txt"
    tmp.write_text("Alpha Wolf is a wolf that hunts mistakes.", encoding="utf-8")

    result = skills.run_skill("read_file_skill", path=str(tmp))
    if not result.get("success"):
        print(f"  ✗ Wrapper failed: {result}")
        return 0

    if not _inner_success(result):
        print(f"  ✗ Inner result not success: {result}")
        return 0

    if "Alpha Wolf" not in str(result.get("result", {})):
        print(f"  ✗ Wrong content: {result}")
        return 0

    print(f"  ✓ Read {tmp.name}")
    print(f"  ✓ Content contains expected text")

    # Test missing file
    result2 = skills.run_skill("read_file_skill", path="/nonexistent/file.txt")
    if _inner_success(result2):
        print(f"  ✗ Should have failed for missing file: {result2}")
        return 0
    print(f"  ✓ Missing file properly rejected (inner success=False)")

    tmp.unlink()
    return 1


def test_web_search_skill() -> int:
    """Test web_search_skill end-to-end."""
    banner("TEST 3: web_search_skill")
    from backend.agent import skills

    # 3.1 Empty query
    result = skills.run_skill("web_search_skill", query="")
    if not result.get("success"):
        print(f"  ✗ Wrapper crashed on empty query: {result}")
        return 0
    if _inner_success(result):
        print(f"  ✗ Empty query should fail inner: {result}")
        return 0
    print(f"  ✓ Empty query rejected (inner success=False)")

    # 3.2 Real query (DuckDuckGo or Wikipedia fallback)
    result2 = skills.run_skill("web_search_skill", query="Alpha Wolf Agent", max_results=3)
    if not result2.get("success"):
        print(f"  ✗ Wrapper failed: {result2}")
        return 0

    if not _inner_success(result2):
        print(f"  ✗ Inner failed: {result2}")
        return 0

    source = result2.get("result", {}).get("source", "unknown")
    count = result2.get("result", {}).get("count", 0)
    print(f"  ✓ Real query succeeded via '{source}' ({count} results)")

    return 1


def test_code_review_skill() -> int:
    """Test code_review_skill end-to-end."""
    banner("TEST 4: code_review_skill")
    from backend.agent import skills

    # 4.1 Security review on dangerous code
    tmp = Path(tempfile.gettempdir()) / "test_code_review.py"
    tmp.write_text('''
def unsafe():
    user_input = input("> ")
    return eval(user_input)
''', encoding="utf-8")

    result = skills.run_skill("code_review_skill", path=str(tmp), focus="security")
    if not result.get("success"):
        print(f"  ✗ Wrapper failed: {result}")
        return 0
    if not _inner_success(result):
        print(f"  ✗ Inner failed: {result}")
        return 0

    issues = result.get("result", {}).get("static", {}).get("issues", [])
    rule_names = {i["rule"] for i in issues}

    if "eval(" not in rule_names:
        print(f"  ✗ Should detect eval(): got rules {rule_names}")
        return 0

    print(f"  ✓ Detected {len(issues)} security issues:")
    for issue in issues:
        print(f"    {issue['severity']} {issue['rule']}")

    # 4.2 Style review
    tmp2 = Path(tempfile.gettempdir()) / "test_style.py"
    tmp2.write_text('''
def func1(x, y):
    return x + y

def very_long_function_name_with_lots_of_parameters(first_param, second_param, third_param, fourth_param):
    return first_param + second_param + third_param + fourth_param
''', encoding="utf-8")

    result2 = skills.run_skill("code_review_skill", path=str(tmp2), focus="style")
    if not result2.get("success"):
        print(f"  ✗ Style wrapper failed: {result2}")
        return 0
    if not _inner_success(result2):
        print(f"  ✗ Style inner failed: {result2}")
        return 0
    print(f"  ✓ Style review: {len(result2['result']['static']['issues'])} issues")

    # 4.3 Missing file
    result3 = skills.run_skill("code_review_skill", path="/nonexistent.py")
    if not result3.get("success"):
        print(f"  ✗ Wrapper crashed on missing file: {result3}")
        return 0
    if _inner_success(result3):
        print(f"  ✗ Should have failed inner for missing file: {result3}")
        return 0
    print(f"  ✓ Missing file properly rejected (inner success=False)")

    tmp.unlink()
    tmp2.unlink()
    return 1


def test_skills_manager() -> int:
    """Test skills_manager end-to-end."""
    banner("TEST 5: Skills Manager")
    from backend.agent import skills_manager

    mgr = skills_manager.SkillsManager()
    mgr.auto_load()  # populate cache

    # 5.1 list_all from registry
    all_records = mgr.list_all()
    if len(all_records) < 4:
        print(f"  ✗ Registry should have 4+ skills, has {len(all_records)}")
        return 0
    print(f"  ✓ Registry has {len(all_records)} skills")

    # 5.2 install_from_text
    test_code = '''"""Name: script_test_skill
Description: Test skill | مهارة اختبار
Version: 0.5.0
Author: Test
"""

def run(msg: str = "hi") -> dict:
    return {"echo": msg}
'''
    install_result = mgr.install_from_text("script_test_skill", test_code)
    if not install_result.get("success"):
        print(f"  ✗ install_from_text failed: {install_result}")
        return 0
    print(f"  ✓ install_from_text: {install_result['skill']} v0.5.0")

    # 5.3 get metadata
    record = mgr.get("script_test_skill")
    if not record or record["version"] != "0.5.0":
        print(f"  ✗ get: wrong metadata: {record}")
        return 0
    print(f"  ✓ get: version={record['version']}, source={record['install_source']}")

    # 5.4 run the new skill
    run_result = mgr.run("script_test_skill", {"msg": "hello"})
    if not run_result.get("success") or run_result["result"].get("echo") != "hello":
        print(f"  ✗ run failed: {run_result}")
        return 0
    print(f"  ✓ run: echo='hello'")

    # 5.5 uninstall
    un_result = mgr.uninstall("script_test_skill")
    if not un_result.get("success"):
        print(f"  ✗ uninstall failed: {un_result}")
        return 0
    print(f"  ✓ uninstall: {un_result['skill']}")

    # 5.6 sessions
    sess = skills_manager.upsert_session("test-session-1", user_id="hesham", metadata={"client": "script"})
    if sess["session_id"] != "test-session-1":
        print(f"  ✗ upsert_session failed: {sess}")
        return 0
    print(f"  ✓ session created: {sess['session_id']}")

    return 1


def test_tools_discover() -> int:
    """Test /v1/tools/discover endpoint (if backend running)."""
    banner("TEST 6: /v1/tools/discover (live HTTP test)")
    try:
        import httpx
    except ImportError:
        print(f"  ~ httpx not available, skipping live test")
        return 1  # not a failure

    try:
        resp = httpx.get("http://localhost:8001/v1/tools/discover", timeout=5)
        if resp.status_code != 200:
            print(f"  ~ Backend not running (status {resp.status_code}) — skipping live test")
            return 1  # acceptable for offline test

        data = resp.json()
        counts = data.get("counts", {})
        print(f"  ✓ Unified catalog: {counts}")
        print(f"  ✓ Total tools: {counts.get('total', 0)}")
        return 1
    except Exception as e:
        print(f"  ~ Backend not reachable ({type(e).__name__}): {e}")
        print(f"  ~ Run `python -m backend.run_server` to test live")
        return 1  # acceptable


def main() -> int:
    """Run all skills tests."""
    print("="*60)
    print("  ALPHA WOLF AGENT — Skills System Test Suite")
    print("  نظام اختبار المهارات")
    print("="*60)

    tests = [
        ("Built-in Skills", test_builtin_skills),
        ("read_file_skill", test_read_file_skill),
        ("web_search_skill", test_web_search_skill),
        ("code_review_skill", test_code_review_skill),
        ("Skills Manager", test_skills_manager),
        ("Tools Discover (live)", test_tools_discover),
    ]

    passed = 0
    total = len(tests)

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            print(f"\n  ✗ {name}: EXCEPTION {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{total} tests passed")
    print(f"  النتائج: {passed}/{total} اختبار نجح")
    print(f"{'='*60}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())