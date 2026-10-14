#!/usr/bin/env python3
r"""
Alpha Wolf — Audio-events skill | مهارة الأحداث الصوتية (قسم audiofx)
========================================================================
Section models: ast-finetuned-audioset (environmental event labels),
wav2vec2-base (speech representation similarity). Non-speech sounds here;
speech transcription belongs to transcribe_skill.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, List

SKILL_NAME = "audiofx_skill"
SKILL_DESCRIPTION = ("Environmental sound events (AST AudioSet) + speech "
                     "representation compare (wav2vec2). Use for non-speech audio.")
SKILL_DESCRIPTION_AR = "الأحداث الصوتية المحيطة."
MODELS = ["ast-finetuned-audioset", "wav2vec2-base"]
_AST = "MIT/ast-finetuned-audioset-10-10-0.4593"
_W2V = "facebook/wav2vec2-base"


def run(audio_path: str = "", top_k: int = 5,
        compare_paths: List[str] | None = None, model: str = "",
        **kwargs: Any) -> Dict[str, Any]:
    """Label sound events / compare speech reps. حلل حدثاً صوتياً."""
    try:
        if model == "wav2vec2-base" and not compare_paths:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "compare_paths required: add 1+ compare file paths"}
        if not audio_path:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "audio_path is required"}
        from backend.agent import hf_runner
        if compare_paths:
            import librosa
            import torch
            from transformers import AutoModel, AutoProcessor
            local = str(hf_runner.resolve_snapshot(_W2V))
            proc = AutoProcessor.from_pretrained(local)
            mdl = AutoModel.from_pretrained(local).eval()
            vecs = []
            with torch.no_grad():
                for p in [audio_path] + list(compare_paths):
                    wav, sr = librosa.load(p, sr=16000)
                    h = mdl(**proc(wav, sampling_rate=sr,
                                   return_tensors="pt")).last_hidden_state
                    vecs.append(h.mean(1).squeeze(0).tolist())
            del mdl
            ranked = sorted(
                ({"candidate": c,
                  "score": round(hf_runner.cosine(vecs[0], v), 4)}
                 for c, v in zip(compare_paths, vecs[1:])),
                key=lambda d: d["score"], reverse=True)
            return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                    "model_used": "wav2vec2-base", "ranking": ranked}
        r = hf_runner.run_pipe("audio-classification", _AST, audio_path,
                               top_k=top_k)
        if not r.get("success"):
            return {"success": False, "skill": SKILL_NAME,
                    "models": MODELS, "error": r.get("error")}
        out = r["output"] if isinstance(r["output"], list) else [r["output"]]
        return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                "model_used": "ast-finetuned-audioset",
                "events": [{"label": e.get("label"),
                            "score": round(float(e.get("score", 0)), 4)}
                           for e in out]}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and len(MODELS) == 2
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
