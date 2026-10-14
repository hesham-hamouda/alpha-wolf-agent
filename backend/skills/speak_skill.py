#!/usr/bin/env python3
r"""
Alpha Wolf — Speak skill | مهارة النطق (قسم الصوت: TTS)
=========================================================
Section models: supertonic3 (D:/tts, ONNX, CPU — no VRAM battle).
Runs automatically when the image-gen... (no —) when the TTS section is
invoked: text → speech WAV with a named voice style.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

SKILL_NAME = "speak_skill"
SKILL_DESCRIPTION = ("Text-to-speech (Supertonic-3, CPU, Arabic+English voices). "
                     "Use whenever the user asks to speak, narrate, or voice any text.")
SKILL_DESCRIPTION_AR = "تحويل النص لكلام مسموع بأصوات عربية وإنجليزية."
MODELS = ["supertonic3"]
MODEL_DIR = r"D:\Intelligence models\tts\supertonic3"
OUT_DIR = Path("data") / "generated_audio"

_tts = None


def _load():
    global _tts
    if _tts is None:
        from supertonic import TTS
        _tts = TTS(model="supertonic-3", model_dir=MODEL_DIR, auto_download=False)
    return _tts


def run(text: str = "", voice: str = "F1", lang: str = "ar",
        filename: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Speak text to a WAV file. انطق النص إلى ملف صوتي."""
    try:
        if not (text or "").strip():
            return {"success": False, "skill": SKILL_NAME,
                    "error": "text is required | النص مطلوب"}
        tts = _load()
        try:
            style = tts.get_voice_style(voice)
        except Exception:
            style = tts.get_voice_style("F1")
            voice = "F1"
        wav, _ = tts.synthesize(text, voice_style=style, lang=lang or "ar")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        import time
        out = OUT_DIR / (filename or f"wolf_tts_{int(time.time())}_{voice}.wav")
        tts.save_audio(wav, str(out))
        return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                "model_used": "supertonic3", "voice": voice, "lang": lang,
                "wav_path": str(out)}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and MODELS == ["supertonic3"]
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
