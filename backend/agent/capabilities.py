#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Capability Map | خريطة القدرات
==================================================
Single source of truth for what the Wolf IS and OWNS, generated LIVE from
the tool registry + skills registry (never a stale hardcoded list).

المصدر الوحيد الموثوق لقدرات الذئب — يُولَّد حياً من السجلات.

Injected into every system prompt (streaming + chat) so the model ALWAYS
knows its tools/servers/paths, and exposed as the `my_capabilities` tool
for explicit "what can you do?" questions (deterministic, complete).

Iron Laws: #15 verify (self-test), #47 bilingual, #33 lessons.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

BACKEND_PORT = int(os.environ.get("FASTAPI_PORT", "8001"))
FRONTEND_PORT = 8501
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def build_capability_map() -> str:
    """Build the live capability map (markdown, compact).

    بناء خريطة القدرات الحية (موجزة).
    """
    from backend.agent import tools as _tools

    lines = [
        "# WHO YOU ARE | من أنت",
        "You are Alpha Wolf Agent. 7 traits: mistake_hunter, goal_persistence, "
        "tenacity, deep_thinking, resourceful, self_aware, reinforcement_learning.",
        "",
        "# YOUR SERVERS | سيرفراتك",
        f"- Backend (YOU live here): http://127.0.0.1:{BACKEND_PORT} "
        "(/v1/chat, /v1/tools, /v1/skills, /v1/web, /v1/self, /v1/body, /v1/rag, /v1/jev)",
        f"- Frontend (user sees you here): http://127.0.0.1:{FRONTEND_PORT}/",
        # POLICY 2026-10-12 (القائد): local chain, originals only (training suspended,
        # v10 weights deleted). Inference = Ollama stock models on :11434.
        # Embeddings use EmbeddingGemma 2 via HF transformers (NOT Ollama — architecture mismatch).
        f"- Chat Inference (local Ollama {os.environ.get('LLAMACPP_MODEL', 'maternion/spark-x2.5:4b-q4_K_M')}): {OLLAMA_URL} — default brain for chat + Jev scoring",
        f"- Vision (local Ollama): moondream (light) / qwen2.5vl:7b (flagship) via {OLLAMA_URL}",
        f"- EmbeddingGemma 2 (multimodal embeddings, 768d): HuggingFace transformers — text + image + audio + video",
        "",
        "# YOUR PLACES | أماكنك",
    ]
    try:
        lines.append(f"- Body (knowledge/memory/skills — READ-ONLY for projects): {__import__('backend.agent.live_context', fromlist=['get_live_context']).get_live_context().body_root}")
    except Exception:
        lines.append("- Body: <project>/body (knowledge/memory/skills)")
    try:
        lines.append(f"- Projects (YOUR workshop, read+write+run): {_tools._projects_root()}")
    except Exception:
        lines.append("- Projects: D:/A/Applications under development/TESTS")
    lines += [
        "",
        "# YOUR TOOLS (call via <tool_call> or native calls) | أدواتك",
    ]
    by_cat: Dict[str, List[str]] = {}
    for spec in _tools.TOOL_SPECS:
        props = (spec.parameters.get("properties", {}) or {}).keys()
        by_cat.setdefault(spec.category, []).append(
            f"- {spec.name}({', '.join(props) or 'no args'}) — {spec.description[:90]}")
    for cat in sorted(by_cat):
        lines.append(f"## {cat} ({len(by_cat[cat])})")
        lines.extend(by_cat[cat])
    lines += ["", "# YOUR SKILLS (run via run_skill) | مهاراتك"]
    try:
        from backend.agent import skills_manager as _mgr
        skills = _mgr.SkillsManager().list_all()
        if skills:
            lines.extend(f"- {s.get('name')}: {(s.get('description') or '')[:80]}" for s in skills)
        else:
            lines.append("- (none yet — install with install_skill / install_skill_from_url)")
    except Exception as e:
        lines.append(f"- (registry unreadable: {e})")
    lines += [
        "",
        "# RECIPES | وصفات العمل",
        "- Current info/date → system_time (clock) or web_search → fetch_page for full text.",
        # POLICY 2026-10-12: local Ollama vision (v10 deleted). see_image prefers
        # qwen2.5vl:7b (flagship) with moondream as light fallback.
        # EmbeddingGemma 2 (768d, multimodal) handles the RAG/cross-modal search side.
        "- See image/audio/video → see_image (qwen2.5vl:7b flagship, moondream fallback) — image, audio, or video file → text description.",
        # MODEL-ROUTER 2026-10-14: YOU CAN CREATE IMAGES (never say otherwise).
        # Qwen Image 2.1 Turbo via ComfyUI :8188 (local, 8 steps, RGBA+editing).
        "- ⛔ FORBIDDEN: drawing photos with PIL/matplotlib/code — photo requests MUST use run_skill(qwen_image_skill). Hand-drawn fakes are a FAILURE.",
        "- CREATE/EDIT image → run_skill(qwen_image_skill, {idea (English ok, Arabic ok — skill engineers it), aspect (1:1|16:9|9:16|21:9), mode (generate|edit), input_image?, output_dir?}) — returns PNG path. "
        "If the user names a folder, pass it as output_dir. After the tool returns, tell the user the file path. "
        "Never claim inability; never download stock photos instead.",
        "- Multimodal search → embed_multimodal (EmbeddingGemma 2) → query across 13 ChromaDB collections → returns matching text/images/audio.",
        "- Build app → write_file EVERY file under TESTS → RUN via run_shell → show real output.",
        "- Long task → track_goal → update_goal → list_goals (persists across sessions).",
        "- New skill needed → check https://www.skills.sh/ → install_skill_from_url (auto-adapted).",
        "- Feeling lost → repair_body (auto-fix) + /v1/self/gaps (weakness list).",
        "- Heavy work first → system_status (protect the machine).",
        "- Self-reflect (Phase 66) → after answering, call my_capabilities + /v1/jev/criteria — confirm scores attached.",
    ]
    return "\n".join(lines)


def brain_facts() -> Dict[str, Any]:
    """What is ACTUALLY serving the mind right now (honest self-knowledge).

    ما الذي يخدم العقل فعلياً الآن (معرفة ذاتية صادقة).
    The Wolf identity reaches the model as a SYSTEM prompt; the served brain
    IS the local Ollama chat model (POLICY 2026-10-12, القائد: training
    suspended, originals only — v10 weights deleted, served via Ollama
    :11434, NOT the retired :8002 Transformers server). Reporting it keeps
    the agent from lying about itself (trait: self_aware).
    """
    _adapters_base = os.environ.get(
        "ALPHA_WOLF_ADAPTERS_BASE",
        "E:/Trained intelligence models/alpha-wolf/adapters",
    )
    # POLICY 2026-10-12 — local chain (was: v10 served brain, weights deleted):
    # served brain = stock Ollama model named by LLAMACPP_MODEL.
    _served = os.environ.get("LLAMACPP_MODEL", "maternion/spark-x2.5:4b-q4_K_M")
    _jev_scoring = os.environ.get("JEV_SCORING_MODEL", "qwen3:4b")
    out: Dict[str, Any] = {
        "served_model": _served,
        "served_via": f"Ollama on {OLLAMA_URL} (local originals — retired :8002 Transformers server deleted with v10 weights)",
        "base_model": "stock Ollama model (no local training served — TRAINING SUSPENDED 2026-10-12)",
        "adapter": "none served (trained LoRA adapters remain on disk, NOT loaded)",
        "quantization": "per-model Ollama quant (see live probe below)",
        "multimodal_native": False,  # chat model is text (+thinking); vision via separate Ollama vision models
        "vision_method": "Ollama vision models (qwen2.5vl:7b flagship, moondream light)",
        "adapter_served": False,
        "identity_source": "system_prompt (15 HARD RULES: 12 original + 3 Phase 66 multimodal/Jev/embedding) loaded from E:\\Trained intelligence models\\alpha-wolf\\models\\Wolf_Qwen3.5_Modelfile.txt",
        "trained_adapters_on_disk": [
            f"{_adapters_base}/v0_identity",
            f"{_adapters_base}/v2_tools_step500",
            f"{_adapters_base}/v4_code_step500",
            f"{_adapters_base}/v8_wolf",          # legacy Llama-3.1-8B (not served)
            f"{_adapters_base}/qwen_wolf_v10",   # weights deleted 2026-10-12 (NOT served)
        ],
        "embedding_brain": "EmbeddingGemma 2 (HF transformers, 768d, multimodal: text + image + audio + video)",
        "embedding_fallback_chain": [
            "embeddinggemma-2 (HF, multimodal, 768d)",
            "embeddinggemma (Ollama, 768d, text-only)",
            "nomic-embed-text (Ollama, 768d, text-only)",
        ],
        "jev_engine": {
            "scoring_model": f"{_jev_scoring} (local Ollama chain — v10 deleted 2026-10-12)",
            "criteria_count": 9,
            "criteria": ["urgency", "fraud_risk", "purchase_intent", "spam_score", "sentiment",
                         "budget_fit", "technical_compatibility", "security_implication", "git_operation_complexity"],
            "default_mode": "ADVISORY (scores attached to response, no blocking)",
            "hard_block_mode_env": "JEV_HARD_BLOCK=true (refusal if score < 30)",
        },
        "memory_layers": {
            "short_term": "in-memory LRU (10 conversations)",
            "long_term": f"ChromaDB at body/knowledge_graph/chromadb (13 collections: kb_code, kb_self, kb_tools, kb_mistakes, kb_vision, kb_goals, kb_reasoning, kb_science_*, alpha_wolf_project_index)",
            "episodic": "SQLite at body/memory/state.db (16 tables: episodes, mistakes, goals, projects, sessions, reflections, tools, entities, relations, ...)",
            "semantic": f"NetworkX knowledge graph at body/knowledge_graph/networkx (17 nodes, 7 edges)",
            "zvec": "zvec vector store at body/memory/embeddings/zvec",
        },
    }
    try:
        import json as _json
        import urllib.request as _u
        req = _u.Request(f"{OLLAMA_URL}/api/show",
                         data=_json.dumps({"name": out["served_model"]}).encode())
        with _u.urlopen(req, timeout=8) as _r:
            d = _json.loads(_r.read().decode())
        det = d.get("details", {}) or {}
        info = d.get("model_info", {}) or {}
        ctx_cfg = None
        for line in str(d.get("parameters", "")).splitlines():
            if line.strip().startswith("num_ctx"):
                try:
                    ctx_cfg = int(line.split()[-1])
                except ValueError:
                    pass
        native = next((v for k, v in info.items()
                       if k.endswith(".context_length")), None)
        out.update({
            "family": det.get("family"),
            "parameters": det.get("parameter_size"),
            "quantization": det.get("quantization_level"),
            "native_context_tokens": native,
            "served_context_tokens": ctx_cfg,
            "capabilities": d.get("capabilities", []),
            "is_thinking_model": "thinking" in (d.get("capabilities") or []),
        })
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


def self_test() -> bool:
    """Verify the map builds and names every registered tool."""
    print("Running capability-map self-test...")
    from backend.agent import tools as _tools
    m = build_capability_map()
    missing = [s.name for s in _tools.TOOL_SPECS if s.name not in m]
    has_servers = all(x in m for x in ("8001", "8501", "11434", "run_skill"))
    ok = not missing and has_servers and "RECIPES" in m
    print(f"  tools covered: {len(_tools.TOOL_SPECS) - len(missing)}/{len(_tools.TOOL_SPECS)}")
    brain = brain_facts()
    print(f"  served brain: {brain.get('served_model')} via {brain.get('served_via')}")
    print(f"  multimodal_native: {brain.get('multimodal_native')} | vision: {brain.get('vision_method')}")
    print(f"  adapter_served: {brain.get('adapter_served')}")
    print(f"  identity: {brain.get('identity_source')[:80]}...")
    # POLICY 2026-10-12: local chain honesty — served_model must be the
    # env-configured Ollama model (never the deleted v10 id).
    ok = ok and brain.get("served_model") not in (
        "alpha-wolf-qwen3.5-v10", "alpha-wolf-agent")
    ok = ok and brain.get("adapter_served") is False
    print("SELF-TEST:", "PASSED" if ok else f"FAILED missing={missing}")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
