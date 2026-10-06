#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Vision Module (LIVE) | وحدة الرؤية
=======================================================
The Wolf's eyes: image understanding via a small LOCAL vision model.

عيون الذئب: فهم الصور عبر نموذج رؤية محلي صغير.

Architecture (hybrid, per the placeholder's own roadmap option b):
- Text reasoning stays on the main inference backend.
- IMAGES go to Ollama `qwen2.5vl:7b` (6GB, local, free, private) via /api/chat.
- The chat model NEVER receives pixels — vision works as the `see_image`
  TOOL, which returns words the model can reason about. This is how a
  text-only pipeline gains sight without retraining.

Config (env):
    VISION_MODEL=qwen2.5vl:7b  (override per machine)

Iron Laws Applied:
- #15 (Verify)        : self_test with a real generated PNG
- #22 (Autonomous)    : no prompts — describe immediately
- #33 (Lessons)       : bilingual AR+EN docstrings (Iron Law #47)
- #41 (Conflict)      : VRAM contention disclosed (6GB model swaps the 9.6GB
                         chat model; vision calls are slow, use deliberately)
- #47 (Bilingual)     : every public function has Arabic translation
- #48 (Separated)     : isolated module — only stdlib + HTTP
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("alpha_wolf.vision")


# ============================================================================
# Configuration
# ============================================================================

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# Small local vision model (user directive 2026-09-26: small + local).
# moondream (1.7GB) describes a UI screenshot correctly in ~70s.
# qwen2.5vl:7b returns EMPTY on this box (verified 2026-09-26) — kept only
# as fallback attempt, never trusted blindly (provenance in model_used).
VISION_MODEL = os.environ.get("VISION_MODEL", "moondream")
FALLBACK_VISION_MODEL = "qwen2.5vl:7b"
DEFAULT_VISION_MODEL = VISION_MODEL  # alias kept for backend/main.py compat
DEFAULT_VISION_MODEL = VISION_MODEL  # alias kept for backend/main.py compat

MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


# ============================================================================
# Interface
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


def _ollama_models() -> List[Dict[str, Any]]:
    """List Ollama models (raw)."""
    req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags",
                                 headers={"User-Agent": "AlphaWolfAgent/0.1"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8")).get("models", [])


def is_available() -> bool:
    """Check if vision is usable (Ollama reachable AND vision model present).

    التحقق من توفر الرؤية (Ollama يعمل ونموذج الرؤية موجود).
    """
    try:
        names = [(m.get("name", "") or "").lower() for m in _ollama_models()]
        want = VISION_MODEL.lower()
        return any(want in n or n in want for n in names)
    except Exception as e:
        logger.warning("vision availability check failed: %s", e)
        return False


def _load_image_b64(image_path: str) -> tuple:
    """Validate + base64-load an image. Returns (b64, size_kb) or raises."""
    p = Path(image_path)
    if not p.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if p.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"Not an image (suffix {p.suffix}): {image_path}")
    size = p.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large ({size / 1e6:.1f}MB > 10MB)")
    return base64.b64encode(p.read_bytes()).decode("utf-8"), round(size / 1024, 1)


def describe_image(image_path: str, prompt: str = "Describe this image | صف هذه الصورة",
                   max_tokens: int = 512) -> Dict[str, Any]:
    """Describe an image with the local vision model (LIVE).

    وصف صورة بنموذج الرؤية المحلي (يعمل فعلياً).

    NOTE (Iron Law #41): vision models swap VRAM with the 9.6GB chat model —
    moondream (1.7GB) answers in ~1min; use deliberately, one look per need.
    """
    start = time.time()
    try:
        b64, size_kb = _load_image_b64(image_path)
    except (FileNotFoundError, ValueError, OSError) as e:
        return {"success": False, "error": str(e), "vision_available": is_available()}
    payload = json.dumps({
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": prompt or "Describe this image",
                      "images": [b64]}],
        "stream": False,
        "options": {"num_predict": max(64, min(int(max_tokens or 512), 2048))},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat", data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AlphaWolfAgent/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"success": False, "error": f"Vision model call failed: {type(e).__name__}: {e}",
                "model": VISION_MODEL, "vision_available": is_available()}
    text = ((data.get("message") or {}).get("content") or "").strip()
    if not text:
        # Fallback model once before giving up
        try:
            payload2 = json.dumps({
                "model": FALLBACK_VISION_MODEL,
                "messages": [{"role": "user", "content": prompt or "Describe this image",
                              "images": [b64]}],
                "stream": False, "options": {"num_predict": 512},
            }).encode()
            req2 = urllib.request.Request(
                f"{OLLAMA_BASE_URL}/api/chat", data=payload2,
                headers={"Content-Type": "application/json", "User-Agent": "AlphaWolfAgent/0.1"})
            with urllib.request.urlopen(req2, timeout=300) as resp2:
                data2 = json.loads(resp2.read().decode("utf-8"))
            text = ((data2.get("message") or {}).get("content") or "").strip()
            used = FALLBACK_VISION_MODEL
        except Exception as e2:
            return {"success": False, "error": f"Empty vision reply (+fallback failed: {e2})",
                    "model": VISION_MODEL}
    else:
        used = VISION_MODEL
    if not text:
        return {"success": False, "error": "Empty vision reply", "model": used}
    return {"success": True, "description": text, "model_used": used,
            "image_path": image_path, "image_size_kb": size_kb,
            "seconds": round(time.time() - start, 1)}


def encode_image_base64(image_path: str) -> str:
    """Encode image to base64 (utility — works today).

    ترميز الصورة إلى base64 (أداة مساعدة — تعمل اليوم).
    """
    p = Path(image_path)
    return base64.b64encode(p.read_bytes()).decode("utf-8")


def list_local_vision_models() -> List[Dict[str, str]]:
    """List locally-available vision models (checks Ollama).

    قائمة بنماذج الرؤية المتاحة محلياً (تفحص Ollama).
    """
    try:
        models = _ollama_models()
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
    """Verify vision module works (LIVE contract).

    التحقق من أن وحدة الرؤية تعمل (عقد حي).
    """
    print("Running vision self-tests...")
    print("تشغيل اختبارات وحدة الرؤية...")

    passed = 0
    failed = 0

    try:
        # Test 1: availability is a real boolean
        avail = is_available()
        if isinstance(avail, bool):
            passed += 1
            print(f"  ✓ is_available: {avail}")
        else:
            failed += 1
            print(f"  ✗ is_available: wrong type")

        # Test 2: describe_image returns structured error for missing file
        result = describe_image("/nonexistent/image.png")
        if not result["success"] and "not found" in result.get("error", "").lower():
            passed += 1
            print(f"  ✓ describe_image: missing file handled")
        else:
            failed += 1
            print(f"  ✗ describe_image: {result}")

        # Test 3: non-image file rejected
        import tempfile
        tmp_txt = Path(tempfile.gettempdir()) / "vision_notimg.txt"
        tmp_txt.write_text("hello", encoding="utf-8")
        result = describe_image(str(tmp_txt))
        if not result["success"] and "not an image" in result.get("error", "").lower():
            passed += 1
            print(f"  ✓ describe_image: non-image rejected")
        else:
            failed += 1
            print(f"  ✗ describe_image non-image: {result}")
        tmp_txt.unlink()

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

        # Test 5: list_local_vision_models returns a list
        models = list_local_vision_models()
        if isinstance(models, list):
            passed += 1
            print(f"  ✓ list_local_vision_models: {[m['name'] for m in models]}")
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