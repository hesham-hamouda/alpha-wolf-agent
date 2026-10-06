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
        "(/v1/chat, /v1/tools, /v1/skills, /v1/web, /v1/self, /v1/body, /v1/rag)",
        f"- Frontend (user sees you here): http://127.0.0.1:{FRONTEND_PORT}/",
        f"- Inference (Ollama): {OLLAMA_URL} — chat model + nomic embeddings + moondream eyes",
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
        "- See image → see_image (moondream eyes, text comes back).",
        "- Build app → write_file EVERY file under TESTS → RUN via run_shell → show real output.",
        "- Long task → track_goal → update_goal → list_goals (persists across sessions).",
        "- New skill needed → check https://www.skills.sh/ → install_skill_from_url (auto-adapted).",
        "- Feeling lost → repair_body (auto-fix) + /v1/self/gaps (weakness list).",
        "- Heavy work first → system_status (protect the machine).",
    ]
    return "\n".join(lines)


def brain_facts() -> Dict[str, Any]:
    """What is ACTUALLY serving the mind right now (honest self-knowledge).

    ما الذي يخدم العقل فعلياً الآن (معرفة ذاتية صادقة).
    The Wolf identity reaches the model as a SYSTEM prompt; the trained
    v8_wolf LoRA (Llama-3.1-8B) is NOT the served brain. Reporting it keeps
    the agent from lying about itself (trait: self_aware).
    """
    _adapters_base = os.environ.get(
        "ALPHA_WOLF_ADAPTERS_BASE",
        "E:/Trained intelligence models/alpha-wolf/adapters",
    )
    out: Dict[str, Any] = {
        "served_model": os.environ.get("LLAMACPP_MODEL", "alpha-wolf-agent-v8"),  # FIX 2026-10-06: original broken
        "adapter_served": False,
        "identity_source": "system_prompt (7 Wolf traits) + RAG self-knowledge",
        "trained_adapters_on_disk": [
            f"{_adapters_base}/v0_identity",
            f"{_adapters_base}/v2_tools_step500",
            f"{_adapters_base}/v4_code_step500",
            f"{_adapters_base}/v8_wolf",
        ],
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
    has_servers = all(x in m for x in ("8001", "8501", "TESTS", "run_skill"))
    ok = not missing and has_servers and "RECIPES" in m
    print(f"  tools covered: {len(_tools.TOOL_SPECS) - len(missing)}/{len(_tools.TOOL_SPECS)}")
    brain = brain_facts()
    print(f"  brain: {brain.get('family')} {brain.get('parameters')} "
          f"{brain.get('quantization')} | ctx {brain.get('served_context_tokens')}"
          f"/{brain.get('native_context_tokens')} | adapter_served="
          f"{brain.get('adapter_served')}")
    ok = ok and brain.get("adapter_served") is False and bool(brain.get("family"))
    print("SELF-TEST:", "PASSED" if ok else f"FAILED missing={missing}")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
