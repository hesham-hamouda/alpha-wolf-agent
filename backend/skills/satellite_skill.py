#!/usr/bin/env python3
r"""
Alpha Wolf — Satellite skill | مهارة الأقمار (قسم satellite)
===============================================================
Section models: clip-fine-tuned-satellite (zero-shot scene labels),
segformer-b0 (ade20k semantic segmentation). Task pick inside.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, List

SKILL_NAME = "satellite_skill"
SKILL_DESCRIPTION = ("Satellite imagery (CLIP zero-shot + SegFormer segmentation). "
                     "Use for overhead/remote-sensing scenes.")
SKILL_DESCRIPTION_AR = "صور الأقمار: تصنيف وتجزئة."
MODELS = ["clip-fine-tuned-satellite", "segformer-b0"]
_CLIP = "NemesisAlm/clip-fine-tuned-satellite"
_SEG = "nvidia/segformer-b0-finetuned-ade-512-512"
_LABELS = ["urban", "farmland", "forest", "water", "desert", "road", "building"]


def run(image_path: str = "", task: str = "classify",
        labels: List[str] | None = None, **kwargs: Any) -> Dict[str, Any]:
    """Classify or segment a satellite scene. حلل مشهداً فضائياً."""
    try:
        if not image_path:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "image_path is required"}
        from backend.agent import hf_runner
        if task == "segment":
            r = hf_runner.run_pipe("image-segmentation", _SEG, image_path)
            if not r.get("success"):
                return {"success": False, "skill": SKILL_NAME,
                        "models": MODELS, "error": r.get("error")}
            segs = r["output"] if isinstance(r["output"], list) else [r["output"]]
            return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                    "model_used": "segformer-b0",
                    "segments": [{"label": s.get("label"), "score": round(float(s.get("score", 0)), 4)}
                                 for s in segs][:12]}
        from transformers import CLIPProcessor, CLIPModel
        import torch
        from PIL import Image
        local = str(hf_runner.resolve_snapshot(_CLIP))
        proc = CLIPProcessor.from_pretrained(local)
        mdl = CLIPModel.from_pretrained(local).eval()
        with torch.no_grad():
            out = mdl(**proc(text=labels or _LABELS,
                             images=Image.open(image_path).convert("RGB"),
                             return_tensors="pt", padding=True))
            probs = out.logits_per_image.softmax(-1).squeeze(0).tolist()
        del mdl
        ranked = sorted(zip(labels or _LABELS, probs), key=lambda z: z[1],
                        reverse=True)
        return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                "model_used": "clip-fine-tuned-satellite",
                "ranking": [{"label": l, "score": round(float(s), 4)}
                            for l, s in ranked]}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and len(MODELS) == 2
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
