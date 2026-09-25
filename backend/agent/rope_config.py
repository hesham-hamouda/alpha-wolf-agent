#!/usr/bin/env python3
r"""
Alpha Wolf Agent — RoPE Scaling Config | توسيع نافذة السياق
===========================================================
Context window expansion via RoPE (Rotary Position Embedding) scaling.

STATUS: FUTURE WORK — not enabled in the running model.

Why future:
- Current inference is via llama.cpp server with default context (128K native for Llama-3.1-8B)
- RoPE scaling requires switching to llama.cpp with `--rope-scaling` flag OR
  using HuggingFace Transformers with custom code
- User mentioned 500K context target (Quханд directive) — needs:
  - YaRN or NTK-aware scaling
  - Sufficient attention memory (~4GB for 500K @ 8B model)
  - Re-testing all evaluations at new context length

Iron Laws Applied:
- #15 (Verify)   : config_proposal() returns structured dict (testable)
- #22 (Autonomous): no actual model reload — just documentation + helper
- #41 (Conflict) : current limitation honestly disclosed
- #47 (Bilingual) : bilingual AR+EN (Iron Law #47)
- #48 (Separated) : config isolated from running inference (no side effects)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List


# ============================================================================
# Current State (read-only verification)
# ============================================================================

NATIVE_CONTEXT = 131_072     # Llama-3.1-8B native context (128K)
TARGET_CONTEXT = 524_288     # Quханд target (500K = 4× native)


# ============================================================================
# Configuration Proposal (FUTURE)
# ============================================================================

def config_proposal(target_context: int = TARGET_CONTEXT) -> Dict[str, Any]:
    """Return a configuration proposal for context window expansion.

    يُرجع اقتراح تكوين لتوسيع نافذة السياق.

    Three strategies are evaluated. Each has tradeoffs.

    Args:
        target_context: Desired context window in tokens (default 524288 = 500K).

    Returns:
        Dict with: current_state, strategies, recommendation, steps_to_enable
    """
    ratio = target_context / NATIVE_CONTEXT

    return {
        "current_state": {
            "native_context": NATIVE_CONTEXT,
            "current_context": int(os.environ.get("ALPHA_WOLF_CONTEXT", NATIVE_CONTEXT)),
            "engine": "llama.cpp (HTTP server)",
            "status": "DEFAULT — RoPE scaling NOT enabled",
        },
        "target": {
            "tokens": target_context,
            "ratio": ratio,
            "type": "YaRN" if ratio > 2 else "Linear",
        },
        "strategies": [
            {
                "name": "Linear Scaling (simplest)",
                "name_ar": "التحجيم الخطي (الأسهل)",
                "description": "Divides position IDs by ratio. Free, no retrain, but loses precision.",
                "factor": ratio,
                "use_case": "ratio < 2.0",
                "pros": ["Simple", "No retraining", "Works in llama.cpp with --rope-scaling linear"],
                "cons": ["Loses precision > 4x", "Model 'forgets' middle of long context"],
            },
            {
                "name": "YaRN (recommended)",
                "name_ar": "YaRN (موصى به)",
                "description": "Neural Tangent Kernel-aware scaling. Best quality/cost ratio.",
                "factor": ratio,
                "use_case": "ratio >= 2.0 (your case: 4x = 500K)",
                "pros": ["Best quality at long context", "No retraining", "Free"],
                "cons": [
                    "Requires llama.cpp built with RoPE scaling support",
                    "Memory overhead (~4GB attention @ 500K)",
                ],
            },
            {
                "name": "NTK-aware (alternative)",
                "name_ar": "NTK-aware (بديل)",
                "description": "Modifies base frequency. Slightly different quality curve.",
                "factor": ratio,
                "use_case": "ratio 1.5-4x",
                "pros": ["No retraining", "Fast", "Good middle ground"],
                "cons": ["Less tested than YaRN", "May need per-model tuning"],
            },
        ],
        "recommendation": "YaRN" if ratio >= 2 else "Linear",
        "recommendation_reason": (
            f"At ratio {ratio:.2f}x, YaRN provides the best precision at minimal cost. "
            f"Linear scaling would degrade precision noticeably."
        ),
        "steps_to_enable": [
            "1. Verify llama.cpp supports RoPE scaling (compile flag GGML_ROPE_SCALE):",
            "   `llama-server --version | grep -i rope`",
            "",
            "2. Build llama.cpp with RoPE scaling (if not already):",
            "   `cmake -B build -DGGML_ROPE_SCALE=ON && cmake --build build --config Release`",
            "",
            "3. Restart llama-server with scaling parameters:",
            "   `llama-server -m model.gguf --rope-scaling yarn --yarn-orig-ctx 131072 --yarn-ext-factor 4.0 --ctx-size 524288`",
            "",
            "4. Update ALPHA_WOLF_CONTEXT env var:",
            "   `set ALPHA_WOLF_CONTEXT=524288` (Windows) or `export ALPHA_WOLF_CONTEXT=524288` (Linux)",
            "",
            "5. Update FastAPI proxy timeout:",
            "   `LLAMACPP_TIMEOUT=300` (5 min for first 500K call)",
            "",
            "6. Re-run eval suite at new context length (Iron Law #15 verification):",
            "   `python -m backend.agent.memory` + `python -m backend.agent.live_context`",
            "",
            "7. Re-test memory for 500K conversations (Iron Law #15):",
            "   `python scripts/test_memory_persistence.py`",
        ],
        "ram_estimate": {
            "native_128k": "~8 GB VRAM (model + KV cache)",
            "yarn_500k": "~12-16 GB VRAM (4x KV cache)",
            "minimum_gpu": "RTX 5060 Ti (16 GB) — already owned",
        },
        "iron_law_41_disclosure": (
            "This proposal is NOT applied to the running model. "
            "Current model uses native 128K context via llama.cpp defaults. "
            "To enable 500K context, follow `steps_to_enable` above. "
            "Risk: enabling RoPE scaling without re-evaluating may cause "
            "silent quality degradation at long contexts (Iron Law #15)."
        ),
    }


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify config_proposal returns structured, valid output.

    التحقق من أن اقتراح التكوين يُرجع مخرجات صحيحة ومنظمة.
    """
    print("Running rope_config self-tests...")
    print("تشغيل اختبارات توسيع السياق...")

    passed = 0
    failed = 0

    try:
        proposal = config_proposal()

        # Check structure
        required_keys = ["current_state", "target", "strategies", "recommendation",
                         "steps_to_enable", "ram_estimate", "iron_law_41_disclosure"]
        for key in required_keys:
            if key in proposal:
                passed += 1
                print(f"  ✓ has key: {key}")
            else:
                failed += 1
                print(f"  ✗ missing key: {key}")

        # Check recommendation makes sense for 4x ratio
        if proposal["recommendation"] == "YaRN":
            passed += 1
            print(f"  ✓ recommendation = YaRN (correct for {proposal['target']['ratio']:.2f}x)")
        else:
            failed += 1
            print(f"  ✗ wrong recommendation: {proposal['recommendation']}")

        # Check steps are actionable
        if len(proposal["steps_to_enable"]) >= 5:
            passed += 1
            print(f"  ✓ steps_to_enable: {len(proposal['steps_to_enable'])} steps")
        else:
            failed += 1
            print(f"  ✗ steps_to_enable too few: {len(proposal['steps_to_enable'])}")

        # Check transparency (Iron Law #41)
        if "NOT applied" in proposal["iron_law_41_disclosure"]:
            passed += 1
            print(f"  ✓ iron_law_41_disclosure: honest")
        else:
            failed += 1
            print(f"  ✗ missing transparency")

    except Exception as e:
        failed += 1
        print(f"  ✗ exception: {type(e).__name__}: {e}")

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()