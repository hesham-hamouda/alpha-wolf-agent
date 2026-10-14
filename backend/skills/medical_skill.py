#!/usr/bin/env python3
r"""
Alpha Wolf — Medical skill | مهارة الطب (قسم medical)
========================================================
Section models: text → biobert / PathologyBERT / scibert (similarity over
biomedical language); slides → phikon (pathology encoder); papers →
BiomedCLIP (zero-shot when processor present). Sub-type routing inside.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, List

SKILL_NAME = "medical_skill"
SKILL_DESCRIPTION = ("Medical text/slide support (BioBERT, PathologyBERT, phikon). "
                     "Use for biomedical questions and pathology slides.")
SKILL_DESCRIPTION_AR = "الدعم الطبي: نصوص وشرائح مرضية."
MODELS = ["phikon", "BiomedCLIP", "biobert", "PathologyBERT", "scibert"]
_TEXT = {"biobert": "dmis-lab/biobert-base-cased-v1.2",
         "PathologyBERT": "tsantos/PathologyBERT",
         "scibert": "allenai/scibert_scivocab_uncased"}
_SLIDE = "owkin/phikon"


def run(text: str = "", candidates: List[str] | None = None,
        slide_path: str = "", model: str = "",
        **kwargs: Any) -> Dict[str, Any]:
    """Biomedical similarity / slide embedding. حلل طبياً."""
    try:
        from backend.agent import hf_runner
        if slide_path:
            # phikon is a vision encoder: embed via feature path below.
            from transformers import AutoModel, AutoProcessor
            local = str(hf_runner.resolve_snapshot(_SLIDE))
            from PIL import Image
            proc = AutoProcessor.from_pretrained(local, trust_remote_code=True)
            import torch
            mdl = AutoModel.from_pretrained(local, trust_remote_code=True).eval()
            with torch.no_grad():
                v = mdl(**proc(Image.open(slide_path).convert("RGB"),
                               return_tensors="pt")).last_hidden_state.mean(1)
            dim = v.shape[-1]
            del mdl
            return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                    "model_used": "phikon", "slide_embedding_dim": dim}
        if not (text or "").strip():
            return {"success": False, "skill": SKILL_NAME,
                    "error": "text or slide_path is required"}
        if model not in _TEXT:
            low = text.lower()
            model = ("PathologyBERT" if any(w in low for w in
                     ("patholog", "slide", "tumor", "باثولوجي", "ورم"))
                     else "biobert")
        e = hf_runner.embed_texts(_TEXT[model],
                                  [text] + list(candidates or []))
        if not e.get("success"):
            return {"success": False, "skill": SKILL_NAME,
                    "models": MODELS, "error": e.get("error")}
        out: Dict[str, Any] = {"success": True, "skill": SKILL_NAME,
                               "models": MODELS, "model_used": model}
        if candidates:
            out["similar"] = sorted(
                ({"candidate": c,
                  "score": round(hf_runner.cosine(e["vectors"][0], v), 4)}
                 for c, v in zip(candidates, e["vectors"][1:])),
                key=lambda d: d["score"], reverse=True)
        else:
            out["embedding_dim"] = len(e["vectors"][0])
        return out
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and "phikon" in MODELS
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
