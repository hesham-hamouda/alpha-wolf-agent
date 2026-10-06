#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Self Evaluator | المقيِّم الذاتي
=====================================================
Auto-rate each conversation and extract lessons.

After every conversation ends, the Wolf analyzes:
- Tool selection accuracy (correct vs invalid tool names)
- Response quality (length, structure, language match)
- Refusal patterns
- User language vs response language

Output:
- Structured evaluation persisted in `conversations.metadata.self_evaluation`.
- Aggregated lessons available via `/v1/eval/suggestions`.

Iron Laws Applied:
- #15 (Verify)    : self_test in __main__
- #21 (NO Delete) : never deletes — only appends to metadata
- #33 (Lessons)   : bilingual docstrings
- #41 (Conflict)  : returns detailed context on failures
- #47 (Bilingual) : AR + EN user-facing strings
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.agent import memory as mem

logger = logging.getLogger("alpha_wolf.self_eval")


# ============================================================================
# Heuristics (lightweight, no LLM needed)
# ============================================================================

_REFUSAL_PATTERNS_AR = [
    r"لا أستطيع",
    r"لا يمكنني",
    r"عذراً، لا يمكن",
    r"معذرة، لا أستطيع",
    r"غير قادر على",
]
_REFUSAL_PATTERNS_EN = [
    r"I cannot",
    r"I am unable",
    r"I'm unable",
    r"I can't help",
    r"sorry, I can't",
]
_REFUSAL_PATTERNS = _REFUSAL_PATTERNS_AR + _REFUSAL_PATTERNS_EN

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def _is_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def _refusal_count(messages: List[Dict[str, Any]]) -> int:
    n = 0
    for m in messages:
        if m.get("role") == "assistant":
            txt = m.get("content", "") or ""
            if any(re.search(p, txt, re.IGNORECASE) for p in _REFUSAL_PATTERNS):
                n += 1
    return n


def _avg_assistant_length(messages: List[Dict[str, Any]]) -> float:
    lens = [
        len(m.get("content", "") or "")
        for m in messages if m.get("role") == "assistant"
    ]
    return sum(lens) / max(1, len(lens))


def _user_lang(messages: List[Dict[str, Any]]) -> str:
    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        return "unknown"
    ar = sum(1 for m in user_msgs if _is_arabic(m.get("content", "")))
    return "ar" if ar / len(user_msgs) > 0.5 else "en"


def _response_lang(messages: List[Dict[str, Any]]) -> str:
    asst_msgs = [m for m in messages if m.get("role") == "assistant"]
    if not asst_msgs:
        return "unknown"
    ar = sum(1 for m in asst_msgs if _is_arabic(m.get("content", "")))
    return "ar" if ar / len(asst_msgs) > 0.5 else "en"


def _tool_accuracy(messages: List[Dict[str, Any]]) -> tuple[float, int]:
    """Compute tool-call accuracy against the live tool registry.

    Returns (correct_ratio, total_calls).
    """
    tool_calls: List[Dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "assistant":
            tcs = m.get("tool_calls") or []
            for tc in tcs:
                if isinstance(tc, dict):
                    # native OpenAI style
                    name = tc.get("function", {}).get("name") or tc.get("name")
                    if name:
                        tool_calls.append({"name": name})
                    continue
                # legacy XML / parsed
                n = getattr(tc, "name", None)
                if n:
                    tool_calls.append({"name": n})
    total = len(tool_calls)
    if total == 0:
        return 1.0, 0
    try:
        from backend.agent.tools import TOOL_SPECS
        valid = {s.name for s in TOOL_SPECS}
    except Exception:
        valid = set()
    correct = sum(1 for tc in tool_calls if tc.get("name") in valid)
    return (correct / total) if total else 1.0, total


# ============================================================================
# Conversation Evaluation
# ============================================================================

def evaluate_conversation(conv_id: str) -> Dict[str, Any]:
    """Auto-evaluate a completed conversation.

    تقييم تلقائي لمحادثة منتهية.

    Returns dict with: overall_score (0-10), tool_accuracy, refusal_rate,
    language_match, lessons.
    """
    if not mem.conversation_exists(conv_id):
        return {"success": False, "error": f"Conversation not found: {conv_id}"}

    messages = mem.get_conversation(conv_id)
    if not messages:
        return {
            "success": False,
            "error": "Conversation has no messages yet — only persists after first message",
        }

    # 1. Tool selection accuracy
    tool_acc, tool_total = _tool_accuracy(messages)

    # 2. Refusal rate
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    ref_count = _refusal_count(messages)
    refusal_rate = (ref_count / len(assistant_msgs)) if assistant_msgs else 0

    # 3. Language match
    u_lang = _user_lang(messages)
    r_lang = _response_lang(messages)
    lang_match = u_lang == r_lang

    # 4. Average response length
    avg_len = _avg_assistant_length(messages)
    length_ok = avg_len >= 50  # too short answers usually mean refusal/cutoff

    # 5. Overall score (weighted heuristic)
    overall_score = (
        tool_acc * 4          # 40% — tool accuracy
        + (1 - refusal_rate) * 3  # 30% — non-refusal
        + (1.0 if lang_match else 0.5) * 2  # 20% — language match
        + (1.0 if length_ok else 0.5) * 1  # 10% — substantive response
    )
    # Round to 2 decimals
    overall_score = round(overall_score, 2)

    # 6. Extract lessons
    lessons: List[Dict[str, Any]] = []
    if refusal_rate > 0.3:
        lessons.append({
            "type": "high_refusal_rate",
            "detail": (
                f"{int(refusal_rate * 100)}% of assistant turns were refusals. "
                "Strengthen forced-call fallback."
            ),
        })
    if not lang_match and u_lang != "unknown" and r_lang != "unknown":
        lessons.append({
            "type": "language_mismatch",
            "detail": f"User wrote in {u_lang}, agent responded in {r_lang}.",
        })
    if tool_acc < 0.8 and tool_total > 0:
        lessons.append({
            "type": "tool_accuracy_low",
            "detail": (
                f"Only {int(tool_acc * 100)}% of tool calls were valid "
                f"({tool_total} total). Review tool descriptions."
            ),
        })
    if not length_ok:
        lessons.append({
            "type": "short_responses",
            "detail": (
                f"Avg assistant length is {int(avg_len)} chars "
                "(target ≥ 50)."
            ),
        })

    # 7. Persist into conversations.metadata (Iron Law #21: append-only)
    evaluation = {
        "conversation_id": conv_id,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "tool_accuracy": round(tool_acc, 3),
        "tool_call_count": tool_total,
        "refusal_rate": round(refusal_rate, 3),
        "refusal_count": ref_count,
        "language_match": lang_match,
        "user_lang": u_lang,
        "response_lang": r_lang,
        "avg_response_length": round(avg_len, 1),
        "overall_score": overall_score,
        "lessons": lessons,
        "message_count": len(messages),
        "assistant_count": len(assistant_msgs),
    }
    try:
        with mem._get_conn() as conn:
            row = conn.execute(
                "SELECT metadata FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            if row is not None:
                meta_raw = row["metadata"] or "{}"
                try:
                    meta = json.loads(meta_raw)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
                # Append — never overwrite existing evaluations
                existing = meta.get("self_evaluation")
                if not isinstance(existing, list):
                    meta["self_evaluation"] = [evaluation]
                else:
                    meta["self_evaluation"] = existing + [evaluation]
                conn.execute(
                    "UPDATE conversations SET metadata = ? WHERE id = ?",
                    (json.dumps(meta, ensure_ascii=False), conv_id),
                )
                conn.commit()
    except Exception as e:
        logger.warning("Failed to persist evaluation for %s: %s", conv_id, e)

    return {"success": True, "evaluation": evaluation}


# ============================================================================
# History & Suggestions
# ============================================================================

def get_evaluation_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Get the latest self-evaluation per conversation.

    جلب آخر تقييم ذاتي لكل محادثة.
    """
    try:
        with mem._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, metadata FROM conversations
                WHERE deleted_at IS NULL AND metadata LIKE '%self_evaluation%'
                ORDER BY last_activity DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
    except Exception as e:
        logger.warning("get_evaluation_history failed: %s", e)
        return []

    history: List[Dict[str, Any]] = []
    for r in rows:
        try:
            meta = json.loads(r["metadata"] or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        evs = meta.get("self_evaluation")
        if isinstance(evs, list) and evs:
            history.append(evs[-1])  # latest only
        elif isinstance(evs, dict):
            history.append(evs)
    return history


def get_improvement_suggestions() -> List[str]:
    """Aggregate lessons into actionable suggestions.

    تجميع الدروس في اقتراحات قابلة للتنفيذ.
    """
    history = get_evaluation_history(limit=20)
    if not history:
        return ["No evaluations yet — let the agent run for a while first. لا توجد تقييمات بعد."]

    # Aggregate
    issues: Dict[str, int] = {}
    for ev in history:
        for lesson in ev.get("lessons", []):
            t = lesson.get("type", "unknown")
            issues[t] = issues.get(t, 0) + 1

    suggestions: List[str] = []
    avg_score = sum(ev.get("overall_score", 0) for ev in history) / len(history)
    suggestions.append(
        f"📊 Average score: {avg_score:.2f}/10 over {len(history)} conversations"
    )

    for issue_type, count in sorted(issues.items(), key=lambda x: -x[1]):
        if count < 3:
            continue
        if issue_type == "high_refusal_rate":
            suggestions.append(
                f"⚠️ High refusal rate in {count} conversations — strengthen forced-call fallback"
            )
        elif issue_type == "language_mismatch":
            suggestions.append(
                f"⚠️ Language mismatch in {count} conversations — improve language detection"
            )
        elif issue_type == "tool_accuracy_low":
            suggestions.append(
                f"⚠️ Tool accuracy low in {count} conversations — review tool descriptions"
            )
        elif issue_type == "short_responses":
            suggestions.append(
                f"⚠️ Short responses in {count} conversations — check for accidental cutoffs"
            )

    if not suggestions[1:]:
        suggestions.append("✅ No recurring issues detected in the last 20 conversations")
    return suggestions


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def self_test() -> bool:
    """Verify self-evaluator pieces (Iron Law #15)."""
    print("Running self_evaluator self-tests...")
    ok = True
    try:
        # Test 1: language detection
        if _is_arabic("مرحبا"):
            print("  ✓ Arabic detection")
        else:
            print("  ✗ Arabic detection failed")
            ok = False
        if not _is_arabic("hello"):
            print("  ✓ English non-Arabic detection")
        else:
            print("  ✗ English wrongly detected as Arabic")
            ok = False

        # Test 2: refusal pattern detection
        msgs_refusal = [
            {"role": "user", "content": "Write a function"},
            {"role": "assistant", "content": "I cannot write code for you."},
        ]
        if _refusal_count(msgs_refusal) == 1:
            print("  ✓ refusal_count (EN)")
        else:
            print(f"  ✗ refusal_count (EN): {_refusal_count(msgs_refusal)}")
            ok = False

        msgs_refusal_ar = [
            {"role": "user", "content": "اكتب لي دالة"},
            {"role": "assistant", "content": "لا أستطيع كتابة برناج"},
        ]
        if _refusal_count(msgs_refusal_ar) == 1:
            print("  ✓ refusal_count (AR)")
        else:
            print(f"  ✗ refusal_count (AR): {_refusal_count(msgs_refusal_ar)}")
            ok = False

        # Test 3: language match
        msgs_match = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        if _user_lang(msgs_match) == "en" and _response_lang(msgs_match) == "en":
            print("  ✓ language match (EN)")
        else:
            print(f"  ✗ language match (EN): u={_user_lang(msgs_match)} r={_response_lang(msgs_match)}")
            ok = False

        msgs_mismatch = [
            {"role": "user", "content": "مرحبا كيف حالك"},
            {"role": "assistant", "content": "Hi how are you doing today"},
        ]
        if _user_lang(msgs_mismatch) == "ar" and _response_lang(msgs_mismatch) == "en":
            print("  ✓ language mismatch detection")
        else:
            print(f"  ✗ language mismatch failed")
            ok = False

        # Test 4: avg length
        avg = _avg_assistant_length([
            {"role": "assistant", "content": "hello"},  # 5
            {"role": "assistant", "content": "hello world"},  # 11
        ])
        if abs(avg - 8.0) < 0.1:
            print(f"  ✓ avg_assistant_length = {avg}")
        else:
            print(f"  ✗ avg_assistant_length = {avg} (expected 8.0)")
            ok = False

        # Test 5: improvement suggestions on empty history
        sugg = get_improvement_suggestions()
        if isinstance(sugg, list) and len(sugg) >= 1:
            print(f"  ✓ suggestions returns list ({len(sugg)} entries)")
        else:
            print("  ✗ suggestions failed")
            ok = False

        # Test 6: evaluate_conversation on non-existent conv
        r = evaluate_conversation("nonexistent_conv_id")
        if not r.get("success") and "not found" in str(r.get("error", "")).lower():
            print("  ✓ evaluate_conversation handles missing conv")
        else:
            print(f"  ✗ evaluate_conversation missing: {r}")
            ok = False

    except Exception as e:
        print(f"  ✗ exception: {type(e).__name__}: {e}")
        ok = False

    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)