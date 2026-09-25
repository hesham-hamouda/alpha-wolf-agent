#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Skills Manager | مدير المهارات
===================================================
Separated concerns layer over backend/agent/skills.py (Iron Law #48).

Responsibilities:
- Skills lifecycle: install, list, run, uninstall, upgrade
- Skills DB persistence (sync code + version + metadata)
- Skills auto-loader on backend startup
- Skills discovery (where they come from, dependencies)
- Runtime validation of skill contracts (has run()?)

Iron Laws Applied:
- #13 (Self-Critical) : self_test() at bottom
- #15 (Verify)        : every operation returns structured dict
- #21 (NO Deletion)    : never removes skill files unless user says so
- #22 (Autonomous)    : no prompts — execute
- #33 (Lessons)       : bilingual AR+EN docstrings (Iron Law #47)
- #36 (5-Layer Save)  : skills metadata persisted in conversations.db
- #47 (Bilingual)     : every public function has Arabic translation
- #48 (Separated)     : thin wrapper over skills.py — no logic duplication
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.agent import skills as _skills_layer
from backend.agent import memory as _memory_layer

logger = logging.getLogger("alpha_wolf.skills_manager")


# ============================================================================
# Skills DB (Iron Law #36 — persistent registry in conversations.db)
# ============================================================================

def _registry_table_sql() -> str:
    """Return SQL to create the skills registry table.

    Returns SQL لإنشاء جدول سجل المهارات.
    """
    return """
    CREATE TABLE IF NOT EXISTS skills_registry (
        name TEXT PRIMARY KEY,
        version TEXT,
        description TEXT,
        description_ar TEXT,
        author TEXT,
        parameters TEXT,
        path TEXT,
        installed_at TEXT,
        last_verified TEXT,
        install_source TEXT  -- 'builtin' | 'url' | 'file' | 'text'
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        metadata TEXT,
        created_at TEXT NOT NULL,
        last_active TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_skills_registry_verified
    ON skills_registry(last_verified DESC);
    """


@contextmanager
def _registry_conn():
    """Reuse memory.py connection (single DB file = Iron Law #21).

    إعادة استخدام اتصال memory.py (ملف DB واحد).
    """
    # Lazy import to avoid circular dependency
    with _memory_layer._get_conn() as conn:
        conn.executescript(_registry_table_sql())
        yield conn


# ============================================================================
# Skills Manager — public API
# ============================================================================

@dataclass
class SkillRecord:
    """Persistent record for an installed skill.

    سجل دائم لمهارة مثبتة.
    """
    name: str
    version: str = "0.0.0"
    description: str = ""
    description_ar: str = ""
    author: str = ""
    parameters: Dict[str, Any] = None
    path: str = ""
    installed_at: str = ""
    last_verified: str = ""
    install_source: str = "builtin"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class SkillsManager:
    """High-level skills lifecycle manager.

    مدير دورة حياة المهارات عالي المستوى.

    Wraps backend/agent/skills.py with persistence + validation + discovery.
    """

    def __init__(self):
        self._cache: Dict[str, SkillRecord] = {}

    # ------------------------------------------------------------------
    # Auto-load on backend startup
    # ------------------------------------------------------------------

    def auto_load(self) -> Dict[str, Any]:
        """Discover + register all skills from backend/skills/.

        اكتشاف + تسجيل جميع المهارات من backend/skills/.
        Called once at backend startup (Iron Law #15 freshness).
        """
        discovered = _skills_layer.list_skills()
        registered = 0
        errors: List[str] = []

        for meta in discovered:
            try:
                self._register_from_metadata(meta, install_source="builtin")
                registered += 1
            except Exception as e:
                errors.append(f"{meta.name}: {type(e).__name__}: {e}")

        logger.info("Skills auto-load: %d registered, %d errors", registered, len(errors))
        return {
            "registered": registered,
            "errors": errors,
            "total_discovered": len(discovered),
        }

    # ------------------------------------------------------------------
    # Install / Uninstall
    # ------------------------------------------------------------------

    def install_from_file(self, source_path: str, target_name: Optional[str] = None) -> Dict[str, Any]:
        """Install a skill from a local .py file.

        تثبيت مهارة من ملف .py محلي.
        """
        result = _skills_layer.install_skill_from_file(source_path, target_name)
        if result.get("success"):
            meta = result["metadata"]
            self._register_from_metadata(meta, install_source="file")
        return result

    def install_from_url(self, url: str, target_name: Optional[str] = None) -> Dict[str, Any]:
        """Install a skill from a URL.

        تثبيت مهارة من URL.
        """
        result = _skills_layer.install_skill_from_url(url, target_name)
        if result.get("success"):
            meta = result["metadata"]
            self._register_from_metadata(meta, install_source="url")
        return result

    def install_from_text(self, name: str, source_text: str) -> Dict[str, Any]:
        """Install a skill from inline Python text (Iron Law #33 self-improvement).

        تثبيت مهارة من نص بايثون inline (تحسين ذاتي).

        Validates that the text contains a run() function before saving.
        يتحقق من وجود دالة run() قبل الحفظ.
        """
        if "def run" not in source_text:
            return {"success": False, "error": "No `def run` found in source text"}

        skills_dir = _skills_layer._skills_dir()
        target = skills_dir / f"{name}.py"

        if target.exists():
            return {"success": False, "error": f"Skill {name} already exists"}

        target.write_text(source_text, encoding="utf-8")

        meta = _skills_layer._load_skill_from_file(target)
        if not meta:
            target.unlink()
            return {"success": False, "error": "Failed to parse metadata"}

        self._register_from_metadata(meta, install_source="text")
        return {
            "success": True,
            "skill": name,
            "installed_path": str(target),
            "metadata": meta.to_dict(),
        }

    def uninstall(self, name: str) -> Dict[str, Any]:
        """Uninstall a skill.

        إزالة مهارة.
        Iron Law #21: explicit user action, not routine deletion.
        """
        result = _skills_layer.uninstall_skill(name)
        if result.get("success"):
            self._unregister(name)
        return result

    # ------------------------------------------------------------------
    # Discovery + Listing
    # ------------------------------------------------------------------

    def list_all(self) -> List[Dict[str, Any]]:
        """List all installed skills (from registry).

        قائمة بجميع المهارات المثبتة.
        """
        with _registry_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT name, version, description, description_ar, author,
                       parameters, path, installed_at, last_verified, install_source
                FROM skills_registry
                ORDER BY name
            """)
            records = []
            for row in cur.fetchall():
                params = {}
                if row["parameters"]:
                    try:
                        params = json.loads(row["parameters"])
                    except json.JSONDecodeError:
                        pass
                records.append({
                    "name": row["name"],
                    "version": row["version"],
                    "description": row["description"],
                    "description_ar": row["description_ar"],
                    "author": row["author"],
                    "parameters": params,
                    "path": row["path"],
                    "installed_at": row["installed_at"],
                    "last_verified": row["last_verified"],
                    "install_source": row["install_source"],
                })
            return records

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a single skill by name from the registry.

        الحصول على مهارة واحدة من السجل.
        """
        with _registry_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM skills_registry WHERE name = ?", (name,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("parameters"):
                try:
                    d["parameters"] = json.loads(d["parameters"])
                except json.JSONDecodeError:
                    d["parameters"] = {}
            return d

    def run(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a skill by name (delegates to skills layer).

        تشغيل مهارة بالاسم (يفوّض لطبقة المهارات).
        """
        args = arguments or {}
        return _skills_layer.run_skill(name, **args)

    # ------------------------------------------------------------------
    # Internal: register / unregister in DB
    # ------------------------------------------------------------------

    def _register_from_metadata(self, meta: Any, install_source: str) -> None:
        """Insert or replace a skill record in the DB.

        إدراج أو استبدال سجل مهارة في قاعدة البيانات.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Serialize parameters
        params_str = json.dumps(meta.parameters or {}, ensure_ascii=False)

        with _registry_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO skills_registry
                (name, version, description, description_ar, author, parameters, path,
                 installed_at, last_verified, install_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                meta.name,
                meta.version,
                meta.description,
                meta.description_ar,
                meta.author,
                params_str,
                meta.path,
                now,
                now,
                install_source,
            ))

    def _unregister(self, name: str) -> None:
        """Remove a skill from the registry (DB).

        إزالة مهارة من السجل (DB).
        """
        with _registry_conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM skills_registry WHERE name = ?", (name,))


# ============================================================================
# Sessions API (lightweight user/session tracking)
# ============================================================================

def upsert_session(session_id: str, user_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create or update a session record (Iron Law #36 — persistence).

    إنشاء أو تحديث سجل جلسة.

    Args:
        session_id: Unique session ID (UUID or any stable identifier)
        user_id: Optional user identifier
        metadata: Optional JSON metadata (e.g. client info, IP)

    Returns:
        Dict with session_id, user_id, created_at, last_active, metadata
    """
    now = datetime.now(timezone.utc).isoformat()
    meta_str = json.dumps(metadata or {}, ensure_ascii=False)

    with _registry_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_at FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE sessions SET last_active = ?, user_id = ?, metadata = ?
                WHERE id = ?
            """, (now, user_id, meta_str, session_id))
            created_at = row["created_at"]
        else:
            cur.execute("""
                INSERT INTO sessions (id, user_id, metadata, created_at, last_active)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, meta_str, now, now))
            created_at = now

    return {
        "session_id": session_id,
        "user_id": user_id,
        "metadata": metadata or {},
        "created_at": created_at,
        "last_active": now,
    }


def list_sessions(limit: int = 100) -> List[Dict[str, Any]]:
    """List all sessions (most recent first).

    قائمة بجميع الجلسات (الأحدث أولاً).
    """
    with _registry_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, user_id, metadata, created_at, last_active
            FROM sessions
            ORDER BY last_active DESC
            LIMIT ?
        """, (limit,))
        results = []
        for row in cur.fetchall():
            meta = {}
            if row["metadata"]:
                try:
                    meta = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    pass
            results.append({
                "session_id": row["id"],
                "user_id": row["user_id"],
                "metadata": meta,
                "created_at": row["created_at"],
                "last_active": row["last_active"],
            })
        return results


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify skills_manager works end-to-end.

    التحقق من أن مدير المهارات يعمل من البداية للنهاية.
    """
    print("Running skills_manager self-tests...")
    print("تشغيل اختبارات مدير المهارات الذاتية...")

    passed = 0
    failed = 0

    try:
        mgr = SkillsManager()

        # Test 1: Auto-load
        load_result = mgr.auto_load()
        if load_result["registered"] >= 1:
            passed += 1
            print(f"  ✓ auto_load: {load_result['registered']} registered")
        else:
            failed += 1
            print(f"  ✗ auto_load: {load_result}")

        # Test 2: list_all
        all_skills = mgr.list_all()
        if len(all_skills) >= 1:
            passed += 1
            print(f"  ✓ list_all: {len(all_skills)} skills in registry")
        else:
            failed += 1
            print(f"  ✗ list_all: empty")

        # Test 3: install_from_text (Iron Law #33 self-improvement)
        test_code = '''"""Name: mgr_test_skill
Description: Multiply two numbers | ضرب رقمين
Version: 1.0.0
Author: Alpha Wolf Team
"""

def run(x: int, y: int) -> int:
    return x * y
'''
        install_result = mgr.install_from_text("mgr_test_skill", test_code)
        if install_result["success"]:
            passed += 1
            print(f"  ✓ install_from_text: {install_result['skill']}")
        else:
            failed += 1
            print(f"  ✗ install_from_text: {install_result['error']}")

        # Test 4: run installed skill
        run_result = mgr.run("mgr_test_skill", {"x": 3, "y": 4})
        if run_result.get("success") and run_result.get("result") == 12:
            passed += 1
            print(f"  ✓ run mgr_test_skill: 3*4={run_result['result']}")
        else:
            failed += 1
            print(f"  ✗ run: {run_result}")

        # Test 5: get by name
        record = mgr.get("mgr_test_skill")
        if record and record["version"] == "1.0.0":
            passed += 1
            print(f"  ✓ get: version={record['version']}, source={record['install_source']}")
        else:
            failed += 1
            print(f"  ✗ get: {record}")

        # Test 6: sessions
        sess = upsert_session("test-sess-001", user_id="hesham", metadata={"client": "test"})
        if sess["session_id"] == "test-sess-001":
            passed += 1
            print(f"  ✓ upsert_session: {sess['session_id']}")
        else:
            failed += 1
            print(f"  ✗ upsert_session: {sess}")

        sess_list = list_sessions(limit=10)
        if any(s["session_id"] == "test-sess-001" for s in sess_list):
            passed += 1
            print(f"  ✓ list_sessions: {len(sess_list)} sessions")
        else:
            failed += 1
            print(f"  ✗ list_sessions: {sess_list}")

        # Cleanup
        mgr.uninstall("mgr_test_skill")

    except Exception as e:
        failed += 1
        print(f"  ✗ exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()