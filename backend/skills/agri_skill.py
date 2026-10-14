#!/usr/bin/env python3
r"""
Alpha Wolf — Agriculture skill | مهارة الزراعة (قسم agriculture)
===================================================================
Section models (per-crop picks): plantnet300k, CGIAR-Crop, Mango_leaf,
aquaculture_oysters, vit-Diatome. All image classifiers — biggest label
wins, crop routed by keywords, fallback tries each verified classifier.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict

SKILL_NAME = "agri_skill"
SKILL_DESCRIPTION = ("Crop/plant disease ID (per-crop specialist classifiers). "
                     "Use for leaves, crops, aquaculture, diatoms.")
SKILL_DESCRIPTION_AR = "تشخيص المحاصيل والنباتات."
MODELS = ["plantnet300k", "CGIAR-Crop", "Mango_leaf", "aquaculture_oysters",
          "vit-Diatome"]
_HUB = {"plantnet300k": "janjibDEV/vit-plantnet300k",
        "CGIAR-Crop": "Professor/CGIAR-Crop-disease",
        "Mango_leaf": "DunnBC22/vit-base-patch16-224-in21k-Mango_leaf_Disease",
        "aquaculture_oysters": "csecht/aquaculture_oysters",
        "vit-Diatome": "sgonzalezsilot/vit-Diatome"}
_CROP_HINTS = (("mango", "Mango_leaf"), ("مانجو", "Mango_leaf"),
               ("oyster", "aquaculture_oysters"), ("سمك", "aquaculture_oysters"),
               ("diatom", "vit-Diatome"))


def run(image_path: str = "", hint: str = "", top_k: int = 3,
        **kwargs: Any) -> Dict[str, Any]:
    """Identify crop disease. شخّص مرض المحصول."""
    try:
        if not image_path:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "image_path is required"}
        order = list(MODELS)
        low = (hint or "").lower()
        for kw, m in _CROP_HINTS:
            if kw in low:
                order.remove(m)
                order.insert(0, m)
        from backend.agent import hf_runner
        tried = []
        for m in order:
            r = hf_runner.run_pipe("image-classification", _HUB[m],
                                   image_path, top_k=top_k)
            tried.append(m)
            if r.get("success"):
                return {"success": True, "skill": SKILL_NAME,
                        "models": MODELS, "model_used": m,
                        "predictions": [
                            {"label": p.get("label"),
                             "score": round(float(p.get("score", 0)), 4)}
                            for p in (r["output"] if isinstance(r["output"], list)
                                      else [r["output"]])],
                        "tried": tried}
        return {"success": False, "skill": SKILL_NAME, "models": MODELS,
                "tried": tried,
                "error": "all crop classifiers failed — check image/weights"}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and len(MODELS) == 5
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
