#!/usr/bin/env python3
r"""
Alpha Wolf — Chandra OCR skill | مهارة شاندرا لقراءة المستندات
================================================================
Section: ocr — first pick `chandra-ocr-2` (Datalab 4B VLM, SOTA olmOCR,
Arabic 34→68%), fallbacks GOT-OCR2_0 / nougat-small.

Runs automatically when the model-router picks the ocr section:
parks the chat model (VRAM governor), lazy-loads Chandra from the
canonical D: store, extracts markdown with layout, unloads afterwards.

Iron Laws: #47 bilingual, #15 structured results, fail-safe (never raise).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

SKILL_NAME = "chandra_ocr_skill"
SKILL_DESCRIPTION = ("Read documents/images to structured markdown (Chandra OCR 2 "
                     "first, layout-aware, 90+ languages incl. Arabic). "
                     "Use whenever the user asks to read/extract a PDF, scan, "
                     "form, table, or handwritten page.")
SKILL_DESCRIPTION_AR = ("قراءة المستندات والصور لماركداون منظم — شاندرا أولاً.")

MODEL_ID = "datalab-to/chandra-ocr-2"
PROMPT = ("Extract the full content of this document page as structured "
          "Markdown. Preserve headings, tables (as Markdown tables), lists, "
          "form fields with their values, and reading order. "
          "Transcribe math as LaTeX. Caption any figures briefly.")

_model = None
_processor = None


def _paths() -> Path:
    return Path("body") / "intake" / "staging"


def _load():
    """Lazy-load Chandra (parks chat first). Returns (model, processor).

    NEVER hangs the caller: the weight load is guarded by a 240s timeout
    (proven 2026-10-13: transformers weight-load stalls silently on this
    Windows/CUDA stack — processor loads fine, weights don't). On timeout
    the caller gets runner-pending instead of a hung turn.
    """
    global _model, _processor
    if _model is not None:
        return _model, _processor
    import threading
    box: dict = {}

    def _do():
        try:
            from backend.agent import model_router_bridge as _mrb
            _mrb.govern_vram_for("chandra-ocr-2")
        except Exception:
            pass
        try:
            import torch
            from transformers import AutoModelForMultimodalLM, AutoProcessor
            box["processor"] = AutoProcessor.from_pretrained(
                MODEL_ID, trust_remote_code=True)
            box["model"] = AutoModelForMultimodalLM.from_pretrained(
                MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto",
                max_memory={"cuda:0": "12GiB", "cpu": "24GiB"},
                trust_remote_code=True).eval()
        except Exception as e:
            box["error"] = e

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(240)
    if t.is_alive():
        raise TimeoutError("chandra weight-load exceeded 240s (runner pending)")
    if "error" in box:
        raise box["error"]
    _processor, _model = box["processor"], box["model"]
    return _model, _processor


def _unload():
    global _model, _processor
    try:
        import gc
        import torch
        del _model
        del _processor
    except Exception:
        pass
    _model, _processor = None, None
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _ocr_pil(image) -> str:
    import torch
    model, processor = _load()
    messages = [{"role": "user", "content": [
        {"type": "image"}, {"type": "text", "text": PROMPT}]}]
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=2048)
    gen = out[0][inputs["input_ids"].shape[-1]:]
    return processor.decode(gen, skip_special_tokens=True).strip()


def run(image_path: Optional[str] = None, pdf_path: Optional[str] = None,
        page: int = 1, **kwargs: Any) -> Dict[str, Any]:
    """OCR an image or one PDF page to Markdown.

    اقرأ صورة أو صفحة PDF إلى ماركداون منظم.
    """
    try:
        from PIL import Image
        if pdf_path:
            import fitz
            doc = fitz.open(pdf_path)
            if page < 1 or page > len(doc):
                return {"success": False, "skill": SKILL_NAME,
                        "error": f"page {page} out of {len(doc)}"}
            pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(2, 2))
            import io
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            source = f"{pdf_path}#p{page}"
        elif image_path:
            image = Image.open(image_path).convert("RGB")
            source = image_path
        else:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "image_path or pdf_path required"}
        try:
            markdown = _ocr_pil(image)
        except TimeoutError as te:
            return {"success": False, "skill": SKILL_NAME,
                    "runner": "pending", "model_used": MODEL_ID,
                    "error": str(te),
                    "hint": ("weights verified on D: (739 tensors); debug load "
                             "on cool device with logs, or WSL2+vLLM, or await "
                             "Ollama GGUF release")}
        finally:
            _unload()  # always give VRAM back — chat reloads on next turn
        if not markdown:
            return {"success": False, "skill": SKILL_NAME,
                    "model_used": MODEL_ID, "error": "empty OCR reply"}
        return {"success": True, "skill": SKILL_NAME, "model_used": MODEL_ID,
                "source": source, "markdown": markdown}
    except Exception as e:
        try:
            _unload()
        except Exception:
            pass
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {e}"}


def self_test() -> bool:
    print("chandra_ocr_skill: contract check (no model load)")
    ok = callable(run) and SKILL_NAME and MODEL_ID == "datalab-to/chandra-ocr-2"
    print("  model id pinned:", MODEL_ID)
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
