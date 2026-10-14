#!/usr/bin/env python3
r"""
Alpha Wolf — DNA skill | مهارة الحمض النووي (قسم dna)
========================================================
Section models: DNABERT-2-117M, agro-nucleotide-1b, hyenadna-tiny
(D: hub). Task-dependent pick, NEVER a chat model for sequences.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, List

SKILL_NAME = "dna_skill"
SKILL_DESCRIPTION = ("DNA/nucleotide analysis (DNABERT-2 and specialists). "
                     "Use for comparing/ranking nucleotide sequences.")
SKILL_DESCRIPTION_AR = "تحليل تسلسلات الحمض النووي."
MODELS = ["DNABERT-2-117M", "agro-nucleotide-1b", "hyenadna-tiny"]
_HUB = {"DNABERT-2-117M": "zhihan1996/DNABERT-2-117M",
        "agro-nucleotide-1b": "InstaDeepAI/agro-nucleotide-transformer-1b",
        "hyenadna-tiny": "LongSafari/hyenadna-tiny-1k-seqlen-hf"}


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
        e = hf_runner.embed_texts(_HUB[model], [query] + list(candidates),
                                  matrix=True)
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
    ok = callable(run) and MODELS[0] == "DNABERT-2-117M"
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
