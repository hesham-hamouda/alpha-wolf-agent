#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Memory Inspector Page
==========================================
Browse and interact with the 4 memory types:
- Episodes: episodic memories (importance, trigger, content)
- Goals: active + completed goals
- Mistakes: lessons from failures
- Reflections: introspective insights

Features:
- Tab-based UI for each memory type
- Filter by importance/severity/date
- Click to expand full content
- "Add to Memory" form for new entries

Iron Laws:
- #15 Verify: live data only
- #41 Conflict: clear messaging for backend offline
- #47 Bilingual: every label AR + EN
- #48 Separated: page-specific code only here
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

sys.path.insert(0, str(PROJECT_ROOT / "frontend"))
from utils import (
    T,
    get_api_client,
    get_backend_status,
    format_timestamp,
    truncate,
)

logger = logging.getLogger("alpha_wolf_memory_inspector_page")


def render() -> None:
    api = get_api_client()
    is_online, _ = get_backend_status()

    if not is_online:
        st.error(f"⚠️ {T['error']}: Backend offline")
        return

    # Header
    st.markdown(
        f"""
        <div class="wolf-header-gradient">
            <h1>🧠 {T['nav_memory']}</h1>
            <p>Browse Alpha Wolf's 4 memory types | تصفح أنواع الذاكرة الأربعة</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Tabs for each memory type
    tabs = st.tabs(
        [
            f"📝 {T['memory_episodes']}",
            f"🎯 {T['memory_goals']}",
            f"⚠️ {T['memory_mistakes']}",
            f"💡 {T['memory_reflections']}",
            f"➕ {T['add_to_memory']}",
        ]
    )

    with tabs[0]:
        _render_episodes(api)
    with tabs[1]:
        _render_goals(api)
    with tabs[2]:
        _render_mistakes(api)
    with tabs[3]:
        _render_reflections(api)
    with tabs[4]:
        _render_add_memory(api)


# ============================================================================
# Episodes
# ============================================================================


def _render_episodes(api) -> None:
    st.markdown(f"#### 📝 {T['memory_episodes']} | الحلقات")

    col1, col2 = st.columns(2)
    with col1:
        importance = st.slider(
            "Min Importance | الحد الأدنى للأهمية",
            min_value=1,
            max_value=10,
            value=3,
            key="ep_min_imp",
        )
    with col2:
        limit = st.number_input(
            "Limit | الحد",
            min_value=10,
            max_value=500,
            value=50,
            step=10,
            key="ep_limit",
        )

    if st.button(f"🔄 {T['refresh']}", key="ep_refresh"):
        st.rerun()

    episodes = api.list_episodes(limit=int(limit), min_importance=importance)
    st.caption(f"Found {len(episodes)} episodes | عدد الحلقات: {len(episodes)}")

    for ep in episodes[:50]:
        content = ep.get("content", "")
        ep_id = ep.get("id", "?")
        trigger = ep.get("trigger_type", "unknown")
        imp = ep.get("importance", 0)
        ts = ep.get("created_at", ep.get("ts"))

        with st.expander(
            f"[#{ep_id}] {T['episode_importance']}: {imp} | trigger: {trigger}"
        ):
            st.markdown(f"**{T['episode_content']}:**")
            st.markdown(content)
            if ts:
                st.caption(f"_{T['timestamp']}: {format_timestamp(ts)}_")


# ============================================================================
# Goals
# ============================================================================


def _render_goals(api) -> None:
    st.markdown(f"#### 🎯 {T['memory_goals']} | الأهداف")

    status = st.selectbox(
        "Status | الحالة",
        ["active", "open", "completed", "failed"],
        key="goals_status",
    )
    limit = st.number_input(
        "Limit | الحد",
        min_value=10,
        max_value=200,
        value=50,
        step=10,
        key="goals_limit",
    )

    if st.button(f"🔄 {T['refresh']}", key="goals_refresh"):
        st.rerun()

    goals = api.list_goals(limit=int(limit), status=status)
    st.caption(f"Found {len(goals)} {status} goals")

    for g in goals:
        gid = g.get("id", "?")
        title = g.get("title", "Untitled")
        desc = g.get("description", "")
        priority = g.get("priority", 5)
        progress = g.get("progress_pct", 0)
        ts = g.get("created_at", g.get("ts"))

        with st.expander(f"[#{gid}] {title} (priority {priority}, {progress}%)"):
            if desc:
                st.markdown(f"**Description:** {desc}")
            if ts:
                st.caption(f"_{format_timestamp(ts)}_")
            st.progress(min(max(progress / 100, 0), 1))


# ============================================================================
# Mistakes
# ============================================================================


def _render_mistakes(api) -> None:
    st.markdown(f"#### ⚠️ {T['memory_mistakes']} | الأخطاء والدروس")

    severity_min = st.slider(
        "Min Severity | الحد الأدنى للشدة",
        min_value=1,
        max_value=10,
        value=1,
        key="mistakes_sev",
    )
    limit = st.number_input(
        "Limit | الحد",
        min_value=10,
        max_value=200,
        value=50,
        step=10,
        key="mistakes_limit",
    )

    if st.button(f"🔄 {T['refresh']}", key="mistakes_refresh"):
        st.rerun()

    mistakes = api.list_mistakes(limit=int(limit), severity_min=severity_min)
    st.caption(f"Found {len(mistakes)} mistakes")

    for m in mistakes:
        mid = m.get("id", "?")
        severity = m.get("severity", 5)
        context = m.get("context", "")
        what_wrong = m.get("what_went_wrong", "")
        lesson = m.get("lesson", "")
        ts = m.get("created_at", m.get("ts"))

        # Severity emoji
        sev_emoji = "🔴" if severity >= 8 else "🟠" if severity >= 5 else "🟡"

        with st.expander(f"{sev_emoji} [#{mid}] Severity {severity} | {truncate(context, 60)}"):
            st.markdown(f"**Context | السياق:** {context}")
            st.markdown(f"**{T['what_went_wrong']}:** {what_wrong}")
            st.markdown(f"**{T['lesson']}:** {lesson}")
            if ts:
                st.caption(f"_{format_timestamp(ts)}_")


# ============================================================================
# Reflections
# ============================================================================


def _render_reflections(api) -> None:
    st.markdown(f"#### 💡 {T['memory_reflections']} | التأملات")

    # Iron Law #41: backend only supports POST (create), not GET (list)
    st.info(
        "ℹ️ **Backend limitation | قيد في الخادم**: "
        "Reflections endpoint only supports POST (create), not GET (list). "
        "Use the API directly to view existing reflections."
    )

    reflections = api.list_reflections()
    if reflections:
        st.caption(f"Found {len(reflections)} reflections")
        for r in reflections:
            rid = r.get("id", "?")
            trigger = r.get("trigger", "")
            insight = r.get("insight", "")
            confidence = r.get("confidence", 0)
            ts = r.get("created_at", r.get("ts"))

            with st.expander(
                f"[#{rid}] {T['confidence']}: {confidence:.2f} | {truncate(trigger, 50)}"
            ):
                st.markdown(f"**Insight | الفكرة:**")
                st.markdown(f"> {insight}")
                if ts:
                    st.caption(f"_{format_timestamp(ts)}_")
    else:
        st.caption("No reflections available via GET. Use POST to create.")


# ============================================================================
# Add Memory
# ============================================================================


def _render_add_memory(api) -> None:
    st.markdown(f"#### ➕ {T['add_to_memory']} | إضافة للذاكرة")

    # Use session state to persist form values across rerun
    content = st.text_area(
        f"{T['episode_content']} | المحتوى",
        height=150,
        key="add_ep_content",
        placeholder="What happened? What did you learn?",
    )

    col1, col2 = st.columns(2)
    with col1:
        trigger_type = st.selectbox(
            "Trigger Type | نوع المحفز",
            ["user_task", "user_question", "observation", "failure", "success", "system_event"],
            key="add_ep_trigger",
        )
    with col2:
        importance = st.slider(
            f"{T['episode_importance']} | الأهمية",
            min_value=1,
            max_value=10,
            value=5,
            key="add_ep_imp",
        )

    if st.button(f"💾 {T['save']}", type="primary", key="add_ep_save"):
        if not content.strip():
            st.error(f"{T['error']}: content cannot be empty")
        else:
            result = api.add_episode(content, trigger_type=trigger_type, importance=importance)
            if result:
                st.success(f"✓ Episode added successfully | تمت الإضافة بنجاح")
                # Clear the form
                st.session_state.add_ep_content = ""
            else:
                st.error(f"{T['error']}: failed to add episode")

    st.caption("💡 Tip: this writes to episodes table. Goals/Mistakes/Reflections have separate APIs.")
