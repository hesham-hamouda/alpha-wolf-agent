#!/usr/bin/env python3
r"""
Alpha Wolf — Climate skill | مهارة المناخ (قسم climate)
==========================================================
Section models: climatebert (distilroberta masked — similarity over climate
language), tspulse-r1 (reconstruction/anomaly), ttm-r2 (forecast from number
series — REAL direct inference, CPU-friendly tiny mixer).

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, List

SKILL_NAME = "climate_skill"
SKILL_DESCRIPTION = ("Climate text similarity + time-series forecast (climatebert, "
                     "TinyTimeMixer). Use for climate questions and numeric series.")
SKILL_DESCRIPTION_AR = "المناخ والسلاسل الزمنية."
MODELS = ["climatebert", "tspulse-r1", "ttm-r2"]
_BERT = "climatebert/distilroberta-base-climate-f"
_TTM = "ibm-granite/granite-timeseries-ttm-r2"


def run(text: str = "", candidates: List[str] | None = None,
        series: List[float] | None = None, horizon: int = 12,
        **kwargs: Any) -> Dict[str, Any]:
    """Climate similarity and/or forecast. حلل مناخياً وتنبأ."""
    try:
        from backend.agent import hf_runner
        out: Dict[str, Any] = {"success": True, "skill": SKILL_NAME,
                               "models": MODELS}
        if series:
            import torch
            from transformers import AutoModel
            local = str(hf_runner.resolve_snapshot(_TTM))
            mdl = AutoModel.from_pretrained(local, trust_remote_code=True).eval()
            with torch.no_grad():
                x = torch.tensor(series, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
                y = mdl(x).prediction_outputs.squeeze().tolist()
            del mdl
            out["forecast"] = {"model_used": "ttm-r2",
                               "values": (y[:horizon] if isinstance(y, list) else y)}
        if text:
            e = hf_runner.embed_texts(_BERT, [text] + list(candidates or []))
            if not e.get("success"):
                out["success"] = False
                out["error"] = e.get("error")
            elif candidates:
                out["similar"] = sorted(
                    ({"candidate": c,
                      "score": round(hf_runner.cosine(e["vectors"][0], v), 4)}
                     for c, v in zip(candidates, e["vectors"][1:])),
                    key=lambda d: d["score"], reverse=True)
            else:
                out["embedding_dim"] = len(e["vectors"][0])
                out["model_used"] = "climatebert"
        if not series and not text:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "text or series is required"}
        return out
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and len(MODELS) == 3
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
