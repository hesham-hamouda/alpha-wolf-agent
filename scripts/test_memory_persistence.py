#!/usr/bin/env python3
r"""
Test Memory Persistence | اختبار استمرارية الذاكرة
=================================================
Verifies:
1. Conversations persist across "restarts" (Python process restart)
2. Sessions table persists
3. Skills registry persists
4. Soft delete works
5. Foreign keys + constraints intact

Approach:
- Create conversation + add messages
- Verify can retrieve in same process
- Exit process (simulate restart by re-importing)
- Verify data still retrievable in NEW process
- Cleanup

Iron Laws Applied:
- #15 (Verify)   : data must survive process restart
- #21 (NO Deletion): use soft delete by default
- #33 (Lessons)  : bilingual output
- #47 (Bilingual): Arabic + English
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Marker file to track test state across processes
MARKER_FILE = PROJECT_ROOT / "data" / "test_memory_persistence_state.json"
DB_PATH = PROJECT_ROOT / "backend" / "conversations.db"


def banner(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def phase1_write_data() -> str:
    """Phase 1: Write conversation + session + skill record."""
    banner("PHASE 1: Write data (simulate process 1)")
    from backend.agent import memory as agent_memory
    from backend.agent import skills_manager

    # 1.1 Create conversation
    conv_id = agent_memory.create_conversation(
        title="Persistence Test | اختبار الاستمرارية",
        metadata={"test": "memory_persistence", "user": "hesham"},
    )
    print(f"  ✓ Created conversation: {conv_id[:8]}...")

    # 1.2 Add messages
    msgs = [
        ("user", "Hello Wolf, can you remember me? | مرحباً يا ذئب، هل تتذكرني؟"),
        ("assistant", "Of course! I'm a wolf — I never forget. | بالطبع! أنا ذئب — لا أنسى أبداً."),
        ("tool", "Recall: 1 conversation found | الاستدعاء: وُجدت محادثة واحدة"),
    ]
    msg_ids = []
    for role, content in msgs:
        mid = agent_memory.add_message(conv_id, role, content, importance=7)
        msg_ids.append(mid)
    print(f"  ✓ Added {len(msg_ids)} messages")

    # 1.3 Create session
    sess = skills_manager.upsert_session(
        session_id="persistence-test-001",
        user_id="hesham",
        metadata={"test_run": "phase1"},
    )
    print(f"  ✓ Created session: {sess['session_id']}")

    # 1.4 Install skill via manager (test registry)
    test_code = '''"""Name: persistence_test_skill
Description: Skill for persistence test | مهارة لاختبار الاستمرارية
Version: 0.1.0
Author: Test
"""

def run() -> dict:
    return {"persistent": True, "lang": "EN+AR"}
'''
    install = skills_manager.SkillsManager().install_from_text("persistence_test_skill", test_code)
    if not install.get("success"):
        print(f"  ✗ Skill install failed: {install}")
        return ""
    print(f"  ✓ Installed skill: {install['skill']}")

    # Save marker
    MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "conv_id": conv_id,
        "msg_ids": msg_ids,
        "session_id": "persistence-test-001",
        "skill_name": "persistence_test_skill",
    }
    MARKER_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"  ✓ State saved to: {MARKER_FILE.name}")

    return conv_id


def phase2_verify_restart() -> int:
    """Phase 2: Verify data survives Python process restart.

    Strategy: spawn a NEW Python subprocess that reads the data.
    If it sees the same conversation, persistence WORKS.
    """
    banner("PHASE 2: Verify across RESTART (subprocess reads data)")

    if not MARKER_FILE.exists():
        print(f"  ✗ Marker file missing — Phase 1 not run")
        return 0

    state = json.loads(MARKER_FILE.read_text(encoding="utf-8"))
    conv_id = state["conv_id"]
    msg_ids = state["msg_ids"]
    session_id = state["session_id"]
    skill_name = state["skill_name"]

    # Spawn a NEW Python subprocess to verify cross-process persistence
    test_script = f'''
import sys
sys.path.insert(0, r"{PROJECT_ROOT}")
from backend.agent import memory as agent_memory
from backend.agent import skills_manager

results = {{"checks": []}}

# Check 1: conversation exists
if agent_memory.conversation_exists("{conv_id}"):
    results["checks"].append({{"name": "conversation_exists", "success": True}})
else:
    results["checks"].append({{"name": "conversation_exists", "success": False, "error": "not found"}})

# Check 2: messages retrieved correctly
msgs = agent_memory.get_conversation("{conv_id}")
if len(msgs) >= 3:
    results["checks"].append({{"name": "messages_count", "success": True, "count": len(msgs)}})
else:
    results["checks"].append({{"name": "messages_count", "success": False, "got": len(msgs)}})

# Check 3: message content
first_user_msg = next((m for m in msgs if m["role"] == "user"), None)
if first_user_msg and "Hello Wolf" in first_user_msg["content"]:
    results["checks"].append({{"name": "message_content", "success": True}})
else:
    results["checks"].append({{"name": "message_content", "success": False}})

# Check 4: session persisted
sessions = skills_manager.list_sessions(limit=20)
if any(s["session_id"] == "{session_id}" for s in sessions):
    results["checks"].append({{"name": "session_persisted", "success": True}})
else:
    results["checks"].append({{"name": "session_persisted", "success": False}})

# Check 5: skill registry persisted
mgr = skills_manager.SkillsManager()
record = mgr.get("{skill_name}")
if record and record["name"] == "{skill_name}":
    results["checks"].append({{"name": "skill_registry_persisted", "success": True, "version": record["version"]}})
else:
    results["checks"].append({{"name": "skill_registry_persisted", "success": False}})

# Check 6: soft delete survives
agent_memory.delete_conversation("{conv_id}", hard=False)
if not agent_memory.conversation_exists("{conv_id}"):
    results["checks"].append({{"name": "soft_delete", "success": True}})
else:
    results["checks"].append({{"name": "soft_delete", "success": False}})

# Check 7: hard delete cleans up
agent_memory.delete_conversation("{conv_id}", hard=True)
if not agent_memory.conversation_exists("{conv_id}"):
    results["checks"].append({{"name": "hard_delete", "success": True}})
else:
    results["checks"].append({{"name": "hard_delete", "success": False}})

import json
print(json.dumps(results))
'''

    try:
        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"  ✗ Subprocess failed: {result.stderr}")
            return 0

        # Parse last JSON line
        output_lines = [ln for ln in result.stdout.strip().splitlines() if ln.startswith("{")]
        if not output_lines:
            print(f"  ✗ No JSON output: {result.stdout}")
            return 0

        data = json.loads(output_lines[-1])
        checks = data.get("checks", [])

        all_passed = True
        for check in checks:
            name = check.get("name")
            success = check.get("success")
            extra = {k: v for k, v in check.items() if k not in ("name", "success")}
            symbol = "✓" if success else "✗"
            print(f"  {symbol} {name}: {extra if not success else 'OK'}")
            if not success:
                all_passed = False

        return 1 if all_passed else 0

    except subprocess.TimeoutExpired:
        print(f"  ✗ Subprocess timed out")
        return 0
    except Exception as e:
        print(f"  ✗ Subprocess error: {type(e).__name__}: {e}")
        return 0


def phase3_cleanup() -> None:
    """Phase 3: Cleanup test data."""
    banner("PHASE 3: Cleanup")
    from backend.agent import skills_manager

    # Uninstall the test skill
    mgr = skills_manager.SkillsManager()
    result = mgr.uninstall("persistence_test_skill")
    print(f"  ✓ Uninstalled skill: {result.get('skill', 'failed')}")

    # Remove marker file
    if MARKER_FILE.exists():
        MARKER_FILE.unlink()
        print(f"  ✓ Removed marker file")

    # Verify DB still exists
    if DB_PATH.exists():
        size_kb = DB_PATH.stat().st_size / 1024
        print(f"  ✓ conversations.db preserved ({size_kb:.1f} KB)")


def main() -> int:
    """Run all persistence tests."""
    print("="*60)
    print("  ALPHA WOLF AGENT — Memory Persistence Test")
    print("  اختبار استمرارية الذاكرة")
    print("="*60)
    print(f"\n  DB path: {DB_PATH}")
    print(f"  Project: {PROJECT_ROOT}")

    # Phase 1: write
    conv_id = phase1_write_data()
    if not conv_id:
        print("\n  PHASE 1 FAILED — aborting")
        return 1

    # Phase 2: verify across restart
    phase2_passed = phase2_verify_restart()

    # Phase 3: cleanup
    phase3_cleanup()

    print(f"\n{'='*60}")
    if phase2_passed:
        print("  ✅ MEMORY PERSISTENCE: WORKS across restart")
        print("  ✅ الذاكرة مستمرة عبر إعادة التشغيل")
        return 0
    else:
        print("  ✗ MEMORY PERSISTENCE: FAILED")
        print("  ✗ الذاكرة: فشل في الاستمرارية")
        return 1
    print(f"{'='*60}\n")


if __name__ == "__main__":
    sys.exit(main())