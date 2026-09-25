#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Main App (Modern ChatGPT-like UI)
=====================================================
Streamlit entry point. Bilingual (AR + EN), ChatGPT-style sidebar + chat.

Run:
    cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
    python frontend/run_streamlit.py

URL: http://127.0.0.1:8501/

Iron Laws Applied:
- #22 (Autonomous) — no questions asked
- #47 (Bilingual) — every label is AR + EN
- #48 (Separated Concerns) — UI here, helpers in utils.py, pages in views/
- #33 (Lessons) — inline tooltips for first-time users
- #41 (Conflict) — backend offline fallback documented in UI
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from streamlit.components.v1 import html

# Local utils
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (
    T,
    WOLF_TRAITS,
    SCREENSHOTS_DIR,
    init_session_state,
    get_session,
    set_session,
    get_api_client,
    get_backend_status,
    format_timestamp,
    truncate,
)

logger = logging.getLogger("alpha_wolf_app")

# ============================================================================
# Page config + global CSS
# ============================================================================

st.set_page_config(
    page_title=f"{T['wolf_emoji']} {T['app_name']}",
    page_icon=str(T["wolf_emoji"]),
    layout="centered",
    initial_sidebar_state="expanded",
    menu_items=None,
)

# Inject custom CSS
CSS_PATH = Path(__file__).resolve().parent / "styles.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


# ============================================================================
# Session state init
# ============================================================================

def init_all_session_state() -> None:
    """Initialize all session state variables in one place."""
    init_session_state("active_conversation_id", None)
    init_session_state("messages", [])                # list of {role, content, tool_calls, ts}
    init_session_state("streaming_active", False)
    init_session_state("pending_user_input", "")
    init_session_state("page", "Chat")                 # default landing page
    init_session_state("pending_prompt", None)        # used to forward prompt from welcome buttons
    init_session_state("model", "alpha-wolf-agent")
    init_session_state("temperature", 0.7)


# ============================================================================
# UI Components
# ============================================================================


def render_topbar() -> None:
    """Sticky top bar with logo + backend status + wolf traits."""
    api = get_api_client()
    is_online, status_label = get_backend_status()
    dot_class = "wolf-status-dot-online" if is_online else "wolf-status-dot-offline"
    dot_status = "🟢" if is_online else "🔴"

    # Wolf traits bar (7 dots)
    traits_html = "".join(
        f'<span class="wolf-trait-chip" title="{T[name]}">{emoji}</span>'
        for name, emoji in WOLF_TRAITS
    )

    html(
        f"""
        <div class="wolf-topbar">
            <div class="wolf-topbar-logo">
                <span style="font-size: 1.6rem;">{T['wolf_emoji']}</span>
                <div>
                    <div>{T['app_name']}</div>
                    <div style="font-size: 0.78rem; color: var(--wolf-text-muted); font-weight: 400;">
                        {T['app_subtitle']}
                    </div>
                </div>
            </div>
            <div class="wolf-traits-bar">
                {traits_html}
            </div>
            <div class="wolf-topbar-status" title="{status_label}">
                <span class="wolf-status-dot {dot_class}"></span>
                <span>{dot_status} {status_label}</span>
            </div>
        </div>
        """,
        height=70,
    )


def render_welcome() -> None:
    """Welcome screen when no conversation is active."""
    st.markdown(
        f"""
        <div class="wolf-header-gradient">
            <h1>{T['wolf_emoji']} {T['app_name']}</h1>
            <p>{T['app_tagline']} · {T['app_tagline_ar']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    api = get_api_client()
    health = api.body_health() if api.health_check() else None

    if health:
        cols = st.columns(4)
        with cols[0]:
            st.markdown(
                f"""
                <div class="wolf-metric-card">
                    <div class="wolf-metric-value">{health['chromadb']['collections']}</div>
                    <div class="wolf-metric-label">{T['chromadb_collections']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                f"""
                <div class="wolf-metric-card">
                    <div class="wolf-metric-value">{health['networkx']['nodes']}</div>
                    <div class="wolf-metric-label">{T['networkx_nodes']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(
                f"""
                <div class="wolf-metric-card">
                    <div class="wolf-metric-value">{health['networkx']['edges']}</div>
                    <div class="wolf-metric-label">{T['networkx_edges']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cols[3]:
            st.markdown(
                f"""
                <div class="wolf-metric-card">
                    <div class="wolf-metric-value">{len(health['sqlite']['tables'])}</div>
                    <div class="wolf-metric-label">{T['sqlite_tables']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Quick action cards
    st.markdown(f"### {T['wolf_emoji']} {T['trait_self_aware']} · 7 Traits")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"🔍 {T['trait_mistake_hunter']}", use_container_width=True):
            set_session("pending_prompt", "Show me your most recent mistakes and what you learned from them.")
            st.rerun()
    with col2:
        if st.button(f"🎯 {T['trait_goal_persistence']}", use_container_width=True):
            set_session("pending_prompt", "What are your active goals right now?")
            st.rerun()
    with col3:
        if st.button(f"🧠 {T['trait_deep_thinking']}", use_container_width=True):
            set_session("pending_prompt", "Reflect on the most important lesson you've learned recently.")
            st.rerun()

    st.markdown(
        f"""
        <div class="wolf-empty-state">
            <div class="wolf-empty-state-icon">{T['wolf_emoji']}</div>
            <div class="wolf-empty-state-text">
                {T['chat_placeholder']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# Sidebar
# ============================================================================


def render_sidebar() -> None:
    """Sidebar with conversation list + page navigation."""
    with st.sidebar:
        st.markdown(f"### {T['wolf_emoji']} {T['app_name']}")

        # New chat button (prominent)
        if st.button(
            f"➕ {T['new_chat']}",
            use_container_width=True,
            type="primary",
            help=T["new_chat"],
        ):
            _create_new_conversation()

        st.markdown(f"#### {T['conversations']}")
        _render_conversation_list()

        st.markdown("---")
        st.markdown(f"#### {T['nav_settings']}")

        # Settings (compact)
        with st.expander(f"⚙️ {T['nav_settings']}", expanded=False):
            st.session_state.model = st.text_input(
                T["model_label"],
                value=get_session("model", "alpha-wolf-agent"),
            )
            st.session_state.temperature = st.slider(
                "Temperature | الحرارة",
                min_value=0.0,
                max_value=1.5,
                value=get_session("temperature", 0.7),
                step=0.05,
            )

        st.markdown("---")
        # Status footer
        is_online, _ = get_backend_status()
        dot = "🟢" if is_online else "🔴"
        st.caption(f"{dot} {T['backend_status']}: {T['backend_connected'] if is_online else T['backend_offline']}")


def _create_new_conversation() -> None:
    """Create a new conversation via backend and switch to it."""
    api = get_api_client()
    conv = api.create_conversation()
    if conv and "conversation_id" in conv:
        set_session("active_conversation_id", conv["conversation_id"])
        set_session("messages", [])
        st.success(f"✓ New conversation: {truncate(conv.get('title', ''), 40)}")
        st.rerun()
    else:
        st.error(f"{T['error']}: could not create conversation (backend offline?)")


def _render_conversation_list() -> None:
    """Render the conversation list in the sidebar."""
    api = get_api_client()
    conversations = api.list_conversations(limit=50)
    active_id = get_session("active_conversation_id")

    if not conversations:
        st.caption(T["no_conversations"])
        return

    for conv in conversations[:30]:  # cap at 30 for performance
        cid = conv.get("conversation_id")
        title = truncate(conv.get("title", "Untitled"), 35)
        is_active = cid == active_id
        marker = "●" if is_active else "○"
        cols = st.columns([0.15, 0.75, 0.10])
        with cols[0]:
            st.write(marker)
        with cols[1]:
            if st.button(
                title,
                key=f"conv_{cid}",
                use_container_width=True,
                disabled=is_active,
                help=f"Last activity: {format_timestamp(conv.get('last_activity_at'))}",
            ):
                _load_conversation(cid)
        with cols[2]:
            if st.button("🗑", key=f"del_{cid}", help=T["delete_chat"]):
                if api.delete_conversation(cid):
                    if cid == active_id:
                        set_session("active_conversation_id", None)
                        set_session("messages", [])
                    st.rerun()


def _load_conversation(conversation_id: str) -> None:
    """Load a conversation's history into the session."""
    api = get_api_client()
    conv = api.get_conversation(conversation_id)
    if conv and "messages" in conv:
        msgs = conv["messages"]
        # Strip system messages from UI display
        ui_msgs = [
            {"role": m["role"], "content": m["content"], "ts": m.get("created_at")}
            for m in msgs
            if m.get("role") in ("user", "assistant")
        ]
        set_session("messages", ui_msgs)
        set_session("active_conversation_id", conversation_id)
        st.rerun()
    else:
        st.error(f"{T['error']}: could not load conversation")


# ============================================================================
# Page routing
# ============================================================================


def route_page() -> None:
    """Route to the selected page (uses session_state.page)."""
    page = get_session("page", "Chat")

    if page == "Chat":
        _render_chat_page()
    elif page == "Body Health":
        _render_body_health_page()
    elif page == "Memory Inspector":
        _render_memory_inspector_page()
    elif page == "Tools Registry":
        _render_tools_registry_page()
    elif page == "Project Awareness":
        _render_project_awareness_page()


# ============================================================================
# Chat page (delegated to views/chat.py)
# ============================================================================


def _render_chat_page() -> None:
    """Render the main chat page. Delegates to views/chat.py logic."""
    try:
        # Lazy import to avoid circular dependencies
        from views import chat
        chat.render()
    except ImportError as exc:
        # Fallback to inline implementation if views/chat.py is unavailable
        logger.warning("views/chat.py not available, using inline fallback: %s", exc)
        _render_chat_page_inline()


def _render_chat_page_inline() -> None:
    """Inline fallback chat implementation if views/chat.py is missing."""
    api = get_api_client()
    messages = get_session("messages", [])

    # Welcome screen if no messages and no conversation
    if not messages and not get_session("active_conversation_id"):
        render_welcome()

    # Render message history
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        ts = msg.get("ts")
        if role == "user":
            with st.chat_message("user", avatar="🙋"):
                st.markdown(content)
                if ts:
                    st.caption(f"_{format_timestamp(ts)}_")
        elif role == "assistant":
            with st.chat_message("assistant", avatar=T["wolf_emoji"]):
                _render_message_content(content)
                if ts:
                    st.caption(f"_{format_timestamp(ts)}_")
        elif role == "tool":
            _render_tool_call(msg)

    # Chat input
    pending_prompt = get_session("pending_prompt")
    if pending_prompt:
        set_session("pending_prompt", None)
        _send_user_message(pending_prompt)

    user_input = st.chat_input(
        T["chat_placeholder"],
        key=f"chat_input_{len(messages)}",
    )
    if user_input:
        _send_user_message(user_input)


def _render_message_content(content: str) -> None:
    """Render message content with markdown + code highlighting."""
    from utils import split_text_by_code

    segments = split_text_by_code(content)
    for seg in segments:
        if seg["type"] == "text":
            if seg["content"].strip():
                st.markdown(seg["content"])
        elif seg["type"] == "code":
            lang = seg.get("lang", "text")
            with st.container():
                st.markdown(
                    f'<div class="wolf-code-block-header">{lang} <span>copy</span></div>',
                    unsafe_allow_html=True,
                )
                st.code(seg["content"], language=lang if lang != "text" else None)


def _render_tool_call(msg: dict) -> None:
    """Render a tool call inline."""
    name = msg.get("name", "unknown")
    args = msg.get("arguments", {})
    result = msg.get("result")
    duration = msg.get("duration_ms")

    st.markdown(
        f"""
        <div class="wolf-tool-call">
            <div class="wolf-tool-call-header">🔧 {T['tool_calling']}: <code>{name}</code></div>
            <div class="wolf-tool-call-input">{args}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result is not None:
        ok = result.get("success", True) if isinstance(result, dict) else True
        cls = "wolf-tool-result" if ok else "wolf-tool-result wolf-tool-result-error"
        st.markdown(
            f'<div class="{cls}">{T["tool_result"]}: {result}</div>',
            unsafe_allow_html=True,
        )

    if duration is not None:
        st.caption(f"⏱ {T['tool_duration']}: {duration}ms")


def _send_user_message(prompt: str) -> None:
    """Send a user message: persist + stream assistant response."""
    api = get_api_client()

    # Ensure we have an active conversation
    conv_id = get_session("active_conversation_id")
    if not conv_id:
        conv = api.create_conversation(title=truncate(prompt, 50))
        if conv and "conversation_id" in conv:
            conv_id = conv["conversation_id"]
            set_session("active_conversation_id", conv_id)
        else:
            st.error(f"{T['error']}: cannot create conversation")
            return

    # Append user message to UI
    messages = get_session("messages", [])
    messages.append({"role": "user", "content": prompt})
    set_session("messages", messages)

    # Persist user message
    api.add_message(conv_id, "user", prompt, importance=5)

    # Stream assistant response
    _stream_assistant_response(api, conv_id, messages)


def _stream_assistant_response(api, conv_id: str, messages: list[dict]) -> None:
    """Stream the assistant response and render progressively."""
    with st.chat_message("assistant", avatar=T["wolf_emoji"]):
        placeholder = st.empty()
        accumulated = ""
        tool_calls_meta = []
        error_occurred = False

        # Send API request
        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        try:
            for event in api.stream_chat(
                api_messages,
                conversation_id=conv_id,
                auto_tools=True,
            ):
                ev_type = event.get("type", "message")

                if ev_type == "token":
                    accumulated += event.get("chunk", "")
                    # Re-render with markdown + code split
                    with placeholder.container():
                        _render_message_content(accumulated)
                elif ev_type == "tool_call":
                    tool_calls_meta.append(
                        {
                            "name": event.get("name"),
                            "arguments": event.get("arguments"),
                            "ts": format_timestamp(None),
                        }
                    )
                    accumulated += f"\n\n🔧 **{T['tool_calling']}: `{event.get('name')}`**\n"
                    with placeholder.container():
                        _render_message_content(accumulated)
                elif ev_type == "tool_result":
                    tool_calls_meta.append(
                        {
                            "name": event.get("name"),
                            "result": event.get("output"),
                            "ts": format_timestamp(None),
                        }
                    )
                    accumulated += f"\n✅ **Result**: {event.get('output', {})}\n"
                    with placeholder.container():
                        _render_message_content(accumulated)
                elif ev_type == "error":
                    error_occurred = True
                    accumulated += f"\n\n⚠️ {event.get('message', 'Error')}"
                    with placeholder.container():
                        _render_message_content(accumulated)
                    break
                elif ev_type == "done":
                    break
        except Exception as exc:
            error_occurred = True
            accumulated += f"\n\n⚠️ {T['error']}: {exc}"
            with placeholder.container():
                _render_message_content(accumulated)

        if not accumulated:
            accumulated = f"⚠️ {T['error']}: empty response from backend"
            with placeholder.container():
                _render_message_content(accumulated)

        # Persist assistant message
        api.add_message(conv_id, "assistant", accumulated, importance=5)

    # Update session messages
    messages.append({"role": "assistant", "content": accumulated})
    set_session("messages", messages)
    st.rerun()


# ============================================================================
# Body Health page (delegated)
# ============================================================================


def _render_body_health_page() -> None:
    try:
        from views import body_health
        body_health.render()
    except ImportError as exc:
        logger.warning("views/body_health.py not available: %s", exc)
        st.error(f"{T['error']}: body_health page not found")


# ============================================================================
# Memory Inspector page (delegated)
# ============================================================================


def _render_memory_inspector_page() -> None:
    try:
        from views import memory_inspector
        memory_inspector.render()
    except ImportError as exc:
        logger.warning("views/memory_inspector.py not available: %s", exc)
        st.error(f"{T['error']}: memory_inspector page not found")


# ============================================================================
# Tools Registry page (delegated)
# ============================================================================


def _render_tools_registry_page() -> None:
    try:
        from views import tools_registry
        tools_registry.render()
    except ImportError as exc:
        logger.warning("views/tools_registry.py not available: %s", exc)
        st.error(f"{T['error']}: tools_registry page not found")


# ============================================================================
# Project Awareness page (delegated)
# ============================================================================


def _render_project_awareness_page() -> None:
    try:
        from views import project_awareness
        project_awareness.render()
    except ImportError as exc:
        logger.warning("views/project_awareness.py not available: %s", exc)
        st.error(f"{T['error']}: project_awareness page not found")


# ============================================================================
# Page selector (in sidebar)
# ============================================================================


def render_page_selector() -> None:
    """Render the page selector in the sidebar."""
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"### 🧭 {T['nav_settings'].split(' | ')[0]} Navigation")

        page_options = [
            ("Chat", f"💬 {T['nav_chat']}"),
            ("Body Health", f"📊 {T['nav_health']}"),
            ("Memory Inspector", f"🧠 {T['nav_memory']}"),
            ("Tools Registry", f"🛠️ {T['nav_tools']}"),
            ("Project Awareness", f"📁 {T['nav_project']}"),
        ]
        labels = [opt[1] for opt in page_options]
        current = get_session("page", "Chat")
        try:
            idx = next(i for i, opt in enumerate(page_options) if opt[0] == current)
        except StopIteration:
            idx = 0

        new_page = st.radio(
            "Go to | اذهب إلى",
            labels,
            index=idx,
            label_visibility="collapsed",
            key="page_selector_radio",
        )
        # Map back to page name
        for opt_name, opt_label in page_options:
            if opt_label == new_page:
                if opt_name != current:
                    set_session("page", opt_name)
                    st.rerun()
                break


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    init_all_session_state()
    render_topbar()
    render_sidebar()
    render_page_selector()
    route_page()


if __name__ == "__main__":
    main()
