#!/usr/bin/env python3
r"""
Alpha Wolf — shared HuggingFace specialist runner | العداء المشترك
====================================================================
One runner for ALL domain-specialist skills (protein/dna/chem/medical/
satellite/agri/marine/food/climate/audiofx/math/extract). Skills stay thin
playbooks (models + task map); heavy lifting lives HERE (no duplication).

- Resolves canonical D: snapshots (models--org--name layout).
- Lazy pipelines per (task, model); VRAM guard: >1GB weights park the
  chat model first (via model_router_bridge, best-effort).
- tasks: image-classification, audio-classification, image-segmentation,
  zero-shot-image-classification, automatic-speech-recognition,
  text-generation, feature-extraction.
- Every public function guarded: returns dicts, never raises into skills.

Iron Laws: #47 bilingual, #15 structured, fail-safe.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

STORE = Path("D:/Intelligence models/huggingface")

_pipes: Dict[str, Any] = {}


def resolve_snapshot(hub_id: str) -> Path:
    """Local snapshot dir for a hub id (models--org--name). Raises FileNotFound."""
    slug = "models--" + hub_id.replace("/", "--")
    snaps = sorted(glob.glob(str(STORE / slug / "snapshots" / "*")))
    if not snaps:
        raise FileNotFoundError(f"not on D:: {hub_id}")
    return Path(snaps[0])


def weights_gb(hub_id: str) -> float:
    """Sum of safetensors/bin blobs (fast, no load)."""
    try:
        total = 0
        for pat in ("*.safetensors", "pytorch_model*.bin"):
            for f in resolve_snapshot(hub_id).glob(pat):
                total += f.stat().st_size
        return round(total / (1024 ** 3), 2)
    except Exception:
        return 0.0


def _device() -> Any:
    try:
        import torch
        return 0 if torch.cuda.is_available() else -1
    except Exception:
        return -1


def run_pipe(task: str, hub_id: str, inputs: Any,
             park_chat: bool = True, **kw: Any) -> Dict[str, Any]:
    """Run a transformers pipeline on a D: model. Guarded, cached, unloaded-safe."""
    key = f"{task}::{hub_id}"
    try:
        if park_chat and weights_gb(hub_id) > 1.0:
            try:
                from backend.agent import model_router_bridge as _mrb
                _mrb.govern_vram_for(hub_id)
            except Exception:
                pass
        if key not in _pipes:
            from transformers import pipeline
            local = str(resolve_snapshot(hub_id))
            use_dev = _device()
            try:
                _pipes[key] = pipeline(task, model=local, tokenizer=local,
                                       device=use_dev, trust_remote_code=True)
            except Exception:
                # retry on CPU (OOM-safe) before giving up
                _pipes[key] = pipeline(task, model=local, tokenizer=local,
                                       device=-1, trust_remote_code=True)
        out = _pipes[key](inputs, **kw)
        return {"success": True, "task": task, "model": hub_id, "output": out}
    except Exception as e:
        _pipes.pop(key, None)
        return {"success": False, "task": task, "model": hub_id,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def embed_texts(hub_id: str, texts: List[str], matrix: bool = False) -> Dict[str, Any]:
    """Mean-pooled embeddings (CPU, no VRAM battle) for similarity skills.

    matrix=True returns per-token matrices (for MaxSim ranking — identical
    sequences then score ~1.0; mean-cosine alone can invert, proven live).
    """
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
        local = str(resolve_snapshot(hub_id))
        tok = AutoTokenizer.from_pretrained(local, trust_remote_code=True)
        mdl = AutoModel.from_pretrained(local, trust_remote_code=True).eval()
        vecs, mats = [], []
        with torch.no_grad():
            for t in texts:
                enc = tok(t, return_tensors="pt", truncation=True, max_length=512)
                h = mdl(**enc).last_hidden_state.squeeze(0)
                m = enc["attention_mask"].squeeze(0).bool()
                mats.append(h[m].tolist())
                w = m.unsqueeze(-1).expand(h.size()).float()
                vecs.append(((h * w).sum(0) / w.sum(0)).squeeze(0).tolist())
        del mdl
        out: Dict[str, Any] = {"success": True, "model": hub_id, "vectors": vecs}
        if matrix:
            out["matrices"] = mats
        return out
    except Exception as e:
        return {"success": False, "model": hub_id,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        # VRAM hygiene: specialist runs must not fragment CUDA for the
        # chat model that narrates right after (proven live 2026-10-14).
        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def maxsim(q: List[List[float]], d: List[List[float]]) -> float:
    """ColBERT-style MaxSim: mean over query tokens of max cosine match."""
    import math

    def _cos(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)

    if not q or not d:
        return 0.0
    return sum(max(_cos(qt, dt) for dt in d) for qt in q) / len(q)


def cosine(a: List[float], b: List[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def unload_all() -> Dict[str, Any]:
    """Drop cached pipelines + free CUDA. Returns counts."""
    n = len(_pipes)
    _pipes.clear()
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    return {"unloaded": n}
