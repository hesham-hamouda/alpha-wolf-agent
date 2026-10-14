#!/usr/bin/env python3
r"""
Alpha Wolf — Protein skill | مهارة البروتينات (قسم protein)
==============================================================
Section models (bigger first): esm2_t30_150M > esm2_t12_35M > prot_bert
(D: hub, facebook/Rostlab). NEVER a chat model for sequences.
Compare a query sequence against candidates by specialist embeddings.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, List

SKILL_NAME = "protein_skill"
SKILL_DESCRIPTION = ("Protein sequence analysis (ESM-2 specialists, biggest first). "
                     "Use for comparing/ranking amino-acid sequences.")
SKILL_DESCRIPTION_AR = "تحليل تسلسلات البروتين بمتخصصي ESM."
MODELS = ["esm2_t30_150M", "esm2_t12_35M", "prot_bert"]
_HUB = {"esm2_t30_150M": "facebook/esm2_t30_150M_UR50D",
        "esm2_t12_35M": "facebook/esm2_t12_35M_UR50D",
        "prot_bert": "Rostlab/prot_bert"}


def run(query: str = "", candidates: List[str] | None = None,
        model: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Rank candidate sequences by similarity to query. رتّب التسلسلات."""
    try:
        if not (query or "").strip() or not candidates:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "query and candidates are required"}
        if model not in MODELS:
            model = MODELS[0]
        from backend.agent import hf_runner
        # ESM-2 reads RAW sequences (no space-join — spaces distort scoring,
        # proven 2026-10-13 live turn: identical seq ranked below poly-G).
        seqs = [query.strip()] + [c.strip() for c in candidates]
        e = hf_runner.embed_texts(_HUB[model], seqs, matrix=True)
        if not e.get("success"):
            return {"success": False, "skill": SKILL_NAME,
                    "models": MODELS, "error": e.get("error")}
        mats = e.get("matrices") or []
        if mats:
            ranked = sorted(
                ({"candidate": c,
                  "score": round(hf_runner.maxsim(mats[0], m), 4)}
                 for c, m in zip(candidates, mats[1:])),
                key=lambda d: d["score"], reverse=True)
        else:
            ranked = sorted(
                ({"candidate": c,
                  "score": round(hf_runner.cosine(e["vectors"][0], v), 4)}
                 for c, v in zip(candidates, e["vectors"][1:])),
                key=lambda d: d["score"], reverse=True)
        return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                "model_used": model, "ranking": ranked}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and MODELS[0] == "esm2_t30_150M"
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
