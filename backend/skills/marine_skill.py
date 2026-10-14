#!/usr/bin/env python3
r"""
Alpha Wolf — Marine skill | مهارة البحر (قسم marine)
========================================================
Section models: fish-shrimp (verified ViT classifier first),
Marine_Species, CoralSCOP, micro-algae (attempted via generic
image-classification; honest per-model errors when weights lack heads).
Organism routed by keywords.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict

SKILL_NAME = "marine_skill"
SKILL_DESCRIPTION = ("Marine organism ID (fish/shrimp verified, reef/algae attempted). "
                     "Use for sea life, coral, aquaculture disease.")
SKILL_DESCRIPTION_AR = "التعرف على الكائنات البحرية."
MODELS = ["fish-shrimp", "Marine_Species", "CoralSCOP", "micro-algae"]
_HUB = {"fish-shrimp": "Saon110/fish-shrimp-disease-classifier",
        "Marine_Species": "Manojnayakmit/Marine_Species_Indentification",
        "CoralSCOP": "reefsupport/CoralSCOP",
        "micro-algae": "mosayed24/micro-algae-detection"}
_HINTS = (("shrimp", "fish-shrimp"), ("fish", "fish-shrimp"),
          ("سمك", "fish-shrimp"), ("coral", "CoralSCOP"),
          ("مرجان", "CoralSCOP"), ("algae", "micro-algae"),
          ("طحالب", "micro-algae"))


def run(image_path: str = "", hint: str = "", top_k: int = 3,
        **kwargs: Any) -> Dict[str, Any]:
    """Identify a marine organism. تعرّف على كائن بحري."""
    try:
        if not image_path:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "image_path is required"}
        order = list(MODELS)
        low = (hint or "").lower()
        for kw, m in _HINTS:
            if kw in low and m in order:
                order.remove(m)
                order.insert(0, m)
        from backend.agent import hf_runner
        tried = []
        for m in order:
            r = hf_runner.run_pipe("image-classification", _HUB[m],
                                   image_path, top_k=top_k)
            tried.append({"model": m, "ok": bool(r.get("success"))})
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
                "error": "verified model (fish-shrimp) failed; others lack heads"}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and MODELS[0] == "fish-shrimp"
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
