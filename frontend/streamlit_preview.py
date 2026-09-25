#!/usr/bin/env python3
r"""
Alpha Wolf Agent — ChatGPT Desktop Style Frontend (Bilingual AR+EN)
====================================================================

A professional, ChatGPT-desktop-style web UI for Alpha Wolf Agent.
Built with Streamlit + heavy CSS customization.

Features:
- ChatGPT-style 3-column layout: sidebar (collapsible), main chat, optional right panel
- Bilingual (AR + EN) per Iron Law #47
- Streaming responses via SSE (Iron Law #33)
- Markdown rendering + code syntax highlighting
- Conversation history (Today / Yesterday / Previous 7 days)
- 7 Wolf traits integration + quick start cards
- Dark theme with Wolf Gold accents (#FFD700)
- Tool call collapsible display
- Settings panel (model, temperature, theme toggle)
- Export conversation (JSON / Markdown)
- Auto-title generation from first message

Run:
    cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
    python frontend/run_streamlit.py

URL: http://127.0.0.1:8501/

Iron Laws Applied:
- #15 (Verify) — backend reachability checks
- #22 (Autonomous) — no questions asked
- #33 (Lessons -> Code) — clean modular architecture
- #41 (Conflict Disclosure) — backend offline fallback, limitations documented
- #47 (Bilingual) — every label is AR + EN
- #48 (Separated) — each component in its own function/class
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Project setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from streamlit.components.v1 import html

# Local utils (sibling file)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (
    T,
    WOLF_TRAITS,
    SCREENSHOTS_DIR,
    BACKEND_URL,
    APIClient,
    APIError,
    init_session_state,
    get_session,
    set_session,
    get_api_client,
    get_backend_status,
    format_timestamp,
    truncate,
    group_conversations_by_date,
    auto_generate_title,
    split_text_by_code,
    export_chat_as_markdown,
    export_chat_as_json,
)

logger = logging.getLogger("alpha_wolf_chatgpt_ui")

# ============================================================================
# Inline CSS (Iron Law #41 — Conflict Disclosure: iframes need inline styles)
# ============================================================================
# Streamlit's st.components.v1.safe_html() creates sandboxed iframes. CSS injected
# via st.markdown(<style>) only applies to the parent document. To make
# custom styling reach iframe content, we inline the critical rules here.

INLINE_BASE_STYLES = """
<style>
.wolf-topbar {
    position: fixed;
    top: 0;
    left: 260px;
    right: 0;
    height: 56px;
    background-color: #212121;
    border-bottom: 1px solid #2E2E2E;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    z-index: 999;
    color: #ECECEC;
    font-family: "Inter", system-ui, sans-serif;
}
.wolf-topbar-left, .wolf-topbar-right {
    display: flex;
    align-items: center;
    gap: 12px;
}
.wolf-topbar-model {
    background-color: transparent;
    color: #ECECEC;
    border: 1px solid #2E2E2E;
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 14px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
}
.wolf-traits-bar {
    display: flex;
    gap: 4px;
    align-items: center;
    flex-wrap: wrap;
}
.wolf-trait-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 9999px;
    background: linear-gradient(135deg, #FFD700, #FFA500);
    color: #1A1A1A;
    font-size: 13px;
}
.wolf-topbar-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #B4B4B4;
}
.wolf-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 9999px;
    display: inline-block;
}
.wolf-status-dot-online {
    background: #10A37F;
    box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.15);
}
.wolf-status-dot-offline {
    background: #EF4444;
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
}
.wolf-welcome {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px 80px;
    text-align: center;
    color: #ECECEC;
    font-family: "Inter", system-ui, sans-serif;
}
.wolf-welcome-logo {
    font-size: 56px;
    margin-bottom: 16px;
    filter: drop-shadow(0 0 24px rgba(255, 215, 0, 0.15));
}
.wolf-welcome-title {
    font-size: 32px;
    font-weight: 700;
    color: #FFD700;
    margin: 0 0 8px 0;
    background: linear-gradient(135deg, #FFD700, #FFA500);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.wolf-welcome-subtitle {
    font-size: 16px;
    color: #B4B4B4;
    margin: 0 0 8px 0;
}
.wolf-welcome-subtitle-ar {
    font-size: 15px;
    color: #8E8E8E;
    margin: 0 0 40px 0;
}
.wolf-quickstart-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 32px;
    width: 100%;
    max-width: 600px;
}
.wolf-quickstart-card {
    background-color: #2F2F2F;
    border: 1px solid #2E2E2E;
    border-radius: 10px;
    padding: 16px;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: #ECECEC;
}
.wolf-quickstart-card-icon {
    font-size: 22px;
    margin-bottom: 4px;
}
.wolf-quickstart-card-title {
    font-size: 14px;
    font-weight: 600;
    color: #ECECEC;
}
.wolf-quickstart-card-desc {
    font-size: 12px;
    color: #B4B4B4;
    line-height: 1.4;
}
.wolf-conv-item {
    padding: 8px 10px;
    border-radius: 6px;
    cursor: pointer;
    color: #ECECEC;
    font-size: 13px;
}
.wolf-conv-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.wolf-conv-active {
    background-color: #2F2F2F;
}
.wolf-sidebar-user {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 10px;
    color: #ECECEC;
}
.wolf-user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 9999px;
    background: linear-gradient(135deg, #FFD700, #FFA500);
    color: #1A1A1A;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
}
.wolf-metric-card {
    background-color: #2F2F2F;
    border: 1px solid #2E2E2E;
    border-radius: 10px;
    padding: 14px;
    text-align: center;
    color: #ECECEC;
}
.wolf-metric-icon { font-size: 24px; }
.wolf-metric-value {
    font-size: 24px;
    font-weight: 700;
    color: #FFD700;
}
.wolf-metric-label {
    font-size: 12px;
    color: #B4B4B4;
    margin-top: 4px;
}
.wolf-thinking {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 0;
    color: #B4B4B4;
    font-style: italic;
}
.wolf-thinking-dots { display: flex; gap: 4px; }
.wolf-thinking-dot {
    width: 6px;
    height: 6px;
    border-radius: 9999px;
    background-color: #FFD700;
    animation: wtpulse 1.4s infinite ease-in-out;
}
.wolf-thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.wolf-thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes wtpulse {
    0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
    30% { opacity: 1; transform: scale(1.2); }
}
.wolf-info, .wolf-error {
    padding: 12px 16px;
    border-radius: 10px;
    margin: 12px 0;
    color: #ECECEC;
}
.wolf-info {
    background-color: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.25);
    color: #93C5FD;
}
.wolf-tool-call {
    margin: 12px 0;
    border-radius: 10px;
    border: 1px solid #2E2E2E;
    background-color: rgba(255, 215, 0, 0.04);
    overflow: hidden;
}
.wolf-tool-call-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    color: #FFD700;
    font-size: 13px;
    font-weight: 500;
}
.wolf-tool-call-name {
    font-family: "JetBrains Mono", monospace;
    color: #FFD700;
}
.wolf-tool-call-body {
    padding: 12px;
    border-top: 1px solid #2E2E2E;
    background-color: #1A1A1A;
    font-family: "JetBrains Mono", monospace;
    font-size: 12px;
    color: #ECECEC;
}
.wolf-tool-call-section { margin-bottom: 8px; }
.wolf-tool-call-section-label {
    color: #8E8E8E;
    font-size: 10px;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.wolf-tool-call-section-content {
    color: #ECECEC;
    white-space: pre-wrap;
    word-break: break-word;
}
.wolf-tool-result-ok { color: #10A37F; }
.wolf-tool-result-err { color: #EF4444; }
.wolf-code-block-wrapper {
    margin: 12px 0;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #2E2E2E;
    background-color: #1A1A1A;
}
.wolf-code-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 12px;
    background-color: #252525;
    color: #8E8E8E;
    font-family: "JetBrains Mono", monospace;
    font-size: 11px;
}
.wolf-code-block-wrapper pre {
    margin: 0;
    padding: 12px 16px;
    background-color: #1A1A1A;
    color: #ECECEC;
    overflow-x: auto;
    font-family: "JetBrains Mono", monospace;
    font-size: 13px;
}
.wolf-anim-fade-in { animation: wfi 0.3s ease; }
@keyframes wfi { from { opacity: 0; } to { opacity: 1; } }
.wolf-anim-slide-in { animation: wsi 0.25s ease; }
@keyframes wsi { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: translateX(0); } }
</style>
"""

def safe_html(content: str, height: int = None) -> str:
    """Render HTML with inline styles for iframe compatibility."""
    full = INLINE_BASE_STYLES + content
    if height:
        html(full, height=height)
    else:
        html(full)


# ============================================================================
# Page Config + Global CSS
# ============================================================================

st.set_page_config(
    page_title=f"{T['wolf_emoji']} {T['app_name']}",
    page_icon=str(T["wolf_emoji"]),
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None,
)

# Inject custom CSS
CSS_PATH = Path(__file__).resolve().parent / "styles.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


# ============================================================================
# Session State Init (Iron Law #48 — Separated)
# ============================================================================


def init_all_session_state() -> None:
    """Initialize all session state variables in one place."""
    init_session_state("active_conversation_id", None)
    init_session_state("messages", [])                # list of {role, content, tool_calls, ts}
    init_session_state("streaming_active", False)
    init_session_state("page", "Chat")                 # default landing page
    init_session_state("pending_prompt", None)        # forward prompt from welcome buttons
    init_session_state("model", "alpha-wolf-agent")
    init_session_state("temperature", 0.7)
    init_session_state("theme", "dark")                # dark/light
    init_session_state("conversations_cache", None)    # cache list to avoid refetch
    init_session_state("conversations_cache_ts", 0)
    init_session_state("search_query", "")             # sidebar search
    init_session_state("settings_open", False)         # settings panel state


# ============================================================================
# TOP BAR (Sticky header — ChatGPT-style)
# ============================================================================


def render_topbar() -> None:
    """Sticky top bar with model selector + actions."""
    is_online, status_label = get_backend_status()
    dot_class = "wolf-status-dot-online" if is_online else "wolf-status-dot-offline"
    dot_status = "\U0001F7E2" if is_online else "\U0001F534"

    # Wolf traits bar (7 dots)
    traits_html = "".join(
        f'<span class="wolf-trait-chip" title="{T[name]}">{emoji}</span>'
        for name, emoji in WOLF_TRAITS
    )

    model = get_session("model", "alpha-wolf-agent")
    conv_id = get_session("active_conversation_id")
    has_messages = bool(get_session("messages", []))

    safe_html(
        f"""
        <div class="wolf-topbar">
            <div class="wolf-topbar-left">
                <div class="wolf-topbar-model" title="{T['model_label']}: {model}">
                    <span class="wolf-topbar-model-icon">{T['wolf_emoji']}</span>
                    <span>{model}</span>
                </div>
                <div class="wolf-traits-bar">{traits_html}</div>
            </div>
            <div class="wolf-topbar-right">
                <div class="wolf-topbar-status" title="{status_label}">
                    <span class="wolf-status-dot {dot_class}"></span>
                    <span>{dot_status} {status_label}</span>
                </div>
            </div>
        </div>
        """,
        height=56,
    )


# ============================================================================
# WELCOME SCREEN (Centered hero — ChatGPT-style)
# ============================================================================


def render_welcome() -> None:
    """Welcome screen when no conversation is active. ChatGPT-style centered hero."""
    api = get_api_client()
    is_online = api.health_check()
    health = api.body_health() if is_online else None

    # Hero section
    safe_html(
        f"""
        <div class="wolf-welcome">
            <div class="wolf-welcome-logo">{T['wolf_emoji']}</div>
            <h1 class="wolf-welcome-title">{T['app_name']}</h1>
            <p class="wolf-welcome-subtitle">{T['app_tagline']}</p>
            <p class="wolf-welcome-subtitle-ar">{T['app_tagline_ar']}</p>
        </div>
        """,
        height=200,
    )

    # Quick start cards (2x2 grid)
    quick_starts = [
        {"icon": "\U0001F50D", "key": "qs_mistake_hunter", "prompt": "Help me debug my code: find bugs and explain what went wrong."},
        {"icon": "\U0001F9E0", "key": "qs_deep_thinking", "prompt": "Analyze a complex problem step-by-step with deep reasoning."},
        {"icon": "\U0001F6E0", "key": "qs_resourceful", "prompt": "Find the right tools and resources to solve this problem."},
        {"icon": "\U0001F4AA", "key": "qs_tenacity", "prompt": "Don't give up on me - keep trying until we find a working solution."},
    ]

    cards_html = ""
    for qs in quick_starts:
        title_key = f"{qs['key']}_title"
        desc_key = f"{qs['key']}_desc"
        # Escape prompt for HTML attribute (use chr(34) for double quote, chr(39) for single)
        prompt_safe = qs["prompt"].replace("'", "&apos;").replace(chr(34), "\"")
        cards_html += (
            f'<div class="wolf-quickstart-card" data-prompt="{prompt_safe}">'
            f'<div class="wolf-quickstart-card-icon">{qs["icon"]}</div>'
            f'<div class="wolf-quickstart-card-title">{T[title_key]}</div>'
            f'<div class="wolf-quickstart-card-desc">{T[desc_key]}</div>'
            f'</div>'
        )

    safe_html(f'<div class="wolf-quickstart-grid">{cards_html}</div>', height=320)

    # Backend health metrics (compact, below cards)
    if health:
        col1, col2, col3, col4 = st.columns(4)
        metrics = [
            ("\U0001F4DA", health["chromadb"]["collections"], T["chromadb_collections"]),
            ("\U0001F578", health["networkx"]["nodes"], T["networkx_nodes"]),
            ("\U0001F517", health["networkx"]["edges"], T["networkx_edges"]),
            ("\U0001F4BE", len(health["sqlite"]["tables"]), T["sqlite_tables"]),
        ]
        for col, (icon, value, label) in zip([col1, col2, col3, col4], metrics):
            with col:
                safe_html(
                    f"""
                    <div class="wolf-metric-card">
                        <div class="wolf-metric-icon">{icon}</div>
                        <div class="wolf-metric-value">{value}</div>
                        <div class="wolf-metric-label">{label}</div>
                    </div>
                    """,
                    height=100,
                )


# ============================================================================
# SIDEBAR (Collapsible left panel — ChatGPT-style)
# ============================================================================


def render_sidebar() -> None:
    """Sidebar with conversation list + page navigation."""
    with st.sidebar:
        # ===== Header =====
        st.markdown(
            f'<div style="display:flex; align-items:center; gap:8px; padding:8px 0;">'
            f'<span style="font-size:24px;">{T["wolf_emoji"]}</span>'
            f'<span style="font-weight:600; font-size:15px;">{T["app_name"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ===== New Chat Button (primary) =====
        if st.button(
            T["new_chat"],
            key="btn_new_chat",
            use_container_width=True,
            type="primary",
            help=T["new_chat"],
        ):
            _create_new_conversation()

        # ===== Search Conversations =====
        search_query = st.text_input(
            T["search_chats"],
            value=get_session("search_query", ""),
            key="search_chats_input",
            label_visibility="collapsed",
            placeholder=T["search_chats"],
        )
        set_session("search_query", search_query)

        st.markdown("---")

        # ===== Conversation List (grouped by date) =====
        _render_conversation_list()

        st.markdown("---")

        # ===== Settings (collapsible) =====
        _render_sidebar_settings()

        st.markdown("---")

        # ===== Status Footer =====
        _render_sidebar_footer()


def _create_new_conversation() -> None:
    """Create a new conversation via backend and switch to it."""
    api = get_api_client()
    conv = api.create_conversation()
    if conv and "conversation_id" in conv:
        set_session("active_conversation_id", conv["conversation_id"])
        set_session("messages", [])
        set_session("conversations_cache", None)
        set_session("conversations_cache_ts", 0)
        st.rerun()
    else:
        st.error(f"{T['error']}: could not create conversation (backend offline?)")


def _get_cached_conversations(api: APIClient, force_refresh: bool = False) -> list:
    """Get conversation list with 5-second cache to avoid hammering backend."""
    cache = get_session("conversations_cache", None)
    cache_ts = get_session("conversations_cache_ts", 0)
    now = time.time()

    if not force_refresh and cache is not None and (now - cache_ts) < 5:
        return cache

    conversations = api.list_conversations(limit=100)
    set_session("conversations_cache", conversations)
    set_session("conversations_cache_ts", now)
    return conversations


def _render_conversation_list() -> None:
    """Render the conversation list in the sidebar (grouped by date)."""
    api = get_api_client()
    conversations = _get_cached_conversations(api)
    active_id = get_session("active_conversation_id")
    search_query = get_session("search_query", "").lower().strip()

    if search_query:
        conversations = [
            c for c in conversations
            if search_query in (c.get("title", "") or "").lower()
        ]

    if not conversations:
        st.caption(T["no_conversations"])
        return

    groups = group_conversations_by_date(conversations)

    bucket_labels = {
        "today": T["today"],
        "yesterday": T["yesterday"],
        "previous_7_days": T["previous_7_days"],
    }

    for bucket_key, label in bucket_labels.items():
        convs_in_bucket = groups.get(bucket_key, [])
        if not convs_in_bucket:
            continue

        st.markdown(
            f'<div style="font-size:11px; color:var(--text-tertiary); '
            f'text-transform:uppercase; letter-spacing:0.05em; margin:8px 0 4px 0; '
            f'font-weight:600;">{label}</div>',
            unsafe_allow_html=True,
        )

        for conv in convs_in_bucket[:20]:
            cid = conv.get("conversation_id")
            title = truncate(conv.get("title") or T["new_chat"], 32)
            is_active = cid == active_id

            safe_html(
                f'<div class="wolf-conv-item {"wolf-conv-active" if is_active else ""}">'
                f'<div class="wolf-conv-title" title="{title}">{title}</div>'
                f'</div>',
                height=36,
            )

            col_open, col_del = st.columns([0.85, 0.15])
            with col_open:
                if st.button(
                    title,
                    key=f"open_conv_{cid}",
                    use_container_width=True,
                    disabled=is_active,
                    type="secondary",
                ):
                    _load_conversation(cid)
            with col_del:
                if st.button(
                    "\U0001F5D1",
                    key=f"del_conv_{cid}",
                    help=T["delete_chat"],
                ):
                    _delete_conversation(cid)


def _delete_conversation(cid: str) -> None:
    """Delete a conversation and refresh the list."""
    api = get_api_client()
    if api.delete_conversation(cid):
        if cid == get_session("active_conversation_id"):
            set_session("active_conversation_id", None)
            set_session("messages", [])
        set_session("conversations_cache", None)
        set_session("conversations_cache_ts", 0)
        st.rerun()


def _load_conversation(cid: str) -> None:
    """Load the conversation history into the session."""
    api = get_api_client()
    conv = api.get_conversation(cid)
    if conv and "messages" in conv:
        msgs = conv["messages"]
        ui_msgs = [
            {"role": m["role"], "content": m["content"], "ts": m.get("created_at")}
            for m in msgs
            if m.get("role") in ("user", "assistant")
        ]
        set_session("messages", ui_msgs)
        set_session("active_conversation_id", cid)
        st.rerun()
    else:
        st.error(f"{T['error']}: could not load conversation")


def _render_sidebar_settings() -> None:
    """Render the settings panel in the sidebar (collapsible)."""
    with st.expander(f"\u2699\uFE0F {T['settings_general']}", expanded=False):
        st.caption(T["model_label"])
        st.session_state.model = st.text_input(
            T["model_label"],
            value=get_session("model", "alpha-wolf-agent"),
            label_visibility="collapsed",
            key="sidebar_model_input",
        )

        st.caption(T["temperature_label"])
        st.session_state.temperature = st.slider(
            T["temperature_label"],
            min_value=0.0,
            max_value=1.5,
            value=get_session("temperature", 0.7),
            step=0.05,
            key="sidebar_temperature",
            label_visibility="collapsed",
        )

    st.markdown(
        f'<div style="font-size:11px; color:var(--text-tertiary); '
        f'text-transform:uppercase; letter-spacing:0.05em; margin:8px 0 4px 0; '
        f'font-weight:600;">Navigation | التنقل</div>',
        unsafe_allow_html=True,
    )

    nav_options = [
        ("Chat", f"\U0001F4AC Chat", "chat"),
        ("Memory", f"\U0001F9E0 Memory", "memory"),
        ("Tools", f"\U0001F6E0 Tools", "tools"),
    ]
    current_page = get_session("page", "Chat")
    for page_name, label, key in nav_options:
        if st.button(
            label,
            key=f"nav_{key}",
            use_container_width=True,
            type="secondary",
            disabled=(page_name == current_page),
        ):
            set_session("page", page_name)
            st.rerun()


def _render_sidebar_footer() -> None:
    """Render the sidebar footer (status + user info)."""
    is_online, status_label = get_backend_status()
    dot = "\U0001F7E2" if is_online else "\U0001F534"
    st.markdown(
        f'<div style="display:flex; align-items:center; gap:6px; font-size:12px; '
        f'color:var(--text-secondary); margin:8px 0;">'
        f'<span>{dot}</span>'
        f'<span>{T["backend_status"]}: {status_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="wolf-sidebar-user">
            <div class="wolf-user-avatar">\u0642</div>
            <div>
                <div class="wolf-user-name">{T['user_name']}</div>
                <div style="font-size:11px; color:var(--text-tertiary);">Alpha Wolf</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# CHAT PAGE (Main view)
# ============================================================================


def render_chat_page() -> None:
    """Render the main chat page (delegated to views/chat.py or inline)."""
    try:
        from views import chat
        chat.render()
    except ImportError as exc:
        logger.warning("views/chat.py not available, using inline: %s", exc)
        _render_chat_inline()


def _render_chat_inline() -> None:
    """Inline chat implementation if views/chat.py is unavailable."""
    api = get_api_client()
    is_online, _ = get_backend_status()

    if not is_online:
        st.markdown(
            f"""
            <div class="wolf-error">
                <span class="wolf-error-icon">\u26A0\uFE0F</span>
                <div>
                    <strong>{T['error_backend_offline']}</strong><br>
                    <code>uvicorn backend.main:app --port 8001</code>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    messages = get_session("messages", [])
    conv_id = get_session("active_conversation_id")

    if not messages and not conv_id:
        render_welcome()
    else:
        if conv_id:
            safe_html(
                f'<div style="font-size:12px; color:var(--text-tertiary); '
                f'padding:8px 0 12px 0; border-bottom:1px solid var(--border-subtle); '
                f'margin-bottom:16px;">\U0001F4AC {truncate(conv_id, 12)} &middot; '
                f'{len(messages)} messages</div>',
                height=40,
            )

    _render_message_history(messages)

    pending_prompt = get_session("pending_prompt")
    if pending_prompt:
        set_session("pending_prompt", None)
        _send_user_message(api, pending_prompt)
        return

    _render_chat_input_area(api)

    safe_html(
        f'<div class="wolf-chat-input-footer">{T["footer_disclaimer"]}</div>',
        height=24,
    )


def _render_message_history(messages: list) -> None:
    """Render all messages in the conversation."""
    for msg in messages:
        _render_single_message(msg)


def _render_single_message(msg: dict) -> None:
    """Render a single message bubble."""
    role = msg.get("role", "user")
    content = msg.get("content", "")
    ts = msg.get("ts") or msg.get("created_at")

    if role == "user":
        safe_html(
            f"""
            <div class="wolf-message wolf-message-user wolf-anim-fade-in">
                <div class="wolf-message-avatar">\u0642</div>
                <div class="wolf-message-body">
                    <div class="wolf-message-content">{escape_html(content)}</div>
                    <div class="wolf-message-timestamp">{format_timestamp(ts)}</div>
                </div>
            </div>
            """,
            height=100,
        )
    elif role == "assistant":
        _render_assistant_message(content, ts)
    elif role == "tool":
        _render_tool_call_message(msg)


def _render_assistant_message(content: str, ts) -> None:
    """Render an assistant message with markdown + code highlighting."""
    segments = split_text_by_code(content)
    body_parts = []
    body_parts.append('<div class="wolf-message wolf-message-assistant wolf-anim-fade-in">')
    body_parts.append(f'<div class="wolf-message-avatar">{T["wolf_emoji"]}</div>')
    body_parts.append('<div class="wolf-message-body">')
    body_parts.append('<div class="wolf-message-content">')

    for seg in segments:
        if seg["type"] == "text":
            if seg["content"].strip():
                body_parts.append(f'<div>{seg["content"]}</div>')
        elif seg["type"] == "code":
            lang = seg.get("lang", "text")
            code = escape_html(seg["content"])
            body_parts.append(
                f'<div class="wolf-code-block-wrapper">'
                f'<div class="wolf-code-header">'
                f'<span class="wolf-code-lang">{lang}</span>'
                f'<span class="wolf-code-copy">copy</span>'
                f'</div>'
                f'<pre><code class="language-{lang}">{code}</code></pre>'
                f'</div>'
            )

    body_parts.append('</div>')
    if ts:
        body_parts.append(f'<div class="wolf-message-timestamp">{format_timestamp(ts)}</div>')
    body_parts.append('</div></div>')

    full_html = "".join(body_parts)
    safe_html(full_html, height=200)


def _render_tool_call_message(msg: dict) -> None:
    """Render a tool call inline message."""
    name = msg.get("name", "unknown")
    args = msg.get("arguments", {})
    result = msg.get("result")
    duration = msg.get("duration_ms")
    success = msg.get("success", True)

    args_str = json.dumps(args, ensure_ascii=False, indent=2)[:500]
    result_str = json.dumps(result, ensure_ascii=False, indent=2)[:500] if result else ""
    result_class = "wolf-tool-result-ok" if success else "wolf-tool-result-err"
    duration_str = f"\u23F1 {duration}ms" if duration else ""

    safe_html(
        f"""
        <div class="wolf-tool-call open wolf-anim-slide-in">
            <div class="wolf-tool-call-header">
                <span class="wolf-tool-call-icon">\U0001F527</span>
                <span>{T['tool_calling']}:</span>
                <span class="wolf-tool-call-name">{escape_html(name)}</span>
                <span class="wolf-tool-call-arrow">\u25B8</span>
            </div>
            <div class="wolf-tool-call-body">
                <div class="wolf-tool-call-section">
                    <div class="wolf-tool-call-section-label">{T['tool_arguments']}</div>
                    <div class="wolf-tool-call-section-content">{escape_html(args_str)}</div>
                </div>
                {f'<div class="wolf-tool-call-section"><div class="wolf-tool-call-section-label">{T["tool_result"]}</div><div class="wolf-tool-call-section-content {result_class}">{escape_html(result_str)}</div></div>' if result else ''}
                {f'<div style="font-size:10px; color:var(--text-tertiary); margin-top:6px;">{duration_str}</div>' if duration_str else ''}
            </div>
        </div>
        """,
        height=120,
    )


def _render_chat_input_area(api: APIClient) -> None:
    """Render the chat input area at the bottom."""
    with st.form(key="chat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([10, 1])
        with col_input:
            user_input = st.text_area(
                T["chat_placeholder"],
                key="chat_input_field",
                height=80,
                max_chars=8000,
                label_visibility="collapsed",
                placeholder=T["chat_placeholder"],
            )
        with col_btn:
            st.write("")
            submitted = st.form_submit_button(
                "\u2191",
                use_container_width=False,
                help=T["send"],
            )

    if submitted and user_input and user_input.strip():
        _send_user_message(api, user_input.strip())


def _send_user_message(api: APIClient, prompt: str) -> None:
    """Send a user message: persist + stream assistant response."""
    conv_id = get_session("active_conversation_id")
    if not conv_id:
        conv = api.create_conversation(title=auto_generate_title(prompt))
        if conv and "conversation_id" in conv:
            conv_id = conv["conversation_id"]
            set_session("active_conversation_id", conv_id)
            set_session("conversations_cache", None)
            set_session("conversations_cache_ts", 0)
        else:
            st.error(f"{T['error']}: cannot create conversation")
            return

    messages = get_session("messages", [])
    user_msg = {"role": "user", "content": prompt, "ts": format_timestamp(None)}
    messages.append(user_msg)
    set_session("messages", messages)

    api.add_message(conv_id, "user", prompt, importance=5)

    _stream_response(api, conv_id, messages)


def _stream_response(api: APIClient, conv_id: str, messages: list) -> None:
    """Stream assistant response via SSE."""
    safe_html(
        f"""
        <div class="wolf-thinking wolf-anim-fade-in">
            <div class="wolf-thinking-dots">
                <div class="wolf-thinking-dot"></div>
                <div class="wolf-thinking-dot"></div>
                <div class="wolf-thinking-dot"></div>
            </div>
            <span>{T['thinking']}...</span>
        </div>
        """,
        height=40,
    )

    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

    accumulated = ""
    tool_calls_meta: list = []
    error_occurred = False
    start_time = time.time()

    try:
        for event in api.stream_chat(
            api_messages,
            conversation_id=conv_id,
            auto_tools=True,
        ):
            ev_type = event.get("type", "message")

            if ev_type == "token":
                chunk = event.get("chunk", "")
                accumulated += chunk
            elif ev_type == "tool_call":
                name = event.get("name", "")
                args = event.get("arguments", {})
                tool_calls_meta.append(
                    {"name": name, "arguments": args, "ts": format_timestamp(None)}
                )
                accumulated += f"\n\n\U0001F527 **{T['tool_calling']}: `{name}`**\n"
            elif ev_type == "tool_result":
                name = event.get("name", "")
                output = event.get("output", {})
                tool_calls_meta.append(
                    {"name": name, "result": output, "ts": format_timestamp(None)}
                )
                accumulated += f"\n\u2705 **Result**: `{name}`\n"
            elif ev_type == "error":
                error_occurred = True
                error_msg = event.get("message", "Unknown error")
                accumulated += f"\n\n\u26A0\uFE0F {T['error']}: {error_msg}"
                break
            elif ev_type == "done":
                break

    except Exception as exc:
        error_occurred = True
        accumulated += f"\n\n\u26A0\uFE0F {T['error']}: {exc}"
        logger.exception("Stream chat failed")

    if not accumulated.strip():
        accumulated = f"\u26A0\uFE0F {T['error']}: empty response from backend"

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Stream complete: %d chars in %dms (tools: %d)",
        len(accumulated), elapsed_ms, len(tool_calls_meta)
    )

    api.add_message(conv_id, "assistant", accumulated, importance=5)

    messages.append(
        {
            "role": "assistant",
            "content": accumulated,
            "ts": format_timestamp(None),
            "tool_calls": tool_calls_meta,
        }
    )
    set_session("messages", messages)


# ============================================================================
# MEMORY INSPECTOR PAGE (Sidebar nav)
# ============================================================================


def render_memory_page() -> None:
    """Memory Inspector page (delegated to views/ or inline)."""
    try:
        from views import memory_inspector
        memory_inspector.render()
    except ImportError:
        _render_memory_inline()


def _render_memory_inline() -> None:
    """Inline memory inspector."""
    api = get_api_client()

    safe_html(
        f"""
        <div style="padding:20px 0;">
            <h1 style="color:var(--accent-gold); margin:0 0 16px 0;">\U0001F9E0 {T['memory_inspector']}</h1>
        </div>
        """,
        height=80,
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        f"\U0001F3AF {T['active_goals']}",
        f"\u26A0\uFE0F {T['recent_mistakes']}",
        f"\U0001F4A1 {T['recent_reflections']}",
        f"\U0001F4DD {T['recent_episodes']}",
    ])

    with tab1:
        goals = api.list_goals(limit=20)
        if not goals:
            safe_html('<div class="wolf-info">No goals found</div>', height=60)
        else:
            for g in goals:
                title = g.get("title", "Untitled")
                priority = g.get("priority", 5)
                progress = g.get("progress_pct", 0)
                status = g.get("status", "open")
                safe_html(
                    f"""
                    <div class="wolf-tool-call wolf-anim-slide-in" style="margin:8px 0;">
                        <div class="wolf-tool-call-header">
                            <span>\U0001F3AF</span>
                            <span>{escape_html(title)}</span>
                            <span style="margin-left:auto; font-size:11px; color:var(--text-tertiary);">
                                {status} | priority: {priority} | {progress}%
                            </span>
                        </div>
                    </div>
                    """,
                    height=50,
                )

    with tab2:
        mistakes = api.list_mistakes(limit=20)
        if not mistakes:
            safe_html('<div class="wolf-info">No mistakes logged</div>', height=60)
        else:
            for m in mistakes:
                severity = m.get("severity", 5)
                what = m.get("what_went_wrong", "")
                lesson = m.get("lesson", "")
                safe_html(
                    f"""
                    <div class="wolf-tool-call wolf-anim-slide-in" style="margin:8px 0;">
                        <div class="wolf-tool-call-header">
                            <span>\u26A0\uFE0F</span>
                            <span>[Severity {severity}] {escape_html(truncate(what, 60))}</span>
                            <span class="wolf-tool-call-arrow">\u25B8</span>
                        </div>
                        <div class="wolf-tool-call-body">
                            <div class="wolf-tool-call-section">
                                <div class="wolf-tool-call-section-label">{T['what_went_wrong']}</div>
                                <div class="wolf-tool-call-section-content">{escape_html(what)}</div>
                            </div>
                            <div class="wolf-tool-call-section">
                                <div class="wolf-tool-call-section-label">{T['lesson']}</div>
                                <div class="wolf-tool-call-section-content wolf-tool-result-ok">{escape_html(lesson)}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    height=60,
                )

    with tab3:
        safe_html('<div class="wolf-info">Reflections endpoint is POST-only - no list view</div>', height=60)

    with tab4:
        episodes = api.list_episodes(limit=20)
        if not episodes:
            safe_html('<div class="wolf-info">No episodes found</div>', height=60)
        else:
            for e in episodes:
                trigger = e.get("trigger_type", "")
                importance = e.get("importance", 5)
                content = e.get("content", "")
                safe_html(
                    f"""
                    <div class="wolf-tool-call wolf-anim-slide-in" style="margin:8px 0;">
                        <div class="wolf-tool-call-header">
                            <span>\U0001F4DD</span>
                            <span>[{trigger}] (importance: {importance})</span>
                            <span class="wolf-tool-call-arrow">\u25B8</span>
                        </div>
                        <div class="wolf-tool-call-body">
                            <div class="wolf-tool-call-section-content">{escape_html(truncate(content, 200))}</div>
                        </div>
                    </div>
                    """,
                    height=60,
                )


# ============================================================================
# TOOLS REGISTRY PAGE (Sidebar nav)
# ============================================================================


def render_tools_page() -> None:
    """Tools Registry page (delegated to views/ or inline)."""
    try:
        from views import tools_registry
        tools_registry.render()
    except ImportError:
        _render_tools_inline()


def _render_tools_inline() -> None:
    """Inline tools registry."""
    api = get_api_client()
    tools_data = api.list_tools()

    safe_html(
        f"""
        <div style="padding:20px 0;">
            <h1 style="color:var(--accent-gold); margin:0 0 16px 0;">\U0001F6E0 {T['tools_total']}</h1>
        </div>
        """,
        height=80,
    )

    if not tools_data:
        safe_html('<div class="wolf-info">No tools available</div>', height=60)
        return

    tools = tools_data.get("tools", []) if isinstance(tools_data, dict) else tools_data
    if not tools:
        safe_html('<div class="wolf-info">No tools available</div>', height=60)
        return

    safe_html(
        f'<div class="wolf-info">Total: <strong>{len(tools)}</strong></div>',
        height=40,
    )

    for tool in tools:
        name = tool.get("name", "unknown")
        category = tool.get("category", "general")
        invocation = tool.get("invocation", "")
        invocations = tool.get("invocation_count", 0)
        safe_html(
            f"""
            <div class="wolf-tool-call wolf-anim-slide-in" style="margin:8px 0;">
                <div class="wolf-tool-call-header">
                    <span>\U0001F6E0</span>
                    <span>{escape_html(name)}</span>
                    <span style="margin-left:auto; font-size:11px; color:var(--text-tertiary);">
                        {category} | {invocations}x
                    </span>
                </div>
                <div class="wolf-tool-call-body">
                    <div class="wolf-tool-call-section">
                        <div class="wolf-tool-call-section-label">{T['tool_invocation']}</div>
                        <div class="wolf-tool-call-section-content">{escape_html(invocation)}</div>
                    </div>
                </div>
            </div>
            """,
            height=80,
        )


# ============================================================================
# HELPERS
# ============================================================================


def escape_html(text: str) -> str:
    """Escape HTML special characters for safe rendering."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&")
        .replace("<", "<")
        .replace(">", ">")
        .replace(chr(34), "\"")
        .replace(chr(39), "'")
    )


def route_page() -> None:
    """Route to the selected page."""
    page = get_session("page", "Chat")

    if page == "Chat":
        render_chat_page()
    elif page == "Memory":
        render_memory_page()
    elif page == "Tools":
        render_tools_page()
    else:
        render_chat_page()


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Main entry point."""
    init_all_session_state()
    render_topbar()
    render_sidebar()
    route_page()


if __name__ == "__main__":
    main()
