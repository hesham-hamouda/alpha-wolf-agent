#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Agent Page (self-awareness console)
=======================================================
The Wolf's mirror: who it is, its health, weaknesses, machine, skills, goals.

Sections (all live from backend):
- Self-Model (/v1/self/model): identity, tools, skills, servers
- Weaknesses (/v1/self/gaps): critical/warning/info with suggestions
- Machine (/v1/tools/execute system_status): CPU/RAM/disks/GPU/Ollama
- Skills: list + install from URL (skills.sh FIRST) + run with args
- Goals: open goals + mark done

Iron Laws: #15 verify (live data only), #41 conflict (errors shown),
#47 bilingual, #48 separated (page-only code).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

sys.path.insert(0, str(PROJECT_ROOT / "frontend"))
from utils import T, get_api_client, get_backend_status, truncate

logger = logging.getLogger("alpha_wolf_agent_page")


def render() -> None:
    api = get_api_client()
    is_online, _ = get_backend_status()

    st.markdown(
        """
        <div class="wolf-header-gradient">
            <h1>🐺 Agent | الوكيل — Self-Awareness Console</h1>
            <p>Who I am · my health · my weaknesses · my machine · my skills · my goals</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not is_online:
        st.error(f"⚠️ {T['error']}: Backend offline")
        return

    tab_model, tab_gaps, tab_machine, tab_skills, tab_goals = st.tabs([
        "🐺 Self-Model | النموذج الذاتي",
        "🔍 Weaknesses | نقاط الضعف",
        "🖥️ Machine | الجهاز",
        "🧬 Skills | المهارات",
        "🎯 Goals | الأهداف",
    ])

    with tab_model:
        _render_self_model(api)
    with tab_gaps:
        _render_gaps(api)
    with tab_machine:
        _render_machine(api)
    with tab_skills:
        _render_skills(api)
    with tab_goals:
        _render_goals(api)


def _render_self_model(api) -> None:
    model = api.self_model()
    if not model:
        st.error(f"{T['error']}: cannot load self-model")
        return
    st.markdown(f"### 🐺 {model.get('name', 'Alpha Wolf Agent')}")
    st.caption("Traits: " + ", ".join(model.get("traits", [])))
    caps = model.get("capabilities", {})
    tools = caps.get("tools", {})
    skills = caps.get("skills", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🛠️ Tools | الأدوات", tools.get("count", "?"))
    c2.metric("🧬 Skills | المهارات", skills.get("count", "?"))
    c3.metric("📂 Categories | الفئات", len(tools.get("categories", [])))
    inf = model.get("inference", {})
    backend_ok = "🟢" if (model.get("body_health") or {}).get("chromadb", {}).get("ok") else "🔴"
    c4.metric("Backend | الخادم", f"{backend_ok} {inf.get('model', '')[:18]}")

    with st.expander(f"🛠️ All tools ({tools.get('count', 0)}) | كل الأدوات", expanded=False):
        for name in tools.get("names", []):
            st.code(name, language="text")
    with st.expander(f"🧬 Skills ({skills.get('count', 0)}) | المهارات", expanded=False):
        for name in skills.get("names", []):
            st.code(name, language="text")
    with st.expander("🖥️ Servers | السيرفرات", expanded=False):
        st.json({
            "inference": inf,
            "weakness_scan": model.get("weakness_scan"),
            "body_browser": model.get("body_browser"),
        })


def _render_gaps(api) -> None:
    with st.spinner("Scanning weaknesses... | فحص نقاط الضعف..."):
        data = api.self_gaps()
    if not data:
        st.error(f"{T['error']}: gaps scan failed")
        return
    gaps = data.get("gaps", [])
    c1, c2 = st.columns(2)
    c1.metric("⚠️ Total | الإجمالي", data.get("count", len(gaps)))
    c2.metric("🔴 Critical | حرجة", data.get("criticals", 0))
    if not gaps:
        st.success("✅ No weaknesses found | لا نقاط ضعف")
        return
    sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    for g in gaps:
        icon = sev_icon.get(g.get("severity"), "⚪")
        with st.expander(f"{icon} **{g.get('id')}** · {g.get('area')}"):
            st.markdown(f"**Detail:** {g.get('detail')}")
            st.info(f"💡 Suggestion: {g.get('suggestion')}")


def _render_machine(api) -> None:
    with st.spinner("Reading machine... | قراءة الجهاز..."):
        s = api.system_status()
    if not s:
        st.error(f"{T['error']}: system status failed")
        return
    st.markdown(f"### 🕐 {s.get('local_time', '')} ({s.get('timezone', '')})")
    cpu = s.get("cpu", {}) or {}
    ram = s.get("ram", {}) or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("CPU %", cpu.get("percent", "?"))
    c2.metric("RAM %", ram.get("percent", "?"))
    c3.metric("Uptime (h)", s.get("uptime_hours", "?"))
    st.markdown("#### 💽 Disks | الأقراص")
    st.json(s.get("disks", {}))
    with st.expander("🎮 GPU | كرت الشاشة"):
        st.json(s.get("gpu", {}))
    with st.expander("🤖 Ollama | أولاما"):
        st.json(s.get("ollama", {}))
    for w in s.get("warnings", []):
        st.warning(f"⚠️ {w}")
    if not s.get("warnings"):
        st.success("✅ Machine healthy | الجهاز سليم")


def _render_skills(api) -> None:
    skills = api.list_skills()
    st.markdown(f"### 🧬 Installed skills: {len(skills)} | المهارات المثبتة")
    for sk in skills:
        name = sk.get("name", "?")
        with st.expander(f"🔧 **{name}** v{sk.get('version', '?')}"):
            st.caption(sk.get("description", ""))
            if sk.get("description_ar"):
                st.caption(sk.get("description_ar"))
            with st.form(key=f"run_skill_{name}"):
                args_text = st.text_area(
                    "Arguments (JSON) | المعاملات",
                    value="{}",
                    height=80,
                    key=f"skill_args_{name}",
                )
                if st.form_submit_button("▶️ Run | تشغيل", type="primary"):
                    try:
                        args = json.loads(args_text) if args_text.strip() else {}
                    except json.JSONDecodeError as exc:
                        st.error(f"Invalid JSON: {exc}")
                        return
                    with st.spinner(T["loading"]):
                        res = api.run_skill(name, args)
                    if res and res.get("success"):
                        st.success("✓ Done | تم")
                        st.json(res)
                    else:
                        st.error(f"✗ {(res or {}).get('error', 'failed')}")
    st.markdown("---")
    st.markdown("### ➕ Install skill | تثبيت مهارة")
    st.caption("skills.sh FIRST | ابحث أولاً في skills.sh — e.g. https://www.skills.sh/microsoft/playwright/playwright-cli")
    with st.form(key="install_skill_form"):
        url = st.text_input("Skill URL | رابط المهارة", placeholder="https://www.skills.sh/owner/repo/skill")
        name = st.text_input("Name override (optional) | الاسم (اختياري)", value="")
        if st.form_submit_button("⬇️ Install & adapt | تثبيت وتكييف", type="primary"):
            if not url.strip():
                st.error("URL required | الرابط مطلوب")
            else:
                with st.spinner("Fetching + adapting... | جلب وتكييف..."):
                    res = api.install_skill_from_url(url.strip(), name.strip())
                if res and res.get("success"):
                    st.success(f"✓ Installed: {(res.get('output') or {}).get('skill', name)}")
                    st.json(res.get("output", {}))
                    st.rerun()
                else:
                    st.error(f"✗ {(res or {}).get('error', 'failed')}")


def _render_goals(api) -> None:
    goals = api.list_goals(limit=50, status="open")
    st.markdown(f"### 🎯 Open goals: {len(goals)} | الأهداف المفتوحة")
    if not goals:
        st.info("No open goals | لا أهداف مفتوحة — the Wolf tracks long tasks here via track_goal")
        return
    for g in goals:
        gid = g.get("id", "?")
        title = truncate(g.get("title", "Untitled"), 60)
        prog = g.get("progress_pct", 0) or 0
        with st.expander(f"🎯 **{title}** · {prog}%"):
            st.caption(g.get("description", "") or "_no description_")
            st.caption(f"Priority: {g.get('priority', '?')} · Status: {g.get('status', '?')}")
            cols = st.columns([1, 1, 3])
            with cols[0]:
                if st.button("✅ Done | تم", key=f"goal_done_{gid}"):
                    if api.update_goal(gid, "done", 100.0):
                        st.success("✓ Closed | أُغلق")
                        st.rerun()
                    else:
                        st.error("✗ Failed | فشل")
            with cols[1]:
                if st.button("🚫 Blocked", key=f"goal_block_{gid}"):
                    if api.update_goal(gid, "blocked", prog):
                        st.warning("Marked blocked | عالق")
                        st.rerun()


if __name__ == "__main__":
    render()
