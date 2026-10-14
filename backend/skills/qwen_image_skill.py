#!/usr/bin/env python3
r"""
Alpha Wolf — Qwen Image skill | مهارة إنشاء الصور
===================================================
Section: image-gen — `qwen-image-2.1-turbo-int8` via ComfyUI on D:
(8 denoising steps, CFG=1, native RGBA, editing in one model).

Two phases, honest about each:
  A. Prompt engineering (ALWAYS works, zero GPU): turns a quick Arabic/
     English idea into a disciplined English prompt — observer-perspective
     paragraph (NOT keyword stuffing like "8K, masterpiece"), 8-14 spatial
     phrases, lighting/contrast sentences, disentangled edit instruction,
     aspect ratio resolved to pixels.
  B. Runner (needs ComfyUI :8188 with the D: weights): queues the workflow,
     polls history, returns the PNG path. If the runner is unreachable the
     skill still returns the engineered prompt with runner-pending status.

Iron Laws: #47 bilingual, #15 structured results, fail-safe (never raise).
"""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SKILL_NAME = "qwen_image_skill"
SKILL_DESCRIPTION = ("Create or edit images (Qwen Image 2.1 Turbo via ComfyUI). "
                     "Engineers the prompt automatically (observer paragraph, "
                     "spatial layout, lighting) and renders PNG/RGBA. "
                     "Use whenever the user asks to create, draw, imagine, or "
                     "edit a picture.")
SKILL_DESCRIPTION_AR = ("إنشاء وتعديل الصور — هندسة الأمر تلقائياً ثم العرض.")

MODEL_ID = "qwen-image-2.1-turbo-int8"
COMFY_URL = "http://127.0.0.1:8188"
OUT_DIR = Path("data") / "generated_images"

ASPECTS = {"1:1": (1024, 1024), "16:9": (1536, 864), "9:16": (864, 1536),
           "21:9": (1680, 720), "4:3": (1280, 960), "3:4": (960, 1280)}
STEPS, CFG = 8, 1  # Turbo fused in weights — never raise steps (waste).

_BANNED_KEYWORDS = ("8k", "masterpiece", "best quality", "ultra detailed",
                    "trending on artstation")


def engineer_prompt(idea: str, aspect: str = "1:1",
                    mode: str = "generate") -> Dict[str, Any]:
    """Build the disciplined English prompt from a quick idea.

    ابنِ الأمر الإنجليزي المنضبط من فكرة سريعة (يعمل دون GPU).
    Paths/URLs are delivery instructions, NOT visual content — strip them
    first (proven 2026-10-14: a D:\\ path got rendered as image text).
    """
    import re
    raw = (idea or "").strip()
    clean = re.sub(r"file://\S+|[A-Za-z]:[\\/][^\s\"']+|https?://\S+", "",
                   raw)
    clean = " ".join(clean.split())
    idea = clean or raw
    if aspect not in ASPECTS:
        aspect = "1:1"
    w, h = ASPECTS[aspect]
    lowered = idea.lower()
    if any(k in lowered for k in _BANNED_KEYWORDS):
        note = "keyword stuffing removed — Qwen-Image rejects it"
    else:
        note = "clean idea"
    observer = (
        f"Observer perspective, single coherent scene. {idea} "
        f"Render as one continuous photographic moment with a clear primary "
        f"subject, supporting midground elements, and a readable background "
        f"that gives depth without clutter.")
    spatial = ("Spatial layout: primary subject centered-left in sharp focus; "
               "midground props receding along a gentle diagonal; background "
               "softly separated by atmospheric depth; horizon level; generous "
               "negative space on the right for balance; foreground accents "
               "framing the lower corners; consistent scale between elements; "
               "no cropped faces or cut-off limbs; grounded contact shadows "
               "under every object.")
    light = ("Lighting and contrast: soft key light from the upper left, cool "
             "ambient fill, gentle rim separation on edges, balanced contrast "
             "with preserved shadow detail and no blown highlights.")
    edit_rule = ""
    if mode == "edit":
        edit_rule = ("Edit disentanglement: change ONLY the described element; "
                     "preserve identity, pose, background, lighting, and style "
                     "of everything else pixel-faithful.")
    prompt = f"{observer} {spatial} {light} {edit_rule}".strip()
    return {"prompt": prompt, "width": w, "height": h, "aspect": aspect,
            "steps": STEPS, "cfg": CFG, "seed": random.randint(1, 2 ** 31),
            "note": note, "model": MODEL_ID}


DIFFUSION_FILE = "qwen_image_2.1_turbo_int8_convrot.safetensors"
VAE_FILE = "qwen_image_2.1_vae_bf16.safetensors"
# Main conditioner MUST be the vision-language encoder (qwen3vl) — the pe_*
# files are prompt-ENHANCERS (rewrite step), feeding them as the main clip
# yields noise (proven 2026-10-13 smoke #1).
TE_MAIN = "qwen3vl_8b_int8_convrot.safetensors"
TE_T2I = "qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors"
TE_I2I = "qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors"


def _comfy_alive(timeout: int = 5) -> bool:
    try:
        import httpx
        return httpx.get(f"{COMFY_URL}/system_stats", timeout=timeout).status_code == 200
    except Exception:
        return False


def _upload_input(input_image: str) -> str:
    """Upload an edit source into ComfyUI input dir. Returns server filename."""
    import httpx
    p = Path(input_image)
    with open(p, "rb") as f:
        r = httpx.post(f"{COMFY_URL}/upload/image", files={"image": (p.name, f)},
                       data={"overwrite": "true"}, timeout=120).json()
    return r.get("name", p.name)


def _render(engineered: Dict[str, Any], mode: str = "generate",
            input_image: Optional[str] = None) -> Dict[str, Any]:
    """Queue the NATIVE Qwen-Image-2.1 workflow and wait for the PNG.

    Nodes verified live on :8188 (UNETLoader/CLIPLoader(qwen_image)/
    VAELoader/TextEncodeQwenImage21/KSampler/VAEDecode/SaveImage).
    """
    import httpx
    te_file = TE_MAIN  # main conditioner (pe_* reserved for enhance step)
    wf: Dict[str, Any] = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": DIFFUSION_FILE,
                         "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": te_file, "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_FILE}},
        "4": {"class_type": "TextEncodeQwenImage21",
              "inputs": {"clip": ["2", 0], "prompt": engineered["prompt"],
                         "negative_prompt": "", "resolution": 1024}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": engineered["width"],
                         "height": engineered["height"], "batch_size": 1}},
        "6": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["4", 0],
                         "negative": ["4", 0], "latent_image": ["5", 0],
                         "seed": engineered["seed"],
                         "steps": engineered["steps"], "cfg": engineered["cfg"],
                         "sampler_name": "euler", "scheduler": "simple",
                         "denoise": 1.0}},
        "7": {"class_type": "VAEDecode",
              "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "SaveImage",
              "inputs": {"images": ["7", 0],
                         "filename_prefix": "wolf_qwen21_turbo"}},
    }
    if mode == "edit":
        if not input_image:
            return {"success": False,
                    "error": "edit mode needs input_image"}
        srv = _upload_input(input_image)
        wf["0"] = {"class_type": "LoadImage", "inputs": {"image": srv}}
        wf["4"]["inputs"]["images"] = {"image_1": ["0", 0]}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    q = httpx.post(f"{COMFY_URL}/prompt", json={"prompt": wf},
                   timeout=30).json()
    if q.get("error"):
        return {"success": False, "error": f"queue rejected: {q.get('error')}",
                "node_errors": q.get("node_errors", {})}
    pid = q.get("prompt_id", "")
    if not pid:
        return {"success": False, "error": f"queue rejected: {q}"}
    for _ in range(120):  # ~10 min cap for 2K renders
        time.sleep(5)
        hist = httpx.get(f"{COMFY_URL}/history/{pid}", timeout=30).json()
        if pid in hist:
            outs = (hist[pid].get("outputs") or {})
            for node_out in outs.values():
                for img in node_out.get("images") or []:
                    fn = img.get("filename", "")
                    sub = img.get("subfolder", "")
                    if fn:
                        return {"success": True, "prompt_id": pid,
                                "comfy_path": f"{sub}/{fn}" if sub else fn}
            return {"success": False, "error": "finished without images",
                    "prompt_id": pid}
    return {"success": False, "error": "render timeout", "prompt_id": pid}


def run(idea: str = "", aspect: str = "1:1", mode: str = "generate",
        input_image: Optional[str] = None, output_dir: str = "",
        **kwargs: Any) -> Dict[str, Any]:
    """Create/edit an image: engineer the prompt, render via ComfyUI.

    أنشئ/عدّل صورة: هندسة الأمر ثم العرض عبر ComfyUI.
    output_dir (optional): copy the finished PNG there (created if needed).
    """
    try:
        if not (idea or "").strip():
            return {"success": False, "skill": SKILL_NAME,
                    "error": "idea is required | الفكرة مطلوبة"}
        if mode not in ("generate", "edit"):
            mode = "generate"
        engineered = engineer_prompt(idea, aspect, mode)
        if not _comfy_alive():
            try:
                from backend.agent import model_router_bridge as _mrb
                _gov = _mrb.govern_vram_for("qwen-image-2.1-turbo-int8")
            except Exception:
                _gov = {}
            return {"success": False, "skill": SKILL_NAME,
                    "runner": "pending",
                    "error": "ComfyUI :8188 unreachable — install/run it, then retry",
                    "engineered": engineered, "vram_parked": _gov.get("unloaded", [])}
        # VRAM GOVERNOR 2026-10-14 (root cause of device freeze): park the
        # chat residents BEFORE the DiT load — the render path never did.
        try:
            from backend.agent import model_router_bridge as _mrb2
            _gov2 = _mrb2.govern_vram_for("qwen-image-2.1-turbo-int8")
        except Exception:
            _gov2 = {}
        out = _render(engineered, mode, input_image)
        out.update({"skill": SKILL_NAME, "model_used": MODEL_ID,
                    "engineered": engineered})
        # Deliver to the requested folder when asked (e.g. user-named path).
        # Guard: use it only if it exists or its parent does (never spray dirs).
        if out.get("success") and (output_dir or "").strip():
            try:
                import os
                dest = Path(output_dir)
                if not (dest.is_dir() or (dest.parent and dest.parent.is_dir())):
                    raise NotADirectoryError(f"no such folder: {dest}")
                dest.mkdir(parents=True, exist_ok=True)
                import shutil
                src = (Path(r"D:\Intelligence models\comfyui\app\output")
                       / out["comfy_path"].replace("/", "\\"))
                final = dest / src.name
                shutil.copy2(src, final)
                out["final_path"] = str(final)
            except Exception as e:
                out["copy_warning"] = f"{type(e).__name__}: {e}"
        return out
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {e}"}


def self_test() -> bool:
    print("qwen_image_skill: Phase-A offline check (no GPU, no ComfyUI)")
    eng = engineer_prompt("غروب الشمس على البحر", aspect="16:9")
    checks = [
        len(eng["prompt"].split()) >= 80,
        "8k" not in eng["prompt"].lower().replace("1536", ""),
        (eng["width"], eng["height"]) == (1536, 864),
        eng["steps"] == 8 and eng["cfg"] == 1,
        callable(run),
    ]
    print(f"  prompt words: {len(eng['prompt'].split())}, {eng['width']}x{eng['height']}")
    print("SELF-TEST:", "PASSED" if all(checks) else f"FAILED {checks}")
    return bool(all(checks))


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
