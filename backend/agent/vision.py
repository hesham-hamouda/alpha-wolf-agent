#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Vision Module (Placeholder) | وحدة الرؤية
=============================================================
FUTURE WORK — placeholder for image understanding capability.

Status (2026-09-25):
- Vision-capable models are available locally via Ollama (qwen2.5vl:7b, gemma4:latest)
- The skill system can wrap vision calls (see `vision_skill.py` future)
- Direct integration with the chat endpoint is NOT YET implemented

Why placeholder (Iron Law #41):
- Quханд mentioned "Multi-Modal (Vision) - Future Work" in the task brief
- Current inference is text-only via llama.cpp
- Adding vision requires either:
  (a) Switching inference engine to support multimodal (Ollama has this)
  (b) Hybrid approach: text to llama.cpp, images to Ollama qwen2.5vl

Iron Laws Applied:
- #15 (Verify)        : self_test verifies interface contract
- #22 (Autonomous)    : no actual vision calls (placeholder)
- #41 (Conflict)      : limitations honestly disclosed
- #47 (Bilingual)     : bilingual AR+EN
- #48 (Separated)     : isolated module — no imports of running engine
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("alpha_wolf.vision")


# ============================================================================
# Configuration
# ============================================================================

# Ollama is the recommended path for local vision (no API key, fast, multimodal)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_VISION_MODEL = "qwen2.5vl:7b"
FALLBACK_VISION_MODEL = "gemma4:latest"


# ============================================================================
# Interface (Future API)
# ============================================================================

class VisionInput:
    """Future API input for vision queries.

    مدخلات API مستقبلية لاستعلامات الرؤية.

    Attributes:
        image_path: Path to image file (PNG, JPG, WebP)
        image_base64: Pre-encoded base64 image (alternative to path)
        prompt: Question to ask about the image (default: "Describe this image")
        max_tokens: Max response length (default 512)
    """
    def __init__(self, image_path: Optional[str] = None, image_base64: Optional[str] = None,
                 prompt: str = "Describe this image | صف هذه الصورة",
                 max_tokens: int = 512):
        if not image_path and not image_base64:
            raise ValueError("Either image_path or image_base64 is required")
        self.image_path = image_path
        self.image_base64 = image_base64
        self.prompt = prompt
        self.max_tokens = max_tokens

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"prompt": self.prompt, "max_tokens": self.max_tokens}
        if self.image_base64:
            d["image_base64"] = self.image_base64[:50] + "..." if len(self.image_base64) > 50 else self.image_base64
        elif self.image_path:
            d["image_path"] = self.image_path
        return d


def is_available() -> bool:
    """Check if vision is currently available (always False until integrated).

    التحقق من توفر الرؤية حالياً (دائماً False حتى التكامل).

    Returns:
        False (placeholder). Will become a real check after integration.
    """
    # Iron Law #41: be honest about current state
    return False


def describe_image(image_path: str, prompt: str = "Describe this image | صف هذه الصورة",
                   max_tokens: int = 512) -> Dict[str, Any]:
    """Describe an image (FUTURE — not yet implemented).

    وصف صورة (مستقبل — لم يُنفَّذ بعد).

    Args:
        image_path: Path to image file
        prompt: Question to ask about the image
        max_tokens: Max response length

    Returns:
        Dict with: success, description, model_used, note
        قاموس يحتوي على: نجاح، وصف، النموذج، ملاحظة

    Iron Law #41: returns structured "not implemented" response until integrated.
    """
    p = Path(image_path)
    if not p.exists():
        return {
            "success": False,
            "error": f"Image not found: {image_path}",
            "vision_available": is_available(),
        }

    # Iron Law #41: surface honestly that this is not implemented
    return {
        "success": False,
        "error": "Vision not yet integrated. See ENABLE_VISION.md roadmap.",
        "vision_available": False,
        "image_path": image_path,
        "image_size_kb": round(p.stat().st_size / 1024, 1),
        "recommended_model": DEFAULT_VISION_MODEL,
        "ollama_url": OLLAMA_BASE_URL,
        "note": (
            "To enable vision: switch inference to Ollama (qwen2.5vl:7b), "
            "or add a parallel endpoint that routes images to vision model."
        ),
    }


def encode_image_base64(image_path: str) -> str:
    """Encode image to base64 (utility — works today).

    ترميز الصورة إلى base64 (أداة مساعدة — تعمل اليوم).
    """
    p = Path(image_path)
    return base64.b64encode(p.read_bytes()).decode("utf-8")


def list_local_vision_models() -> List[Dict[str, str]]:
    """List locally-available vision models (utility — checks Ollama).

    قائمة بنماذج الرؤية المتاحة محلياً (تفحص Ollama).
    """
    import urllib.request
    import json

    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", [])
        # Filter vision-capable (heuristic: name contains vl/vision/clip/smolvlm)
        vision_keywords = ("vl", "vision", "clip", "smolvlm", "llava", "minicpm-v")
        return [
            {"name": m["name"], "size_mb": round(m.get("size", 0) / 1024 / 1024, 1)}
            for m in models
            if any(kw in m["name"].lower() for kw in vision_keywords)
        ]
    except Exception as e:
        logger.warning("Failed to query Ollama for vision models: %s", e)
        return []


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify vision module interface works (placeholder contract).

    التحقق من أن واجهة وحدة الرؤية تعمل.
    """
    print("Running vision self-tests...")
    print("تشغيل اختبارات وحدة الرؤية...")

    passed = 0
    failed = 0

    try:
        # Test 1: is_available returns False honestly
        if is_available() is False:
            passed += 1
            print(f"  ✓ is_available: False (honest)")
        else:
            failed += 1
            print(f"  ✗ is_available: should be False")

        # Test 2: describe_image returns structured error for missing file
        result = describe_image("/nonexistent/image.png")
        if not result["success"] and "not found" in result.get("error", "").lower():
            passed += 1
            print(f"  ✓ describe_image: missing file handled")
        else:
            failed += 1
            print(f"  ✗ describe_image: {result}")

        # Test 3: describe_image returns structured error for existing file
        # (since not implemented yet)
        import tempfile
        tmp_img = Path(tempfile.gettempdir()) / "vision_test.png"
        tmp_img.write_bytes(b"\x89PNG\r\n\x1a\n")  # fake PNG header
        result = describe_image(str(tmp_img))
        if not result["success"] and "not yet integrated" in result.get("error", ""):
            passed += 1
            print(f"  ✓ describe_image: placeholder error message")
        else:
            failed += 1
            print(f"  ✗ describe_image: {result}")
        tmp_img.unlink()

        # Test 4: encode_image_base64
        tmp = Path(tempfile.gettempdir()) / "vision_b64_test.txt"
        tmp.write_bytes(b"hello")
        b64 = encode_image_base64(str(tmp))
        if b64 and len(b64) > 0:
            passed += 1
            print(f"  ✓ encode_image_base64: {b64[:20]}...")
        else:
            failed += 1
            print(f"  ✗ encode_image_base64: {b64}")
        tmp.unlink()

        # Test 5: list_local_vision_models (may fail if Ollama not running)
        models = list_local_vision_models()
        if isinstance(models, list):
            passed += 1
            print(f"  ~ list_local_vision_models: {len(models)} found (Ollama may not be running)")
        else:
            failed += 1
            print(f"  ✗ list_local_vision_models: wrong type")

        # Test 6: VisionInput validation
        try:
            VisionInput()  # no image
            failed += 1
            print(f"  ✗ VisionInput validation: should raise")
        except ValueError:
            passed += 1
            print(f"  ✓ VisionInput validation: raises on missing image")

        vi = VisionInput(image_path="/tmp/x.png")
        if vi.prompt and vi.max_tokens:
            passed += 1
            print(f"  ✓ VisionInput construction: prompt='{vi.prompt[:30]}...'")

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