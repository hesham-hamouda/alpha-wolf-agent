#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Auto LoRA Trainer (SCAFFOLDING) | مدرب LoRA التلقائي
=========================================================================
Pipeline for self-improvement via LoRA training.

SAFETY (Iron Law #21 + #41 + #50):
- This module SCAFFOLDS the pipeline but does NOT train by default.
- Real LoRA training requires:
  1. ALPHA_WOLF_TRAIN_TOKEN env var matching the request's confirm_token, AND
  2. unsloth + peft + bitsandbytes installed, AND
  3. ~30 min of GPU time on a 16GB+ VRAM GPU.
- Real deployment (merge + restart Ollama) requires ALPHA_WOLF_DEPLOY_TOKEN.

Workflow scaffolded:
1. analyze_weaknesses()       — read self_evaluator history
2. generate_training_examples_for_weakness()  — extract conversations
3. train_lora()               — DRY-RUN unless token matches
4. deploy_lora()              — DRY-RUN unless token matches

Iron Laws Applied:
- #21 (NO Delete)  : never trains/deploys without explicit token
- #41 (Conflict)   : returns clear "blocked" reason
- #42 (Storage)    : adapters at workspace `data/lora_adapters/`
- #47 (Bilingual)  : AR + EN docstrings
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from backend.agent import self_evaluator, training_data_flywheel

logger = logging.getLogger("alpha_wolf.auto_lora")

# Adapter directory (workspace, NOT body — Iron Law #42)
ADAPTERS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "lora_adapters"
)


# ============================================================================
# Analysis
# ============================================================================

def analyze_weaknesses() -> Dict[str, Any]:
    """Analyze self-evaluation history to identify agent weaknesses.

    تحليل نقاط الضعف من سجل التقييم الذاتي.

    Returns dict with weak_areas (list of {type, frequency, example_lesson}),
    recommended_training_size, estimated_train_time_minutes.
    """
    history = self_evaluator.get_evaluation_history(limit=50)

    if not history:
        return {
            "weak_areas": [],
            "evaluations_analyzed": 0,
            "message": (
                "No evaluations yet. Run /v1/eval/{conv_id} after several "
                "conversations first. لا توجد تقييمات بعد."
            ),
            "gpu_required": "RTX 3060+ (16GB VRAM recommended)",
        }

    # Aggregate lessons by type
    issues_by_type: Dict[str, list] = {}
    for ev in history:
        for lesson in ev.get("lessons", []) or []:
            t = lesson.get("type")
            if t:
                issues_by_type.setdefault(t, []).append(lesson)

    weak_areas = []
    for issue_type, lessons in issues_by_type.items():
        weak_areas.append({
            "type": issue_type,
            "frequency": len(lessons),
            "example_lesson": lessons[0].get("detail", "") if lessons else "",
        })
    weak_areas.sort(key=lambda x: -x["frequency"])

    n_examples_needed = max(50, len(history) * 2)
    estimated_minutes = int(max(15, n_examples_needed * 0.5))

    return {
        "weak_areas": weak_areas,
        "evaluations_analyzed": len(history),
        "recommended_training_size": n_examples_needed,
        "estimated_train_time_minutes": estimated_minutes,
        "gpu_required": "RTX 3060+ (16GB VRAM recommended)",
    }


def generate_training_examples_for_weakness(
    weakness_type: str,
    limit: int = 50,
) -> Dict[str, Any]:
    """Generate training examples targeting a specific weakness.

    ينشئ أمثلة تدريب لاستهداف نقطة ضعف محددة.

    Currently delegates to the flywheel (extracts all high-score conversations
    as baseline). Future: synthesize counter-examples specifically for
    `weakness_type`.
    """
    result = training_data_flywheel.export_successful_conversations(
        min_score=7.0,
        limit=limit,
        output_file=f"targeted_{weakness_type}.jsonl",
    )
    return {
        "weakness_type": weakness_type,
        "examples_generated": result.get("count", 0),
        "file_path": result.get("file_path"),
        "success": result.get("success", False),
        "note": (
            "Future: synthesize examples specifically for " + weakness_type +
            " (currently uses successful conversations as baseline)."
        ),
    }


# ============================================================================
# Training (scaffolded — BLOCKED without token)
# ============================================================================

def train_lora(
    base_model: str = "llama3.1:8b",
    adapter_name: str = "v_self_improve",
    training_file: str = "",
    epochs: int = 1,
    learning_rate: float = 2e-4,
    batch_size: int = 2,
    confirm_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Train a LoRA adapter on successful conversations.

    تدريب LoRA adapter (مسودة — يتطلب توكن صريح).

    SAFETY (Iron Law #21 + #41):
    - Without `ALPHA_WOLF_TRAIN_TOKEN` matching `confirm_token`, returns a
      dry-run analysis WITHOUT training.
    - With matching token, returns the next_steps to perform training manually
      (we do not silently spin up GPU jobs from a chat).

    NOTE: This round ships scaffolding only. Actual training requires
    `unsloth` + `peft` + `bitsandbytes` installed (separate effort).
    """
    expected = os.environ.get("ALPHA_WOLF_TRAIN_TOKEN", "").strip()
    dry_run = {
        "would_train_base_model": base_model,
        "would_create_adapter": adapter_name,
        "training_file": training_file or "<use export_successful_conversations>",
        "epochs": epochs,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "estimated_time_minutes": epochs * 15,
        "estimated_vram_gb": 16,
    }

    if not expected or expected != confirm_token:
        return {
            "success": False,
            "blocked": True,
            "reason": (
                "ALPHA_WOLF_TRAIN_TOKEN not set or doesn't match "
                "confirm_token. Dry-run only."
            ),
            "dry_run": dry_run,
        }

    # Token matched — but actual training is NOT in this round.
    return {
        "success": False,
        "blocked": True,
        "reason": (
            "LoRA training scaffold only — actual training is not "
            "implemented in this round. Use the steps below."
        ),
        "next_steps": [
            "1. Install unsloth: pip install unsloth peft bitsandbytes",
            "2. Use existing scripts/train_v2_tools.py as template",
            "3. Pass --data_path <exported_jsonl>",
            "4. Train with adapter_name='" + adapter_name + "' and merge",
            "5. Export GGUF + create Ollama model",
            "6. Restart llama-server with new model",
        ],
        "dry_run": dry_run,
    }


# ============================================================================
# Deployment (scaffolded — BLOCKED without token)
# ============================================================================

def deploy_lora(
    adapter_name: str,
    confirm_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Deploy a trained LoRA adapter (merge + restart Ollama).

    نشر adapter مدرب (مسودة — يتطلب توكن).

    SAFETY: requires ALPHA_WOLF_DEPLOY_TOKEN. Without it, returns dry-run.
    """
    expected = os.environ.get("ALPHA_WOLF_DEPLOY_TOKEN", "").strip()
    dry_run = {
        "would_merge_adapter": adapter_name,
        "would_create_ollama_model": f"alpha-wolf-{adapter_name}",
        "would_replace_existing_model": False,
        "note": "Create as new model first; switch after validation.",
    }

    if not expected or expected != confirm_token:
        return {
            "success": False,
            "blocked": True,
            "reason": (
                "ALPHA_WOLF_DEPLOY_TOKEN not set or doesn't match. "
                "Dry-run only."
            ),
            "dry_run": dry_run,
        }

    return {
        "success": False,
        "reason": "Deployment pipeline not implemented in this round",
        "next_steps": "Use existing scripts/merge_v8_wolf.py as reference",
        "dry_run": dry_run,
    }


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def self_test() -> bool:
    """Verify auto_lora pieces (Iron Law #15)."""
    print("Running auto_lora_trainer self-tests...")
    ok = True
    try:
        # Test 1: analyze_weaknesses works even with no history
        r = analyze_weaknesses()
        if "weak_areas" in r and "gpu_required" in r:
            print("  ✓ analyze_weaknesses returns expected keys")
        else:
            print(f"  ✗ analyze_weaknesses missing keys: {r.keys()}")
            ok = False

        # Test 2: train_lora WITHOUT token returns blocked
        r = train_lora(adapter_name="test_no_token", confirm_token=None)
        if r.get("blocked") and r.get("dry_run"):
            print("  ✓ train_lora blocked without token (dry-run)")
        else:
            print(f"  ✗ train_lora not blocked: {r}")
            ok = False

        # Test 3: train_lora with WRONG token still blocked
        r = train_lora(adapter_name="test_wrong_token", confirm_token="WRONG_TOKEN_123")
        if r.get("blocked"):
            print("  ✓ train_lora blocked with wrong token")
        else:
            print(f"  ✗ train_lora allowed with wrong token: {r}")
            ok = False

        # Test 4: deploy_lora WITHOUT token returns blocked
        r = deploy_lora(adapter_name="test_no_deploy_token", confirm_token=None)
        if r.get("blocked") and r.get("dry_run"):
            print("  ✓ deploy_lora blocked without token")
        else:
            print(f"  ✗ deploy_lora not blocked: {r}")
            ok = False

        # Test 5: ADAPTERS_DIR is workspace, not body
        if "body" not in str(ADAPTERS_DIR).lower():
            print(f"  ✓ ADAPTERS_DIR in workspace ({ADAPTERS_DIR})")
        else:
            print(f"  ✗ ADAPTERS_DIR in body: {ADAPTERS_DIR}")
            ok = False

        # Test 6: generate_training_examples_for_weakness handles unknown types
        r = generate_training_examples_for_weakness("unknown_type_xyz")
        if "weakness_type" in r:
            print(f"  ✓ generate_training_examples_for_weakness returns dict")
        else:
            print(f"  ✗ generate_training_examples wrong shape: {r}")
            ok = False

    except Exception as e:
        print(f"  ✗ exception: {type(e).__name__}: {e}")
        ok = False

    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)