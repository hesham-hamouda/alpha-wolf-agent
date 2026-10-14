#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Model Router Bridge | جسر توجيه النماذج
============================================================
Thin adapter between the backend and BUILD's `build-model-router` engine
(E:/Agents/BUILD/engines/jev-packs/build-model-router/).

SAFETY CONTRACT (fail-safe — never break a green turn):
- Every public function catches its own exceptions and falls back to the
  known-good defaults (spark for chat, moondream for light vision).
- NOTHING here calls an LLM for decisions: the engine runs in keyword mode
  (`use_model=False`) — zero VRAM, microseconds.
- `govern_vram_for` only UNLOADS (never loads); Ollama reloads on demand.
- `maybe_distill_turn` only writes via the body's own existing impls and
  never raises into the request path.

Registry mapping: the engine speaks short Ollama names ("moondream"),
the backend registry uses full ids ("moondream:latest") — mapped here.
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("alpha_wolf.model_router")

ENGINE_DIR = Path("E:/Agents/BUILD/engines/jev-packs/build-model-router")

SPARK = "maternion/spark-x2.5:4b-q4_K_M"
CHAT_FALLBACK_ORDER = [SPARK, "qwen3:4b", "qwen2.5:1.5b", "qwen2.5:0.5b"]

# engine name -> backend registry id
TO_REGISTRY = {"moondream": "moondream:latest"}
FLAGSHIP_VISION = "qwen2.5vl:7b"
# Models that must park the chat model first (VRAM governor).
PARK_CHAT_FOR = {FLAGSHIP_VISION, "chandra-ocr-2",
                 "qwen-image-2.1-turbo-int8", "qwen-image-2.1-bf16"}

_engine: dict[str, Any] = {"router": None, "sections": None, "tried": False}


def _load_engine() -> bool:
    """Import BUILD engine files by path (stdlib only). Never raises."""
    if _engine["tried"]:
        return _engine["router"] is not None
    _engine["tried"] = True
    try:
        import sys
        if str(ENGINE_DIR) not in sys.path:
            sys.path.insert(0, str(ENGINE_DIR))
        for key, fname in (("router", "router.py"), ("sections", "sections.py")):
            spec = importlib.util.spec_from_file_location(
                f"build_model_router_{key}", str(ENGINE_DIR / fname))
            if spec is None or spec.loader is None:
                return False
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _engine[key] = mod
        logger.info("[ModelRouter] BUILD engine loaded from %s", ENGINE_DIR)
        return True
    except Exception as e:
        logger.warning("[ModelRouter] engine unavailable, static defaults: %s", e)
        _engine["router"] = None
        _engine["sections"] = None
        return False


def _to_registry(name: str) -> str:
    return TO_REGISTRY.get(name, name)


def route_chat(last_user_text: str = "") -> dict[str, Any]:
    """Pick the chat model for a turn — ALWAYS spark (leader philosophy).

    سبارك أساسي كل النص. البدلاء (qwen3:4b...) للفشل فقط عبر fallback_next —
    لا استبدال استباقي أبداً (REVERT 2026-10-14: التوجيه المسبق كان خطأ مني).
    """
    section, skill = "chat", ""
    if _load_engine():
        try:
            section = _engine["sections"].section_for(last_user_text or "")
            skill = _engine["sections"].skill_for_section(section)["skill"]
        except Exception as e:
            logger.warning("[ModelRouter] section detect failed: %s", e)
    return {"model": SPARK, "section": section, "skill": skill}


def fallback_next(failed_model: str) -> str:
    """Next chat model after a failure, or "" when the chain is exhausted.

    البديل التالي بعد الفشل، أو فراغ عند انتهاء السلسلة (صعّد بصدق).
    The backend registry is authoritative here: the BUILD engine chain is a
    superset containing names this backend cannot serve, so the static
    registry order below wins (deterministic, testable offline).
    """
    try:
        i = CHAT_FALLBACK_ORDER.index(failed_model)
        return CHAT_FALLBACK_ORDER[i + 1] if i + 1 < len(CHAT_FALLBACK_ORDER) else ""
    except ValueError:
        return SPARK if failed_model != SPARK else "qwen3:4b"


def pick_vision(prompt: str = "") -> dict[str, Any]:
    """Choose the vision model for a see_image call (light co-lives,
    flagship unloads chat first). Returns registry ids.

    يختار نموذج الرؤية — الخفيف يعيش مع الشات، الكبير يفرّغه أولاً.
    """
    model, action = "moondream:latest", "co_live"
    if _load_engine():
        try:
            a = _engine["router"].next_action(
                {"stage": "before_tool", "tool_name": "see_image",
                 "detail": prompt or ""})
            model, action = _to_registry(a["model"]), a.get("vram_action", "co_live")
        except Exception as e:
            logger.warning("[ModelRouter] vision pick failed: %s", e)
    return {"model": model, "vram_action": action}


def govern_vram_for(target_registry_id: str, ollama_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    """Park chat residents when a heavy model needs the VRAM.

    يفرّغ الشات مؤقتاً للنماذج الثقيلة (راية الرؤية/شاندرا/التوليد).
    Best-effort: never raises, returns what was unloaded. (Ollama-side
    residents only; transformers/ComfyUI runners manage their own device
    maps but still benefit from the freed VRAM.)
    """
    if target_registry_id not in PARK_CHAT_FOR:
        return {"unloaded": [], "reason": "co-live — no parking needed"}
    unloaded: list[str] = []
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            for mid in CHAT_FALLBACK_ORDER:
                try:
                    client.post(f"{ollama_url.rstrip('/')}/api/generate",
                                json={"model": mid, "keep_alive": 0})
                    unloaded.append(mid)
                except Exception as e:
                    logger.warning("[ModelRouter] unload %s failed: %s", mid, e)
    except Exception as e:
        logger.warning("[ModelRouter] VRAM govern failed: %s", e)
    return {"unloaded": unloaded,
            "reason": "heavy model parked chat — chat reloads on next turn"}


def pick_image(prompt: str = "") -> dict[str, Any]:
    """Choose the image-generation model (turbo int8 first).

    يختار نموذج توليد الصور — التوربو أولاً ثم الكامل.
    """
    if _load_engine():
        try:
            a = _engine["router"].next_action(
                {"stage": "before_tool", "tool_name": "generate_image",
                 "detail": prompt or ""})
            return {"model": a["model"], "vram_action": a.get("vram_action", "unload_chat_first")}
        except Exception as e:
            logger.warning("[ModelRouter] image pick failed: %s", e)
    return {"model": "qwen-image-2.1-turbo-int8", "vram_action": "unload_chat_first"}


def pick_ocr(prompt: str = "") -> dict[str, Any]:
    """Choose the OCR model (chandra first, transformers runner).

    يختار نموذج قراءة المستندات — شاندرا أولاً.
    """
    if _load_engine():
        try:
            a = _engine["router"].next_action(
                {"stage": "before_tool", "tool_name": "read_document",
                 "detail": prompt or ""})
            return {"model": a["model"], "vram_action": a.get("vram_action", "unload_chat_first")}
        except Exception as e:
            logger.warning("[ModelRouter] ocr pick failed: %s", e)
    return {"model": "chandra-ocr-2", "vram_action": "unload_chat_first"}


def maybe_distill_turn(messages: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    """Auto-distill one finished non-stream turn into body memory.

    تقطير تلقائي للدور: نظّف → إن كان يستحق → خزّن بأدوات الجسد.
    Skips errors, short replies, and junk. Never raises.
    """
    try:
        if not isinstance(result, dict) or result.get("status") in (
                "backend_unavailable", "endpoint_error"):
            return {"distilled": False, "reason": "error result — skipped"}
        choices = result.get("choices") or []
        answer = ((choices[0].get("message") or {}).get("content") or "") if choices else ""
        if len(answer.strip()) < 200:
            return {"distilled": False, "reason": "short reply — skipped"}
        last_user = next((str(m.get("content", "")) for m in reversed(messages or [])
                          if m.get("role") == "user" and str(m.get("content", "")).strip()), "")
        if not _load_engine():
            return {"distilled": False, "reason": "engine unavailable"}
        tri = _engine["sections"].distill_triage(
            f"{last_user}\n{answer}", source="auto-distill/chat-turn")
        if not tri.get("store"):
            return {"distilled": False, "reason": tri.get("reason", "junk")}
        from backend.agent import tools as _tools
        target = tri.get("target", "remember_episode")
        if target == "log_mistake":
            out = _tools._log_mistake_impl(
                description=f"auto-distilled turn: {last_user[:200]}",
                severity="low", lesson=tri["cleaned"][:1000])
        else:
            out = _tools._remember_episode_impl(
                # trigger_type must satisfy the body CHECK constraint;
                # 'self_reflection' = the agent's own learning. The
                # 'auto-distill' tag marks machine-distilled rows.
                trigger_type="self_reflection", content=tri["cleaned"][:2000],
                importance=6, tags=["auto-distill", target])
        ok = bool(getattr(out, "success", False))
        logger.info("[ModelRouter] auto-distill → %s ok=%s", target, ok)
        return {"distilled": ok, "target": target, "dedup": tri.get("dedup", "")}
    except Exception as e:
        logger.warning("[ModelRouter] distill skipped: %s", e)
        return {"distilled": False, "reason": f"guarded: {type(e).__name__}"}


def engines_report() -> dict[str, Any]:
    """Role contract of every engine in this architecture (honest pending)."""
    if _load_engine():
        try:
            return _engine["sections"].engines_health()
        except Exception as e:
            logger.warning("[ModelRouter] report failed: %s", e)
    return {"verdict": "unknown", "reason": "engine unavailable"}


# ============================================================================
# Chat-list layer (وصل 2026-10-13 — القائد: كل نموذج يظهر ويُستخدم منفرداً)
# Every specialist model gets a dropdown entry; turns resolve here instead
# of Ollama. via: direct (Ollama id) | skill (Wolf skill file) |
# generate (hf_runner text-gen) | tool (see_image) | pending (honest card).
# Embeddings are infra (serve search on every turn) — NOT chat entries.
# ============================================================================

# display skill name -> backend/skills/*.py (no .py)
SKILL_FILES = {
    "doc-read": "chandra_ocr_skill", "image-forge": "qwen_image_skill",
    "speak": "speak_skill", "transcribe": "transcribe_skill",
    "math-verify": "math_skill", "structure-extract": "extract_skill",
    "protein-support": "protein_skill", "dna-support": "dna_skill",
    "chem-support": "chem_skill", "medical-support": "medical_skill",
    "sat-support": "satellite_skill", "agri-support": "agri_skill",
    "marine-support": "marine_skill", "food-support": "food_skill",
    "climate-support": "climate_skill", "audiofx-support": "audiofx_skill",
}
# skill file -> main input param for a text turn
FIRST_PARAM = {
    "chandra_ocr_skill": "image_path", "qwen_image_skill": "idea",
    "speak_skill": "text", "transcribe_skill": "audio_path",
    "math_skill": "problem", "extract_skill": "text",
    "protein_skill": "query", "dna_skill": "query", "chem_skill": "smiles",
    "medical_skill": "text", "satellite_skill": "image_path",
    "agri_skill": "image_path", "marine_skill": "image_path",
    "food_skill": "image_path", "climate_skill": "text",
    "audiofx_skill": "audio_path",
}
# (id, emoji, name_ar, name_en, caps, size_b, quant, via, ref)
# via: direct | skill:<display> | generate | tool:see_image | pending:<alt>
CHAT_EXTRA = [
    ("alpha-wolf-qwen2.5-1.5b", "⚡", "كوين الذئب 1.5B", "Wolf Qwen 1.5B named",
     ["text"], 2, "q4_K_M", "direct", ""),
    ("qwen2.5:1.5b-local", "⚡", "كوين 1.5B الأصلي", "Qwen 1.5B local original",
     ["text"], 2, "q4_K_M", "direct", ""),
    ("moondream", "🌙", "مووندريم (مختصر)", "Moondream short id",
     ["text", "vision"], 2, "q4_K_M", "tool:see_image", ""),
    ("Florence-2-base", "👁", "فلورنس 2 (قريباً)", "Florence-2 pending",
     ["text", "vision"], 1, "bf16", "pending:moondream", ""),
    ("dinov2-small", "👁", "دينو v2 (قريباً)", "DINOv2 pending",
     ["text", "vision"], 0, "bf16", "pending:moondream", ""),
    ("sam-vit-base", "👁", "سام (قريباً)", "SAM pending",
     ["text", "vision"], 1, "bf16", "pending:moondream", ""),
    ("chandra-ocr-2", "📄", "شاندرا OCR 2", "Chandra OCR 2",
     ["text", "vision"], 4, "bf16", "skill:doc-read", ""),
    ("GOT-OCR2_0", "📄", "جوت OCR (استخدم شاندرا)", "GOT-OCR2 use chandra",
     ["text", "vision"], 1, "bf16", "pending:chandra-ocr-2", ""),
    ("nougat-small", "📄", "نوقت علمي (استخدم شاندرا)", "Nougat use chandra",
     ["text", "vision"], 0, "bf16", "pending:chandra-ocr-2", ""),
    ("qwen-image-2.1-turbo-int8", "🎨", "توربو توليد 8 خطوات",
     "Qwen Image Turbo int8", ["text", "image"], 7, "int8",
     "skill:image-forge", ""),
    ("qwen-image-2.1-bf16", "🎨", "التوليد الكامل (استخدم التوربو)",
     "Qwen Image bf16 use turbo", ["text", "image"], 14, "bf16",
     "pending:qwen-image-2.1-turbo-int8", ""),
    ("faster-whisper-base", "🎙", "تفريغ base", "Whisper base",
     ["text", "audio"], 0, "ct2", "skill:transcribe", ""),
    ("faster-whisper-small", "🎙", "تفريغ small", "Whisper small",
     ["text", "audio"], 0, "ct2", "skill:transcribe", ""),
    ("faster-whisper-medium", "🎙", "تفريغ medium", "Whisper medium",
     ["text", "audio"], 1, "ct2", "skill:transcribe", ""),
    ("faster-whisper-large-v3-turbo", "🎙", "تفريغ توربو ⭐", "Whisper turbo",
     ["text", "audio"], 2, "ct2", "skill:transcribe", ""),
    ("supertonic3", "🔊", "نطق سوبرتونك", "Supertonic TTS",
     ["text", "audio"], 0, "onnx", "skill:speak", ""),
    ("Qwen2.5-Coder-1.5B", "💻", "كوين كودر 1.5B", "Qwen Coder 1.5B",
     ["text", "code"], 2, "bf16", "generate:Qwen/Qwen2.5-Coder-1.5B-Instruct", ""),
    ("SmolLM2-1.7B", "💻", "سمول 1.7B", "SmolLM2 1.7B",
     ["text", "code"], 2, "bf16", "generate:HuggingFaceTB/SmolLM2-1.7B-Instruct", ""),
    ("Qwen2.5-Math-1.5B", "🔢", "رياضيات 1.5B", "Qwen Math 1.5B",
     ["text"], 2, "bf16", "skill:math-verify", ""),
    ("NuExtract-tiny", "🧾", "استخلاص JSON", "NuExtract JSON",
     ["text"], 2, "bf16", "skill:structure-extract", ""),
    ("esm2_t30_150M", "🧬", "بروتين ESM كبير", "ESM-2 150M",
     ["text"], 0, "bf16", "skill:protein-support", ""),
    ("esm2_t12_35M", "🧬", "بروتين ESM صغير", "ESM-2 35M",
     ["text"], 0, "bf16", "skill:protein-support", ""),
    ("prot_bert", "🧬", "بروت بيرت", "ProtBERT",
     ["text"], 0, "bf16", "skill:protein-support", ""),
    ("DNABERT-2-117M", "🧪", "دنا بيرت 2", "DNABERT-2",
     ["text"], 0, "bf16", "skill:dna-support", ""),
    ("agro-nucleotide-1b", "🧪", "نيوكليوتيد زراعي", "Agro-nucleotide 1B",
     ["text"], 1, "bf16", "skill:dna-support", ""),
    ("hyenadna-tiny", "🧪", "هايينا DNA", "HyenaDNA tiny",
     ["text"], 0, "bf16", "skill:dna-support", ""),
    ("ChemBERTa-10M-MTR", "⚗", "كيم بيرتا خصائص", "ChemBERTa MTR",
     ["text"], 0, "bf16", "skill:chem-support", ""),
    ("MoLFormer-XL", "⚗", "مول فورمر", "MoLFormer XL",
     ["text"], 1, "bf16", "skill:chem-support", ""),
    ("phikon", "🏥", "فايكون شرائح", "Phikon slides",
     ["text", "vision"], 0, "bf16", "skill:medical-support", ""),
    ("BiomedCLIP", "🏥", "بايوميد كليب (استخدم بايوبيرت)", "BiomedCLIP use biobert",
     ["text", "vision"], 0, "bf16", "pending:biobert", ""),
    ("biobert", "🏥", "بايوبيرت", "BioBERT",
     ["text"], 0, "bf16", "skill:medical-support", ""),
    ("PathologyBERT", "🏥", "باثولوجي بيرت", "PathologyBERT",
     ["text"], 0, "bf16", "skill:medical-support", ""),
    ("scibert", "🏥", "ساي بيرت", "SciBERT",
     ["text"], 0, "bf16", "skill:medical-support", ""),
    ("clip-fine-tuned-satellite", "🛰", "قمر مصنّف", "Satellite CLIP",
     ["text", "vision"], 0, "bf16", "skill:sat-support", ""),
    ("segformer-b0", "🛰", "قمر مجزّئ", "SegFormer b0",
     ["text", "vision"], 0, "bf16", "skill:sat-support", ""),
    ("plantnet300k", "🌾", "نباتات 300k", "PlantNet 300k",
     ["text", "vision"], 0, "bf16", "skill:agri-support", ""),
    ("CGIAR-Crop", "🌾", "محاصيل CGIAR", "CGIAR Crop",
     ["text", "vision"], 0, "bf16", "skill:agri-support", ""),
    ("Mango_leaf", "🌾", "ورقة مانجو", "Mango leaf",
     ["text", "vision"], 0, "bf16", "skill:agri-support", ""),
    ("aquaculture_oysters", "🌾", "محار مزارع", "Aquaculture oysters",
     ["text", "vision"], 0, "bf16", "skill:agri-support", ""),
    ("vit-Diatome", "🌾", "دياتومات", "ViT Diatome",
     ["text", "vision"], 0, "bf16", "skill:agri-support", ""),
    ("Marine_Species", "🌊", "كائنات بحرية", "Marine Species",
     ["text", "vision"], 0, "bf16", "skill:marine-support", ""),
    ("CoralSCOP", "🌊", "مرجان", "CoralSCOP",
     ["text", "vision"], 0, "bf16", "skill:marine-support", ""),
    ("micro-algae", "🌊", "طحالب دقيقة", "Micro-algae",
     ["text", "vision"], 0, "bf16", "skill:marine-support", ""),
    ("fish-shrimp", "🌊", "سمك وجمبري", "Fish shrimp",
     ["text", "vision"], 0, "bf16", "skill:marine-support", ""),
    ("food-nateraw", "🍽", "طعام", "Food",
     ["text", "vision"], 0, "bf16", "skill:food-support", ""),
    ("climatebert", "🌡", "مناخ بيرت", "ClimateBERT",
     ["text"], 0, "bf16", "skill:climate-support", ""),
    ("tspulse-r1", "🌡", "نبض السلاسل", "TSPulse r1",
     ["text"], 0, "bf16", "skill:climate-support", ""),
    ("ttm-r2", "🌡", "تنبؤ TTM", "TinyTimeMixer r2",
     ["text"], 0, "bf16", "skill:climate-support", ""),
    ("videomae-base", "🎬", "فيديو MAE (قريباً)", "VideoMAE pending",
     ["text", "video"], 0, "bf16", "pending:see_image", ""),
    ("timesformer", "🎬", "تايم فورمر (قريباً)", "TimeSformer pending",
     ["text", "video"], 1, "bf16", "pending:see_image", ""),
    ("ast-finetuned-audioset", "🎧", "أحداث صوتية AST", "AST AudioSet",
     ["text", "audio"], 0, "bf16", "skill:audiofx-support", ""),
    ("wav2vec2-base", "🎧", "تمثيل كلامي", "wav2vec2",
     ["text", "audio"], 0, "bf16", "skill:audiofx-support", ""),
]
CHAT_EXTRA_IDS = [e[0] for e in CHAT_EXTRA]
# measured ctx for the sync test (0 = skill-backed, no prompt window)
CTX_OVERRIDES = {"alpha-wolf-qwen2.5-1.5b": (8192, 32768),
                 "qwen2.5:1.5b-local": (8192, 32768)}
SECTION_FLOW = {e[0]: {"via": e[7], "section": None} for e in CHAT_EXTRA}


def _section_of(model_id: str) -> str:
    if _load_engine():
        try:
            for sec, spec in _engine["sections"].SECTIONS.items():
                if model_id in spec["models"]:
                    return sec
        except Exception:
            pass
    return "chat"


def is_section_model(model_id: str) -> bool:
    """True for chat-list specialist ids (served by skills, not Ollama)."""
    if model_id in CHAT_EXTRA_IDS:
        via = next(e[7] for e in CHAT_EXTRA if e[0] == model_id)
        return not via.startswith("direct")
    return False


def needs_thinking_recovery(data: Any) -> bool:
    """True when a 200 response has EMPTY content but a thinking trace.

    Root cause of 'empty response from backend' on long turns (proven
    2026-10-14: 600-word article → 200 + content '' + reasoning present).
    The trace ate the whole max_tokens budget; the answer never started.
    Pure + unit-tested. Never raises.
    """
    try:
        if not isinstance(data, dict):
            return False
        if data.get("status") in ("backend_unavailable", "endpoint_error",
                                  "section_error"):
            return False
        choices = data.get("choices") or []
        if not choices:
            return False
        msg = choices[0].get("message", {}) or {}
        content = (msg.get("content") or "").strip()
        trace = str(msg.get("reasoning", "") or msg.get("thinking", "") or "")
        return (not content) and len(trace.strip()) > 50
    except Exception:
        return False


def _paths_from_text(text: str) -> List[str]:
    import re
    out: List[str] = []
    for m in re.finditer(
            r"file://(?P<f>/[^\s\"']+)|(?P<d>(?<![A-Za-z])(?:[A-Za-z]:[\\/]|/)[^\s\"']+)",
            text or ""):
        out.append(m.group("f") or m.group("d"))
    return list(dict.fromkeys(out))[:3]


def _convention(text: str, *tags: str) -> List[str]:
    """Parse 'fields: a, b' / 'vs: x | y' / 'series: 1, 2' blocks.

    Accepts line-start AND inline occurrences (chat users write inline).
    """
    import re
    for tag in tags:
        for pat in (rf"(?im)^{tag}\s*:\s*(.+)$", rf"(?i){tag}\s*:\s*(.+?)(?:\.|$)"):
            m = re.search(pat, text or "")
            if m:
                items = [c.strip() for c in re.split(r"[,|]", m.group(1)) if c.strip()]
                if items:
                    return items
    return []


def _strip_conventions(text: str) -> str:
    """Remove vs:/candidates:/fields:/series: blocks from the main input.

    Without this the query itself carries the candidates (proven live:
    identical protein ranked below poly-G because the query was contaminated).
    """
    import re
    clean = re.sub(r"(?im)^\s*(?:vs|candidates|fields|series)\s*:.*$", "",
                   text or "")
    clean = re.sub(r"(?i)\s+(?:vs|candidates|fields|series)\s*:[^.]*\.?", "",
                   clean)
    return " ".join(clean.split())


def _format_skill_answer(model_id: str, skill: str, res: Dict[str, Any]) -> str:
    # skills.run_skill wraps: {"success","skill","result":{...skill dict...}}
    inner = res.get("result") if isinstance(res.get("result"), dict) else res
    if not isinstance(inner, dict):
        return f"[{skill}] {str(inner)[:2000]}"
    if inner.get("success", res.get("success", False)):
        keep = {k: v for k, v in inner.items()
                if k in ("answer", "data", "ranking", "similar", "predictions",
                         "events", "segments", "forecast", "text", "markdown",
                         "wav_path", "comfy_path", "code_check", "properties",
                         "embedding_dim", "slide_embedding_dim")}
        import json as _j
        body = _j.dumps(keep, ensure_ascii=False, default=str)[:4000]
        return f"[{model_id} عبر {skill}]\n{body}"
    return (f"[{model_id} عبر {skill}] تعذّر: "
            f"{str(inner.get('error', res.get('error', 'unknown')))[:500]}")


def _ask_spark_verify(user_text: str, facts: str, model_id: str,
                      skill: str,
                      ollama_url: str = "http://127.0.0.1:11434") -> str:
    """Spark answers USING the specialist facts (leader philosophy 2026-10-14:
    سبارك يرد والمتخصص يؤكد — never the reverse). Returns "" on any failure
    so the caller falls back to the raw facts. Never raises.
    reasoning_effort=none reuses the codebase's own anti-starvation lever
    (streaming.py Round 13): thinking models must not eat the budget."""
    try:
        import httpx
        system = ("You are Alpha Wolf Agent. Answer in 2-4 short lines using "
                  "ONLY the verified specialist facts below, in the user's "
                  "language. Minimal reasoning. End with: '✓ تم التأكيد مع " +
                  skill + "/" + model_id + "'. If the facts hold an error, "
                  "honestly say what is missing. أجب باختصار من الحقائق فقط.")
        body = {"model": SPARK,
                "messages": [{"role": "system", "content": system},
                             {"role": "user",
                              "content": f"{user_text[:2000]}\n\n"
                                         f"[حقائق {skill}/{model_id}]\n"
                                         f"{facts[:4000]}"}],
                "max_tokens": 1000, "temperature": 0.3,
                "reasoning_effort": "none"}
        for attempt in range(2):
            try:
                r = httpx.post(f"{ollama_url.rstrip('/')}/v1/chat/completions",
                               json=body, timeout=300)
            except Exception as e:
                logger.warning("[ModelRouter] spark verify net fail: %s", e)
                continue
            if r.status_code != 200:
                logger.warning("[ModelRouter] spark verify HTTP %s",
                               r.status_code)
                continue
            msg = (r.json().get("choices") or [{}])[0].get("message", {}) or {}
            txt = (msg.get("content") or "").strip()
            if txt:
                return txt
            logger.warning("[ModelRouter] spark verify empty (trace %d chars, "
                           "attempt %d/2)",
                           len(str(msg.get("reasoning", "") or "")), attempt + 1)
        return ""
    except Exception as e:
        logger.warning("[ModelRouter] spark verify failed: %s", e)
        return ""


def run_section_turn(model_id: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Serve one chat turn on a specialist model id. Never raises."""
    import time as _time

    def _err(text: str) -> Dict[str, Any]:
        return {"id": "chat-section", "object": "chat.completion",
                "created": int(_time.time()), "model": model_id,
                "choices": [{"index": 0,
                             "message": {"role": "assistant", "content": text},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                          "total_tokens": 0},
                "status": "section_error", "error": text[:300]}

    def _ok(text: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": "chat-section", "object": "chat.completion",
                "created": int(_time.time()), "model": model_id,
                "choices": [{"index": 0,
                             "message": {"role": "assistant", "content": text},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                          "total_tokens": 0},
                "section_skill": meta}

    try:
        entry = next((e for e in CHAT_EXTRA if e[0] == model_id), None)
        if entry is None:
            return _err(f"نموذج غير مسجل في القائمة: {model_id}")
        via = entry[7]
        user_text = next((str(m.get("content", "")) for m in reversed(messages or [])
                          if m.get("role") == "user"), "")
        if via.startswith("pending:"):
            alt = via.split(":", 1)[1]
            return _ok(f"نموذج {model_id} عدّاؤه قيد التجهيز — البديل الجاهز الآن: "
                       f"{alt}. اختره من القائمة وسيعمل فوراً.",
                       {"model": model_id, "pending": True, "alternative": alt})
        if via == "tool:see_image":
            paths = _paths_from_text(user_text)
            if not paths:
                return _ok(f"نموذج {model_id} يرى الصور — أرفق مسار صورة في رسالتك "
                           f"(مثال: D:\\photo.png) وسأصفها فوراً.",
                           {"model": model_id, "need": "image_path"})
            from backend.agent import tools as _tools
            r = _tools._see_image_impl(paths[0], user_text[:500])
            txt = str((r.output or {}).get("description", r.error or ""))[:4000]
            return _ok(txt, {"model": model_id, "tool": "see_image"})
        if via.startswith("generate:"):
            from backend.agent import hf_runner
            r = hf_runner.run_pipe("text-generation", via.split(":", 1)[1],
                                   user_text[:2000], max_new_tokens=1024,
                                   do_sample=False)
            if not r.get("success"):
                return _err(f"تعذّر التوليد: {r.get('error', '')}")
            gen = r["output"]
            txt = (gen[0].get("generated_text", "") if isinstance(gen, list)
                   else str(gen))[-3000:]
            return _ok(txt, {"model": model_id, "via": "generate"})
        if via.startswith("skill:"):
            from backend.agent import skills as _skills
            fname = SKILL_FILES[via.split(":", 1)[1]]
            first = FIRST_PARAM.get(fname, "text")
            kw: Dict[str, Any] = {}
            paths = _paths_from_text(user_text)
            if first in ("image_path", "audio_path"):
                if not paths:
                    need = "صورة" if "image" in first else "صوت"
                    return _ok(f"نموذج {model_id} يحتاج ملف {need} — أرفق مساره "
                               f"في رسالتك وسأعمل فوراً.",
                               {"model": model_id, "need": first})
                kw[first] = paths[0]
            elif first == "idea":
                kw[first] = user_text
                kw["aspect"] = "1:1"
            elif first == "query":
                kw[first] = _strip_conventions(user_text)
                vs = _convention(user_text, "vs", "candidates")
                if vs:
                    kw["candidates"] = vs
            elif first == "text" and fname == "extract_skill":
                kw[first] = _strip_conventions(user_text)
                fl = _convention(user_text, "fields")
                if fl:
                    kw["fields"] = fl
            elif first == "smiles":
                kw[first] = (user_text.strip().split() or [""])[0]
            else:
                kw[first] = user_text
            kw["model"] = model_id  # skill picks its exact chain member
            res = _skills.run_skill(fname, **kw)
            meta = {"model": model_id, "skill": fname,
                    "section": _section_of(model_id)}
            _inner = (res.get("result") if isinstance(res.get("result"), dict)
                      else res)
            if isinstance(_inner, dict) and _inner.get("success") is False and any(
                    k in str(_inner.get("error", "")) for k in ("required",)):
                return _ok(f"نموذج {model_id} جاهز — ينقصه: {_inner.get('error')} "
                           f"أرسل المطلوب وسأعمل فوراً.", meta)
            # LEADER PHILOSOPHY 2026-10-14: spark answers, specialist confirms.
            facts = _format_skill_answer(model_id, fname, res or {})
            answered = _ask_spark_verify(user_text, facts, model_id, fname)
            if answered:
                meta["verified_by"] = f"{fname}/{model_id}"
                return _ok(answered, meta)
            meta["verified_by"] = f"{fname}/{model_id} (raw, spark busy)"
            return _ok(facts, meta)
        return _err(f"مسار غير معروف: {via}")
    except Exception as e:
        logger.warning("[ModelRouter] section turn failed: %s", e)
        return _err(f"عطل مؤقت في {model_id}: {type(e).__name__}")
