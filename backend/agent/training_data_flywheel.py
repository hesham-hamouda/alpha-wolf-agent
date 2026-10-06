#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Training Data Flywheel | دولاب بيانات التدريب
==================================================================
Convert successful conversations (overall_score >= threshold) into JSONL
training data for future fine-tunes.

Output format matches the standard LLMs fine-tuning chat-completions schema:
{"messages": [{"role": "system", ...}, {"role": "user", ...},
              {"role": "assistant", ...}]}

Generated files live in `<workspace>/data/training_data/auto/` (NOT body —
Iron Law #42). Safe to inspect, safe to delete (we don't touch existing
files unless explicitly asked).

Iron Laws Applied:
- #15 (Verify)    : self_test in __main__
- #21 (NO Delete) : never overwrites existing files (timestamp-suffixed)
- #33 (Lessons)   : bilingual docstrings
- #42 (Storage)   : workspace `data/training_data/auto/`, NOT body
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.agent import memory as mem
from backend.agent import self_evaluator

logger = logging.getLogger("alpha_wolf.training_flywheel")

# Default workspace path (NOT body)
TRAINING_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "training_data" / "auto"
)


# ============================================================================
# Formatting
# ============================================================================

def _format_conversation_for_training(conv_id: str) -> Optional[Dict[str, Any]]:
    """Convert one conversation (by id) into the JSONL training schema.

    تُحوِّل محادثة إلى صيغة تدريب JSONL.
    """
    messages_raw = mem.get_conversation(conv_id)
    if not messages_raw:
        return None

    msgs: List[Dict[str, Any]] = []
    for m in messages_raw:
        role = m.get("role", "")
        content = m.get("content", "") or ""
        if role not in ("system", "user", "assistant", "tool"):
            continue
        # Skip empty assistant turns (cut-off)
        if role == "assistant" and len(content) < 10:
            continue
        msg: Dict[str, Any] = {"role": role, "content": content}
        # Annotate tool execution results into the assistant turn
        if role == "assistant" and m.get("tool_calls"):
            for tc in (m["tool_calls"] or []):
                if isinstance(tc, dict):
                    name = tc.get("function", {}).get("name") or tc.get("name")
                    if name:
                        msg["content"] += f"\n[Tool used: {name}]"
        msgs.append(msg)
    if len(msgs) < 2:
        return None
    return {"messages": msgs}


# ============================================================================
# Export
# ============================================================================

def export_successful_conversations(
    min_score: float = 7.0,
    output_file: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Export successful conversations as JSONL training data.

    تصدير المحادثات الناجحة كبيانات تدريب JSONL.

    Args:
        min_score  : minimum overall_score to qualify (default 7)
        output_file: optional custom output filename
        limit      : maximum to export (default 100)

    Returns:
        dict with success / file_path / count / total_size_kb.
    """
    history = self_evaluator.get_evaluation_history(limit=max(200, limit * 2))

    # Filter by score
    successful = [ev for ev in history if ev.get("overall_score", 0) >= min_score]

    if not successful:
        return {
            "success": False,
            "error": f"No conversations with overall_score >= {min_score} (found {len(history)} evaluations)",
            "count": 0,
        }

    # Sort by score desc, take top `limit`
    successful.sort(key=lambda e: -e.get("overall_score", 0))
    successful = successful[:limit]

    # Fetch full conversation text per id
    training_examples: List[Dict[str, Any]] = []
    for ev in successful:
        cid = ev.get("conversation_id")
        if not cid:
            continue
        ex = _format_conversation_for_training(cid)
        if ex:
            ex["_meta"] = {
                "conversation_id": cid,
                "overall_score": ev.get("overall_score"),
                "evaluated_at": ev.get("evaluated_at"),
            }
            training_examples.append(ex)

    if not training_examples:
        return {
            "success": False,
            "error": "No training examples could be extracted (DB empty?)",
            "count": 0,
        }

    # Iron Law #21: never overwrite an existing file.
    # Default filename includes a timestamp so collisions are impossible.
    TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = output_file or f"alpha_wolf_auto_{timestamp}.jsonl"
    file_path = TRAINING_DATA_DIR / filename
    if file_path.exists():
        suffix = 1
        while True:
            candidate = file_path.with_name(
                f"{file_path.stem}__{suffix}{file_path.suffix}"
            )
            if not candidate.exists():
                file_path = candidate
                break
            suffix += 1

    # Write JSONL
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            for example in training_examples:
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
    except OSError as e:
        return {
            "success": False,
            "error": f"Write failed: {type(e).__name__}: {e}",
        }

    total_size = file_path.stat().st_size
    return {
        "success": True,
        "file_path": str(file_path),
        "count": len(training_examples),
        "total_size_kb": round(total_size / 1024, 2),
        "min_score": min_score,
        "avg_score": round(
            sum(ev.get("overall_score", 0) for ev in successful) / len(successful),
            2,
        ),
    }


def list_training_files() -> List[Dict[str, Any]]:
    """List all auto-generated training data files.

    قائمة ملفات بيانات التدريب المُنشأة تلقائياً.
    """
    if not TRAINING_DATA_DIR.exists():
        return []
    files: List[Dict[str, Any]] = []
    for f in sorted(TRAINING_DATA_DIR.glob("*.jsonl"), reverse=True):
        try:
            lines = sum(1 for _ in open(f, encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            lines = -1
        files.append({
            "path": str(f),
            "size_kb": round(f.stat().st_size / 1024, 2),
            "line_count": lines,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return files


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def self_test() -> bool:
    """Verify flywheel pieces (Iron Law #15)."""
    print("Running training_data_flywheel self-tests...")
    ok = True
    try:
        # Test 1: training dir resolves (we'll create parent on demand)
        try:
            TRAINING_DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
            if TRAINING_DATA_DIR.parent.exists():
                print(f"  ✓ training dir parent ready: {TRAINING_DATA_DIR.parent}")
            else:
                print(f"  ✗ training dir parent could not be created")
                ok = False
        except OSError as e:
            print(f"  ✗ training dir parent mkdir: {e}")
            ok = False

        # Test 2: list_training_files returns a list
        files = list_training_files()
        if isinstance(files, list):
            print(f"  ✓ list_training_files ({len(files)} entries)")
        else:
            print("  ✗ list_training_files not a list")
            ok = False

        # Test 3: empty/min_score returns graceful error
        r = export_successful_conversations(min_score=999.0)
        if not r.get("success"):
            print(f"  ✓ export with min_score=999 returns error gracefully")
        else:
            print(f"  ✗ export with min_score=999 unexpectedly succeeded")
            ok = False

        # Test 4: format_conversation for unknown id
        r2 = _format_conversation_for_training("nonexistent_conv_id")
        if r2 is None:
            print("  ✓ format_conversation handles missing id")
        else:
            print(f"  ✗ format_conversation returned data for missing id")
            ok = False

    except Exception as e:
        print(f"  ✗ exception: {type(e).__name__}: {e}")
        ok = False

    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)