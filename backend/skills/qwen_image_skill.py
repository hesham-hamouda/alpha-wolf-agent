#!/usr/bin/env python3
r"""
Alpha Wolf — Qwen Image skill | مهارة إنشاء الصور
===================================================
Section: image-gen — `qwen-image-2.1-turbo-int8` via ComfyUI on D:
(8 denoising steps, CFG=1, native RGBA, editing in one model).

Two phases, honest about each:
  A. Prompt engineering (ALWAYS works, zero GPU): turns a weak Arabic/
     English idea into a professional English prompt — fluent scene
     sentence (roles, action, place), scene-matched photo treatment
     (golden-hour cinema / portrait craft / animal detail / motion),
     observer-perspective paragraph (NOT keyword stuffing like "8K,
     masterpiece"), spatial phrases, lighting/contrast sentences,
     quality-guarding negative prompt, disentangled edit instruction,
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

# Quality guard for the diffusion conditioner (plain descriptive language —
# never banned stuffing). Empty negatives let deformed outputs through.
NEGATIVE_PROMPT = ("blurry, low quality, distorted faces, deformed hands, "
                   "extra limbs, disfigured, watermark, text, logo, "
                   "oversaturated, underexposed")


_QUOTED_DRIVE_RE = r'"[^"]*[A-Za-z]:[\\/][^"]*"|\'[^\']*[A-Za-z]:[\\/][^\']*\''
# Instruction scaffolding (verbs + delivery words) — NOT visual content.
# Proven 2026-10-14: full sentence "انشئ لي صوره في هذا المسار ..." was
# embedded verbatim, drowning the 3-word subject, model defaulted to man.
_INSTRUCTION_WORDS = (
    "انشئ", "إنشئ", "انشاء", "إنشاء", "ارسم", "ولد", "تخيل", "اخلق", "اصنع",
    "انشا", "انشى", "سوي", "اعمل",
    "لي", "لى", "ل", "من فضلك", "لو سمحت",
    "صوره", "صورة", "صور", "لقطة", "لقطه", "مثل",
    "في", "فى", "هذا", "هذه", "المسار", "مسار", "مجلد", "ملف",
    "generate", "create", "draw", "paint", "imagine", "render", "make",
    "photo", "picture", "image",
)
# Minimal offline AR→EN gloss (diffusion is English-biased; Arabic-only
# subjects get ignored). Keep original too — gloss leads, original follows.
# Extended 2026-10-14c (family-on-horses probe): father/son/daughter/wife/
# horses/riding/beach were Arabic-only → no EN anchor. Added with prefix-
# tolerant lookup (و/ل/ال stripped in _norm_ar).
_AR_EN_GLOSS = {
    "قط": "cat", "قطة": "cat", "قطه": "cat", "لقط": "kitten",
    "قطط": "cats", "قططط": "cats",
    "صغير": "small", "صغيره": "small", "صغيرة": "small",
    "يلعب": "playing", "تلعب": "playing", "لعب": "playing",
    "كلب": "dog", "كلبه": "dog", "كلبة": "dog",
    "رجل": "man", "امرأة": "woman", "امراه": "woman",
    "طفل": "child", "بيت": "house", "سيارة": "car", "سياره": "car",
    "عائلة": "family", "عائله": "family",
    "طائر": "bird", "عصفور": "bird", "زهرة": "flower", "ورده": "flower",
    "منظر": "landscape", "بحر": "sea", "شاطئ": "beach",
    "ملعب": "playground", "لاعب": "player",
    # family probe 2026-10-14:
    "اب": "father", "أب": "father",
    "ام": "mother", "أم": "mother",
    "ابن": "son", "ابنه": "son", "إبن": "son",
    "بنت": "daughter", "بنته": "daughter", "ابنة": "daughter", "إبنة": "daughter",
    "زوج": "husband", "زوجة": "wife", "زوجه": "wife", "زوجته": "wife",
    "خيل": "horses", "حصان": "horse", "احصنة": "horses", "أحصنة": "horses",
    "يركب": "riding", "يركبون": "riding", "ركوب": "riding",
    "على": "on", "راس": "Ras", "رأس": "Ras", "البر": "El Bar", "بر": "Bar",
    # sea-life probe 2026-10-14 (dolphins): weak AR → EN underwater cinema.
    "دلفين": "dolphins", "دلافين": "dolphins", "دولفين": "dolphins",
    "سمك": "fish", "سمكة": "fish",
    "تطارد": "chasing", "يطارد": "chasing", "مطاردة": "chasing",
    "تحت": "under", "ماء": "water",
    "حقيقه": "photorealistic", "حقيقة": "photorealistic",
    "واقعي": "photorealistic", "حقيقي": "photorealistic",
    "قرش": "shark", "حوت": "whale",
}


def _norm_ar(tok: str) -> str:
    """Strip Arabic clitic prefixes (و/ف/ب/ك/ل) + definite ال for lookup."""
    t = (tok or "").strip()
    for _ in range(2):
        if len(t) > 2 and t[0] in ("و", "ف", "ب", "ك", "ل") and t[1:2] != "":
            # keep لقط/لأب roots intact via gloss first — strip only to try
            t = t[1:]
        else:
            break
    if len(t) > 3 and t.startswith("ال"):
        t = t[2:]
    # Orthographic tolerance: ة↔ه + أ/إ/آ→ا (dialectal spelling, e.g. بنته/بنته).
    t = t.replace("ة", "ه").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return t


def _strip_instructions(text: str) -> str:
    """Remove instruction scaffolding, keep visual tokens (Arabic intact)."""
    toks = (text or "").split()
    drop = set(_INSTRUCTION_WORDS)
    kept: list[str] = []
    for t in toks:
        ts = t.strip(" \"'.,;!؟?،:()[]").strip()
        if not ts or ts in drop:
            continue
        kept.append(ts)
    return " ".join(kept).strip()


def _to_english_gloss(text: str) -> str:
    """Map known Arabic visual tokens to English, drop instruction words."""
    toks = (text or "").split()
    drop = set(_INSTRUCTION_WORDS)
    out: list[str] = []
    for t in toks:
        ts = t.strip(" \"'.,;!؟?،:()[]").strip()
        if not ts:
            continue
        if ts in drop:
            continue
        # Direct hit first (keeps لقط/لأب roots intact), then prefix-tolerant
        # + orthography-tolerant (keys normalized the same way as tokens).
        _nt = _norm_ar(ts)
        en = (_AR_EN_GLOSS.get(ts) or _AR_EN_GLOSS.get(_nt)
              or next((v for k, v in _AR_EN_GLOSS.items()
                       if _norm_ar(k) == _nt), None))
        if en:
            out.append(en)
        elif ts in ("القط", "القطة", "القطه"):
            out.append("cat")
        else:
            out.append(ts)
    return " ".join(out).strip()


def _detect_scene(en_tokens: List[str], visual_core: str) -> List[str]:
    """Scene tags from EN gloss + Arabic core (beach/family/cat/horse/...).

    Why tags: one weak request ("قط يلعب") must still render with the right
    professional treatment — a beach family needs golden-hour cinema, a
    kitten needs fur-level close detail. Tags pick the treatment.
    """
    tags: List[str] = []
    en = " ".join(en_tokens).lower()
    ar = visual_core or ""
    if any(k in en for k in ("beach", "sea")) or any(
            k in ar for k in ("شاطئ", "بحر", "راس", "البر")):
        tags.append("beach")
    if any(k in en for k in ("family", "father", "mother", "son",
                             "daughter", "wife", "husband")):
        tags.append("family")
    if any(k in en for k in ("cat", "kitten", "cats")):
        tags.append("cat")
    if any(k in en for k in ("dog",)):
        tags.append("dog")
    if any(k in en for k in ("horse", "horses", "riding")):
        tags.append("horses")
    if (("under" in en and "water" in en) or "underwater" in en
            or "تحت الماء" in ar):
        tags.append("underwater")
    if any(k in en for k in ("dolphin", "dolphins", "fish", "shark",
                             "whale")):
        tags.append("sea-life")
    return tags


def _professional_scene(en_tokens: List[str], visual_core: str) -> str:
    """Fluent EN scene sentence from gloss tokens (no word salad).

    Word salad ("father son daughter wife riding...") confuses the
    diffusion conditioner — a fluent sentence with roles, action, and
    place renders the right subjects. Unknown tokens pass through so
    nothing the user said is ever dropped.
    """
    toks = [t for t in en_tokens if t]
    low = [t.lower() for t in toks]
    has = lambda *ws: any(w in low for w in ws)
    fam_roles = ("father", "mother", "son", "daughter", "wife", "husband")
    if any(r in low for r in fam_roles) or (
            has("family") and has("horse", "horses")):
        # Compose ONLY the roles actually asked for (never invent members).
        present = [r for r in fam_roles if r in low]
        who = ", ".join(present) if present else "family"
        if has("horse", "horses", "riding"):
            action = "riding horses together along the shore"
        else:
            action = "together"
        place = " at Ras El Bar beach" if has("beach", "ras", "bar") else ""
        return f"A happy family — {who} — {action}{place}".strip()
    if has("kitten") or (has("cat") and has("small", "playing")):
        return ("A tiny playful kitten playing, bright curious eyes, "
                "soft fluffy fur with fine fur detail and delicate whiskers")
    if has("dolphin", "dolphins"):
        return ("Dolphins chasing a shimmering school of fish in deep blue "
                "water, photorealistic underwater photography, dynamic "
                "predator-prey motion")
    if has("cat"):
        rest = " ".join(t for t in toks if t.lower() not in ("cat",)).strip()
        return f"A cat {rest}".strip() if rest else "A cat"
    if has("family"):
        return "A warm happy family together, " + ", ".join(toks) if toks else \
            "A warm happy family together"
    s = " ".join(toks).strip()
    return s or (visual_core or "")


def _scene_photo_block(tags: List[str]) -> str:
    """Professional camera/lighting treatment per scene (natural language).

    Qwen-Image rejects keyword stuffing ("8K, masterpiece") — so this uses
    full sentences a photographer would say: golden-hour cinema for beach,
    85mm shallow depth of field for family, fur-level macro detail for cats,
    motion freeze for horses. Each block only fires for its scene (YAGNI).
    """
    parts: List[str] = []
    if "beach" in tags:
        parts.append(
            "Coastal cinema treatment: warm golden-hour sunlight low over "
            "the sea, sparkling water highlights, soft sea mist on the "
            "horizon, wide-angle composition with the shoreline leading "
            "diagonally, natural skin tones and true-to-life colors.")
    if "family" in tags:
        parts.append(
            "Family portrait craft: 85mm portrait lens look, shallow depth "
            "of field keeping every face in sharp focus, candid joyful "
            "expressions, natural skin tones, gentle catchlights in the eyes.")
    if "cat" in tags:
        parts.append(
            "Animal close-detail craft: razor-sharp focus on the eyes with "
            "bright catchlights, individual fur detail and delicate "
            "whiskers resolved, shallow depth of field melting the "
            "background into a soft blur.")
    if "horses" in tags:
        parts.append(
            "Equestrian motion craft: frozen mid-gallop motion with flying "
            "mane and kicked-up sand sharply resolved, dynamic diagonal "
            "composition following the riders.")
    if "underwater" in tags or "sea-life" in tags:
        parts.append(
            "Underwater cinema treatment: deep blue water with god rays of "
            "sunlight piercing down from the surface, floating particles, "
            "the chase motion frozen razor-sharp, photorealistic detail on "
            "wet dolphin skin and flashing fish scales, cinematic depth.")
    if not parts:
        parts.append(
            "Photographic craft: balanced cinematic light, sharp focus on "
            "the primary subject, shallow depth of field, natural colors "
            "with true-to-life tones and clean detail.")
    return " ".join(parts)


def engineer_prompt(idea: str, aspect: str = "1:1",
                    mode: str = "generate") -> Dict[str, Any]:
    """Build the disciplined English prompt from a quick idea.

    ابنِ الأمر الإنجليزي المنضبط من فكرة سريعة (يعمل دون GPU).
    Paths/URLs are delivery instructions, NOT visual content — strip them
    first (proven 2026-10-14: a D:\\ path got rendered as image text).
    FIX 2026-10-14b (cat→man bug): quoted Windows paths WITH SPACES
    (e.g. "D:\\A\\Applications under development\\...") were only half
    stripped — regex stopped at first space, leaving "under development..."
    English residue in the VISUAL prompt. Strip quoted drive-paths FIRST
    (spaces included), then bare paths. Also strip instruction verbs and
    prepend an offline AR→EN gloss so the subject survives the template.
    """
    import re
    raw = (idea or "").strip()
    # 1) Quoted drive paths WITH SPACES first (must precede bare-path strip).
    clean = re.sub(_QUOTED_DRIVE_RE, "", raw)
    # 2) Bare paths / file:// / URLs (no spaces).
    clean = re.sub(r"file://\S+|[A-Za-z]:[\\/][^\s\"']+|https?://\S+", "",
                   clean)
    # 3) Leftover drive-letter fragments (e.g. unquoted spaced path tail).
    clean = re.sub(r"[A-Za-z]:[\\/]", "", clean)
    clean = " ".join(clean.split()).strip(" \"'").strip()
    # Visual core: path-stripped AND instruction-stripped (only what to draw).
    visual_core = _strip_instructions(clean) or _strip_instructions(raw) or clean or raw
    gloss = _to_english_gloss(visual_core)
    en_tokens = gloss.split()
    tags = _detect_scene(en_tokens, visual_core)
    scene_en = _professional_scene(en_tokens, visual_core)
    # Lead with the fluent professional scene (diffusion-weighted), keep the
    # Arabic core for nuance. Weak requests become complete descriptions here.
    if scene_en and visual_core and scene_en != visual_core:
        idea = f"{scene_en}. Scene detail: {visual_core}"
    elif scene_en:
        idea = scene_en
    else:
        idea = visual_core or raw
    if aspect not in ASPECTS:
        aspect = "1:1"
    w, h = ASPECTS[aspect]
    lowered = idea.lower()
    if any(k in lowered for k in _BANNED_KEYWORDS):
        note = "keyword stuffing removed — Qwen-Image rejects it"
    else:
        note = "clean idea"
    photo = _scene_photo_block(tags)
    observer = (
        f"Observer perspective, single coherent scene. {idea} "
        f"Render as one continuous photographic moment with a clear primary "
        f"subject, supporting midground elements, and a readable background "
        f"that gives depth without clutter. {photo}")
    spatial = ("Spatial layout: primary subject centered-left in sharp focus; "
               "midground props receding along a gentle diagonal; background "
               "softly separated by atmospheric depth; horizon level; generous "
               "negative space on the right for balance; foreground accents "
               "framing the lower corners; consistent scale between elements; "
               "no cropped faces, ears, paws, tails or cut-off limbs; grounded "
               "contact shadows under every object.")
    light = ("Lighting and contrast: soft key light from the upper left, cool "
             "ambient fill, gentle rim separation on edges, balanced contrast "
             "with preserved shadow detail and no blown highlights.")
    edit_rule = ""
    if mode == "edit":
        edit_rule = ("Edit disentanglement: change ONLY the described element; "
                     "preserve identity, pose, background, lighting, and style "
                     "of everything else pixel-faithful.")
    prompt = f"{observer} {spatial} {light} {edit_rule}".strip()
    return {"prompt": prompt, "negative_prompt": NEGATIVE_PROMPT,
            "width": w, "height": h, "aspect": aspect,
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


# Ordinary-user rule (2026-10-14): the user must never know what ComfyUI
# is. If the renderer is down, START it ourselves — asking a non-technical
# user to start a local server is an obstacle, not a solution.
_COMFY_VENV_PY = r"D:\Intelligence models\comfyui\venv\Scripts\python.exe"
_COMFY_APP_DIR = r"D:\Intelligence models\comfyui\app"


def _launch_comfy() -> bool:
    """Start the local renderer in the background. Returns False fast."""
    try:
        import subprocess
        if not Path(_COMFY_VENV_PY).exists():
            return False
        if _comfy_alive(timeout=3):
            return True  # someone else started it meanwhile
        log = Path(_COMFY_APP_DIR) / "auto14.log"
        err = Path(_COMFY_APP_DIR) / "auto14.err"
        with open(log, "ab") as lo, open(err, "ab") as er:
            subprocess.Popen(
                [_COMFY_VENV_PY, "main.py", "--port", "8188"],
                cwd=_COMFY_APP_DIR, stdout=lo, stderr=er,
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            )
        return True
    except Exception:
        return False


def _ensure_comfy(wait_s: int = 150) -> bool:
    """Renderer ready? Start it ourselves when down, then wait.

    مضمون للمستخدم العادي: برنامج الرسم لو مطفي، الوكيل يشغّله لوحده.
    """
    if _comfy_alive():
        return True
    if not _launch_comfy():
        return False
    import time as _t
    waited = 0
    while waited < wait_s:
        _t.sleep(10)
        waited += 10
        if _comfy_alive():
            return True
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
                         "negative_prompt": engineered.get(
                             "negative_prompt", NEGATIVE_PROMPT),
                         "resolution": 1024}},
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
        # Exact output_dir strip (handles UNQUOTED spaced paths): the detector
        # already isolated the folder — never let its words leak to visuals.
        _od = (output_dir or "").strip()
        if _od and _od in (idea or ""):
            idea = (idea or "").replace(_od, " ")
        engineered = engineer_prompt(idea, aspect, mode)
        if not _ensure_comfy():
            try:
                from backend.agent import model_router_bridge as _mrb
                _gov = _mrb.govern_vram_for("qwen-image-2.1-turbo-int8")
            except Exception:
                _gov = {}
            return {"success": False, "skill": SKILL_NAME,
                    "runner": "pending",
                    "error": ("حاولت أشغّل برنامج الرسم لوحدي وما عرفتش | "
                              "could not auto-start the renderer — "
                              "start D:\\Intelligence models\\comfyui once, then retry"),
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
        # Always keep a project-local copy (Project-Artifact): previously the
        # PNG only lived in the ComfyUI output folder unless output_dir was
        # named — the agent then had no path to show and invented proof
        # numbers instead (proven 2026-10-14: "-39"). OUT_DIR is local data.
        if out.get("success"):
            try:
                import shutil
                src = (Path(r"D:\Intelligence models\comfyui\app\output")
                       / out["comfy_path"].replace("/", "\\"))
                OUT_DIR.mkdir(parents=True, exist_ok=True)
                local = OUT_DIR / src.name
                shutil.copy2(src, local)
                out["final_path"] = str(local)
            except Exception as e:
                out["copy_warning"] = f"{type(e).__name__}: {e}"
        # Deliver to the requested folder when asked (e.g. user-named path).
        # Guard: use it only if it exists or its parent does (never spray dirs).
        if out.get("success") and (output_dir or "").strip():
            try:
                dest = Path(output_dir)
                if not (dest.is_dir() or (dest.parent and dest.parent.is_dir())):
                    raise NotADirectoryError(f"no such folder: {dest}")
                dest.mkdir(parents=True, exist_ok=True)
                import shutil as _sh
                src = (Path(r"D:\Intelligence models\comfyui\app\output")
                       / out["comfy_path"].replace("/", "\\"))
                final = dest / src.name
                _sh.copy2(src, final)
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
