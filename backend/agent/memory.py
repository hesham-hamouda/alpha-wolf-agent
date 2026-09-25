#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Conversation Memory | ذاكرة المحادثات
=========================================================
Persistent conversation history via dedicated SQLite database.

Uses a SEPARATE database file (backend/conversations.db) to avoid
conflicting with body's sessions table (Iron Law #21: no schema clash).

Schema:
- conversations (id, title, created_at, last_activity)
- messages (id, conversation_id, role, content, metadata, created_at, importance)

Iron Laws Applied:
- #15 (Verify)        : Self-test included
- #21 (NO Deletion)   : Soft delete via deleted_at flag in metadata
- #33 (Lessons)       : Bilingual AR+EN docstrings (Iron Law #47)
- #41 (Conflict)      : Uses dedicated DB to avoid body schema clash
- #42 (Storage)       : DB in workspace, not body root
- #47 (Bilingual)     : Every public function has Arabic translation
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================================
# Database Path (Iron Law #42 — Storage Discipline)
# ============================================================================

def _db_path() -> Path:
    """Resolve conversations SQLite database path.

    مسار قاعدة بيانات المحادثات (مستقلة عن body لتجنب تعارض المخطط).
    """
    backend_dir = Path(__file__).resolve().parent.parent
    db_path = backend_dir / "conversations.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@contextmanager
def _get_conn():
    """Context manager for SQLite connection.

    مدير سياق لاتصال SQLite.
    """
    conn = sqlite3.connect(str(_db_path()), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================================
# Schema Management
# ============================================================================

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL,
    last_activity TEXT NOT NULL,
    metadata TEXT,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL,
    importance INTEGER DEFAULT 5,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conv
ON messages(conversation_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_conversations_activity
ON conversations(last_activity DESC) WHERE deleted_at IS NULL;
"""


def ensure_schema() -> None:
    """Ensure the database schema exists.

    ضمان وجود مخطط قاعدة البيانات.
    """
    with _get_conn() as conn:
        conn.executescript(_SCHEMA_SQL)


# ============================================================================
# Conversation Operations (Iron Law #21 — Append Only)
# ============================================================================

def create_conversation(title: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Create a new conversation session.

    إنشاء جلسة محادثة جديدة.
    Returns the conversation_id (UUID).
    """
    ensure_schema()
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    meta = metadata or {}
    if title:
        meta["title"] = title
    meta["created_at_client"] = now

    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO conversations (id, title, created_at, last_activity, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                conv_id,
                title or "New conversation | محادثة جديدة",
                now,
                now,
                json.dumps(meta, ensure_ascii=False),
            ),
        )
    return conv_id


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    importance: int = 5,
) -> int:
    """Add a message to a conversation.

    إضافة رسالة إلى محادثة.

    Iron Law #21: append-only — never modifies existing messages.
    Returns the message ID.
    """
    ensure_schema()

    if role not in ("system", "user", "assistant", "tool"):
        raise ValueError(f"Invalid role: {role}. Must be one of: system, user, assistant, tool")

    meta = metadata or {}
    meta["added_at"] = datetime.now(timezone.utc).isoformat()
    now = datetime.now(timezone.utc).isoformat()

    with _get_conn() as conn:
        cur = conn.cursor()
        # Verify conversation exists and is not deleted
        cur.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND deleted_at IS NULL",
            (conversation_id,),
        )
        if not cur.fetchone():
            raise ValueError(f"Conversation not found or deleted: {conversation_id}")

        cur.execute(
            """
            INSERT INTO messages (conversation_id, role, content, metadata, created_at, importance)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content,
                json.dumps(meta, ensure_ascii=False),
                now,
                importance,
            ),
        )
        msg_id = cur.lastrowid

        # Update conversation's last_activity
        cur.execute(
            "UPDATE conversations SET last_activity = ? WHERE id = ?",
            (now, conversation_id),
        )

    return msg_id


def get_conversation(
    conversation_id: str,
    limit: int = 100,
    include_system: bool = True,
) -> List[Dict[str, Any]]:
    """Get all messages in a conversation.

    الحصول على جميع الرسائل في محادثة.

    Returns list of messages ordered by created_at ASC.
    """
    ensure_schema()

    with _get_conn() as conn:
        cur = conn.cursor()
        if include_system:
            cur.execute(
                """
                SELECT id, conversation_id, role, content, metadata, created_at, importance
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, conversation_id, role, content, metadata, created_at, importance
                FROM messages
                WHERE conversation_id = ? AND role != 'system'
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            )

        return [_row_to_message(row) for row in cur.fetchall()]


def list_conversations(limit: int = 50, include_deleted: bool = False) -> List[Dict[str, Any]]:
    """List all conversations (most recent first).

    عرض جميع المحادثات (الأحدث أولاً).
    """
    ensure_schema()

    with _get_conn() as conn:
        cur = conn.cursor()
        if include_deleted:
            cur.execute(
                """
                SELECT id, title, created_at, last_activity, metadata
                FROM conversations
                ORDER BY last_activity DESC
                LIMIT ?
                """,
                (limit,),
            )
        else:
            cur.execute(
                """
                SELECT id, title, created_at, last_activity, metadata
                FROM conversations
                WHERE deleted_at IS NULL
                ORDER BY last_activity DESC
                LIMIT ?
                """,
                (limit,),
            )

        results = []
        for row in cur.fetchall():
            meta = {}
            if row["metadata"]:
                try:
                    meta = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    pass

            results.append({
                "conversation_id": row["id"],
                "title": row["title"] or meta.get("title") or "Untitled | بدون عنوان",
                "created_at": row["created_at"],
                "last_activity": row["last_activity"],
                "metadata": meta,
            })
        return results


def delete_conversation(conversation_id: str, hard: bool = False) -> bool:
    """Delete a conversation.

    حذف محادثة.

    Args:
        conversation_id: ID to delete
        hard: If True, permanently delete. If False (default), soft delete.

    Iron Law #21: defaults to soft delete (sets deleted_at).
    Hard delete is opt-in for explicit user request.
    """
    ensure_schema()

    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        if not cur.fetchone():
            return False

        if hard:
            # Hard delete (explicit user request only)
            cur.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            cur.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        else:
            # Soft delete (Iron Law #21 default)
            cur.execute(
                "UPDATE conversations SET deleted_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), conversation_id),
            )
        return True


def conversation_exists(conversation_id: str) -> bool:
    """Check if a conversation exists and is not soft-deleted.

    التحقق من وجود محادثة (وغير محذوفة بشكل ناعم).
    """
    ensure_schema()
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND deleted_at IS NULL",
            (conversation_id,),
        )
        return cur.fetchone() is not None


def get_conversation_count() -> int:
    """Get total number of active conversations.

    عدد المحادثات النشطة الإجمالي.
    """
    ensure_schema()
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM conversations WHERE deleted_at IS NULL")
        row = cur.fetchone()
        return row["cnt"] if row else 0


def get_conversation_summary(conversation_id: str) -> Dict[str, Any]:
    """Get a summary of a conversation (no messages, just metadata).

    الحصول على ملخص محادثة (بدون رسائل، فقط البيانات الوصفية).
    """
    ensure_schema()
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.id, c.title, c.created_at, c.last_activity, c.metadata, c.deleted_at,
                   (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count
            FROM conversations c
            WHERE c.id = ?
            """,
            (conversation_id,),
        )
        row = cur.fetchone()
        if not row:
            return {}

        meta = {}
        if row["metadata"]:
            try:
                meta = json.loads(row["metadata"])
            except json.JSONDecodeError:
                pass

        return {
            "conversation_id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "last_activity": row["last_activity"],
            "deleted": row["deleted_at"] is not None,
            "message_count": row["message_count"],
            "metadata": meta,
        }


def _row_to_message(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite Row to a message dict.

    تحويل صف قاعدة البيانات إلى قاموس رسالة.
    """
    meta = {}
    if row["metadata"]:
        try:
            meta = json.loads(row["metadata"])
        except json.JSONDecodeError:
            meta = {"_raw": row["metadata"]}

    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "role": row["role"],
        "content": row["content"],
        "metadata": meta,
        "created_at": row["created_at"],
        "importance": row["importance"],
    }


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify memory operations work end-to-end.

    التحقق من عمليات الذاكرة تعمل من البداية للنهاية.
    """
    print("Running memory self-tests...")
    print("تشغيل اختبارات الذاكرة الذاتية...")

    passed = 0
    failed = 0

    try:
        # Test 1: Schema creation
        ensure_schema()
        passed += 1
        print(f"  ✓ ensure_schema")

        # Test 2: Create conversation
        cid = create_conversation(title="Test Conversation | محادثة اختبار")
        if cid and len(cid) == 36:
            passed += 1
            print(f"  ✓ create_conversation: {cid[:8]}...")
        else:
            failed += 1
            print(f"  ✗ create_conversation: {cid}")

        # Test 3: Add messages
        m1 = add_message(cid, "user", "Hello Wolf! | مرحباً يا ذئب!")
        m2 = add_message(cid, "assistant", "Hello! How can I help? | مرحباً! كيف أساعدك؟",
                        metadata={"tokens": 10, "model": "alpha-wolf-agent"})
        m3 = add_message(cid, "tool", "Read result: success | نتيجة القراءة: نجح",
                        metadata={"tool_name": "read_file"})
        if m1 and m2 and m3:
            passed += 1
            print(f"  ✓ add_message: {m1}, {m2}, {m3}")
        else:
            failed += 1
            print(f"  ✗ add_message failed")

        # Test 4: Retrieve full conversation
        msgs = get_conversation(cid)
        if len(msgs) == 3:
            roles = [m["role"] for m in msgs]
            if roles == ["user", "assistant", "tool"]:
                passed += 1
                print(f"  ✓ get_conversation: 3 messages in order")
            else:
                failed += 1
                print(f"  ✗ wrong roles: {roles}")
        else:
            failed += 1
            print(f"  ✗ get_conversation: {len(msgs)} messages")

        # Test 5: Retrieve excluding system (still 3 since we didn't add system)
        msgs2 = get_conversation(cid, include_system=False)
        if len(msgs2) == 3:
            passed += 1
            print(f"  ✓ get_conversation exclude system")
        else:
            failed += 1
            print(f"  ✗ exclude system: {len(msgs2)}")

        # Test 6: List conversations
        convs = list_conversations(limit=10)
        if any(c["conversation_id"] == cid for c in convs):
            passed += 1
            print(f"  ✓ list_conversations: found")
        else:
            failed += 1
            print(f"  ✗ list_conversations: not found in {len(convs)}")

        # Test 7: Conversation summary
        summary = get_conversation_summary(cid)
        if summary.get("message_count") == 3 and not summary.get("deleted"):
            passed += 1
            print(f"  ✓ get_conversation_summary: {summary['message_count']} msgs")
        else:
            failed += 1
            print(f"  ✗ summary: {summary}")

        # Test 8: conversation_exists
        if conversation_exists(cid):
            passed += 1
            print(f"  ✓ conversation_exists")
        else:
            failed += 1
            print(f"  ✗ conversation_exists: False")

        # Test 9: Soft delete
        if delete_conversation(cid):
            if not conversation_exists(cid):
                passed += 1
                print(f"  ✓ soft delete: hidden from default queries")
            else:
                failed += 1
                print(f"  ✗ soft delete: still exists")
        else:
            failed += 1
            print(f"  ✗ delete_conversation: returned False")

        # Test 10: Include deleted in list
        all_convs = list_conversations(include_deleted=True)
        if any(c["conversation_id"] == cid for c in all_convs):
            passed += 1
            print(f"  ✓ list include_deleted: found")
        else:
            failed += 1
            print(f"  ✗ list include_deleted: not found")

        # Test 11: Add to deleted conversation should fail
        try:
            add_message(cid, "user", "should fail")
            failed += 1
            print(f"  ✗ add_message to deleted should have raised")
        except ValueError:
            passed += 1
            print(f"  ✓ add_message to deleted raises ValueError")

        # Cleanup: hard delete the test conversation
        delete_conversation(cid, hard=True)

    except Exception as e:
        failed += 1
        print(f"  ✗ exception: {type(e).__name__}: {e}")

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()
