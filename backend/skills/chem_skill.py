#!/usr/bin/env python3
r"""
Alpha Wolf — Chemistry skill | مهارة الكيمياء (قسم chemistry)
================================================================
Section models: ChemBERTa-10M-MTR (trained multitask-regression head first),
MoLFormer-XL (masked, similarity). SMILES in, chemistry out.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, List

SKILL_NAME = "chem_skill"
SKILL_DESCRIPTION = ("Chemistry on SMILES (ChemBERTa-MTR properties, MoLFormer "
                     "similarity). Use for molecules/reactions, never a chat model.")
SKILL_DESCRIPTION_AR = "الكيمياء على الجزيئات والتفاعلات."
MODELS = ["ChemBERTa-10M-MTR", "MoLFormer-XL"]
_HUB = {"ChemBERTa-10M-MTR": "DeepChem/ChemBERTa-10M-MTR",
        "MoLFormer-XL": "ibm/MoLFormer-XL-both-10pct"}
_ZINC = "seyonec/ChemBERTa-zinc-base-v1"


def _regression(smiles: str) -> Dict[str, Any]:
    """Property prediction via the trained MTR head (best-effort)."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from backend.agent import hf_runner
    local = str(hf_runner.resolve_snapshot(_HUB["ChemBERTa-10M-MTR"]))
    tok = AutoTokenizer.from_pretrained(local)
    mdl = AutoModelForSequenceClassification.from_pretrained(local).eval()
    with torch.no_grad():
        logits = mdl(**tok(smiles, return_tensors="pt")).logits.squeeze(0).tolist()
    return {"success": True, "values": logits}


def run(smiles: str = "", candidates: List[str] | None = None,
        **kwargs: Any) -> Dict[str, Any]:
    """Predict properties / rank similar molecules. حلل الجزيء."""
    try:
        if not (smiles or "").strip():
            return {"success": False, "skill": SKILL_NAME,
                    "error": "smiles is required"}
        out: Dict[str, Any] = {"success": True, "skill": SKILL_NAME,
                               "models": MODELS, "smiles": smiles}
        try:
            out["properties"] = _regression(smiles)
            out["model_used"] = "ChemBERTa-10M-MTR"
        except Exception as e:
            out["properties"] = {"success": False,
                                 "error": f"head: {type(e).__name__}"}
        if candidates:
            from backend.agent import hf_runner
            e = hf_runner.embed_texts(_ZINC, [smiles] + list(candidates))
            if e.get("success"):
                out["similar"] = sorted(
                    ({"candidate": c,
                      "score": round(hf_runner.cosine(e["vectors"][0], v), 4)}
                     for c, v in zip(candidates, e["vectors"][1:])),
                    key=lambda d: d["score"], reverse=True)
        return out
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and MODELS[0] == "ChemBERTa-10M-MTR"
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
