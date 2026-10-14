#!/usr/bin/env python3
r"""
Alpha Wolf — Food skill | مهارة الغذاء (قسم food)
====================================================
Section models: food-nateraw (ViT classifier, D: hub).

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict

SKILL_NAME = "food_skill"
SKILL_DESCRIPTION = ("Food image classification (nateraw food ViT). "
                     "Use for dishes, meals, food photos.")
SKILL_DESCRIPTION_AR = "تصنيف صور الطعام."
MODELS = ["food-nateraw"]
HUB = "nateraw/food"


def run(image_path: str = "", top_k: int = 3,
        **kwargs: Any) -> Dict[str, Any]:
    """Classify a food photo. صنّف صورة طعام."""
    try:
        if not image_path:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "image_path is required"}
        from backend.agent import hf_runner
        r = hf_runner.run_pipe("image-classification", HUB, image_path,
                               top_k=top_k)
        if not r.get("success"):
            return {"success": False, "skill": SKILL_NAME,
                    "models": MODELS, "error": r.get("error")}
        out = r["output"] if isinstance(r["output"], list) else [r["output"]]
        return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                "model_used": "food-nateraw",
                "predictions": [{"label": p.get("label"),
                                 "score": round(float(p.get("score", 0)), 4)}
                                for p in out]}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and MODELS == ["food-nateraw"]
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
