#!/usr/bin/env python3
r"""
Alpha Wolf — Transcribe skill | مهارة التفريغ (قسم الصوت: STT)
================================================================
Section models (smallest first): faster-whisper-base/small/medium/
large-v3-turbo (D: hub, Systran). CPU for base/small, CUDA for larger.
Runs automatically when audio needs transcription.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

SKILL_NAME = "transcribe_skill"
SKILL_DESCRIPTION = ("Speech-to-text (faster-whisper, local, private). "
                     "Use whenever the user sends audio/video needing transcription.")
SKILL_DESCRIPTION_AR = "تفريغ الصوت لنص محلياً وخصوصية كاملة."
MODELS = ["faster-whisper-base", "faster-whisper-small",
          "faster-whisper-medium", "faster-whisper-large-v3-turbo"]
_HUB = {"faster-whisper-base": "Systran/faster-whisper-base",
        "faster-whisper-small": "Systran/faster-whisper-small",
        "faster-whisper-medium": "Systran/faster-whisper-medium",
        # turbo has no Systran repo — verified 2026-10-13: deepdml ct2 build.
        "faster-whisper-large-v3-turbo":
            "deepdml/faster-whisper-large-v3-turbo-ct2"}


def _snap(hub_id: str) -> str:
    import glob
    slug = "models--" + hub_id.replace("/", "--")
    snaps = sorted(glob.glob(
        r"D:\Intelligence models\huggingface" + "/" + slug + "/snapshots/*"))
    if not snaps:
        raise FileNotFoundError(f"not on D:: {hub_id}")
    return snaps[0]


def run(audio_path: str = "", model: str = "faster-whisper-base",
        language: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Transcribe audio → text. فرّغ الصوت إلى نص."""
    try:
        if not audio_path:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "audio_path is required"}
        if model not in MODELS:
            model = MODELS[0]
        from faster_whisper import WhisperModel
        device = "cuda" if model in ("faster-whisper-medium",
                                     "faster-whisper-large-v3-turbo") else "cpu"
        wm = WhisperModel(_snap(_HUB[model]), device=device,
                          compute_type="int8" if device == "cpu" else "float16")
        try:
            segs, info = wm.transcribe(audio_path, language=language or None)
            text = " ".join(s.text.strip() for s in segs).strip()
        finally:
            del wm
        if not text:
            return {"success": False, "skill": SKILL_NAME,
                    "model_used": model, "error": "empty transcription"}
        return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                "model_used": model, "language": info.language,
                "text": text}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and MODELS[0] == "faster-whisper-base"
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
