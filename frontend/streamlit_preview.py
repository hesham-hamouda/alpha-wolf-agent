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
import re
import sys
import time
from pathlib import Path
from typing import Any

# Project setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from streamlit.components.v1 import html as _streamlit_html

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
    background-color: #0F0F0F;        /* Per UX fix 2026-09-25: matches
                                       page background (was #212121 grey
                                       which clashed with #0F0F0F). */
    border-bottom: 1px solid #2E2E2E;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    z-index: 999;
    color: #ECECEC;
    font-family: "Inter", system-ui, sans-serif;
    backdrop-filter: none;            /* Per UX fix 2026-09-25: removed
                                       blur (was causing transparent veil). */
    -webkit-backdrop-filter: none;
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
/* Quickstart cards removed per UX fix 2026-09-25 (user feedback). */
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
/* Metric cards removed per UX fix 2026-09-25 — counters moved to sidebar
   Settings expander (see _render_sidebar_settings). */
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

/* ========================================================================
   IFRAME BODY FIX (Phase UI-UX 2026-09-25 — dark overlay fix):
   Messages rendered via safe_html() live inside sandboxes where styles.css
   does NOT apply. We MUST inline ALL message styling here.
   ======================================================================== */
html, body {
    background-color: transparent !important;
    color: #F5F5F5 !important;
    font-family: "Inter", system-ui, sans-serif !important;
    margin: 0 !important;
    padding: 0 !important;
}
body { overflow: visible !important; }

.wolf-chat-input-footer {
    color: #6A6A6A !important;
    font-size: 11px !important;
    text-align: center !important;
    padding: 4px 0 !important;
    opacity: 1 !important;
}

.wolf-message {
    display: flex !important;
    gap: 12px !important;
    padding: 10px 0 !important;
    width: 100% !important;
    align-items: flex-start !important;
    line-height: 1.75 !important;
    background-color: transparent !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    filter: none !important;
    opacity: 1 !important;
}
.wolf-message-user { justify-content: flex-end !important; }
.wolf-message-assistant { justify-content: flex-start !important; }

.wolf-message-avatar {
    flex-shrink: 0 !important;
    width: 32px !important;
    height: 32px !important;
    border-radius: 9999px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 16px !important;
    margin-top: 2px !important;
}
.wolf-message-user .wolf-message-avatar {
    background: linear-gradient(135deg, #5436DA, #8B5CF6) !important;
    color: #FFFFFF !important;
    order: 2 !important;
}
.wolf-message-assistant .wolf-message-avatar {
    background: linear-gradient(135deg, #FFD700, #FFA500) !important;
    color: #1A1A1A !important;
    order: 1 !important;
}

.wolf-message-body {
    max-width: calc(100% - 80px) !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 4px !important;
}
.wolf-message-user .wolf-message-body { align-items: flex-end !important; order: 1 !important; }
.wolf-message-assistant .wolf-message-body { align-items: flex-start !important; order: 2 !important; }

/* User bubble — solid dark gray */
.wolf-message-content {
    background-color: #1A1A1A !important;
    color: #F5F5F5 !important;
    padding: 14px 18px !important;
    border-radius: 14px !important;
    font-size: 15px !important;
    line-height: 1.75 !important;
    word-wrap: break-word !important;
    overflow-wrap: break-word !important;
    max-width: 100% !important;
    border: 1px solid #3A3B40 !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    filter: none !important;
    opacity: 1 !important;
}

/* Assistant bubble — transparent + bright text */
.wolf-message-assistant .wolf-message-content {
    background-color: transparent !important;
    padding: 14px 0 !important;
    border: none !important;
    font-size: 16px !important;
    line-height: 1.8 !important;
    color: #FAFAFA !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    filter: none !important;
    opacity: 1 !important;
}

.wolf-message-content p { margin: 0 0 8px 0 !important; color: inherit !important; }
.wolf-message-content p:last-child { margin-bottom: 0 !important; }
.wolf-message-content ul, .wolf-message-content ol {
    margin: 8px 0 !important; padding-left: 24px !important; color: inherit !important;
}
.wolf-message-content li { color: inherit !important; }
.wolf-message-content strong { color: #FFD700 !important; font-weight: 600 !important; }
.wolf-message-content em { color: inherit !important; font-style: italic !important; }
.wolf-message-content h1, .wolf-message-content h2,
.wolf-message-content h3, .wolf-message-content h4 {
    color: #FFD700 !important; margin: 16px 0 8px 0 !important; font-weight: 600 !important;
}
.wolf-message-content h1 { font-size: 1.5em !important; }
.wolf-message-content h2 { font-size: 1.3em !important; }
.wolf-message-content h3 { font-size: 1.15em !important; }
.wolf-message-content code {
    background-color: #252525 !important;
    color: #ECECEC !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    font-family: "JetBrains Mono", monospace !important;
    font-size: 0.9em !important;
}
.wolf-message-content pre {
    background-color: #1A1B20 !important;
    color: #ECECEC !important;
    padding: 12px 16px !important;
    border-radius: 8px !important;
    overflow-x: auto !important;
    border: 1px solid #2E2E2E !important;
}
.wolf-message-content pre code {
    background-color: transparent !important;
    padding: 0 !important;
    font-size: 13px !important;
}

.wolf-message-timestamp {
    font-size: 11px !important;
    color: #8E8E8E !important;
    margin-top: 2px !important;
    opacity: 1 !important;
}

/* Code block wrapper (assistant messages) */
.wolf-code-block-wrapper {
    margin: 12px 0 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    border: 1px solid #2E2E2E !important;
    background-color: #1A1A1A !important;
}
.wolf-code-header {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    padding: 6px 12px !important;
    background-color: #252525 !important;
    color: #8E8E8E !important;
    font-family: "JetBrains Mono", monospace !important;
    font-size: 11px !important;
}
.wolf-code-block-wrapper pre {
    margin: 0 !important;
    padding: 12px 16px !important;
    background-color: #1A1A1A !important;
    color: #ECECEC !important;
    overflow-x: auto !important;
    font-family: "JetBrains Mono", monospace !important;
    font-size: 13px !important;
}
.wolf-code-copy { cursor: pointer !important; }
.wolf-code-copy:hover { color: #FFD700 !important; }

/* Wolf-error styling inside iframe */
.wolf-error {
    background-color: rgba(239, 68, 68, 0.1) !important;
    border: 1px solid rgba(239, 68, 68, 0.3) !important;
    color: #FCA5A5 !important;
    padding: 12px 16px !important;
    border-radius: 10px !important;
    margin: 12px 0 !important;
}
.wolf-error-icon { margin-right: 8px !important; }
</style>
"""

def safe_html(content: str, height: int = None) -> str:
    """Render HTML with inline styles for iframe compatibility.

    FIX 2026-09-27 (Round 19): replaced st.components.v1.html() with
    st.html(). The Streamlit html() component creates a sandboxed iframe
    with both allow-scripts and allow-same-origin, which is a known
    sandbox-escape vulnerability. st.html() renders directly in the page
    DOM — no iframe, no sandbox, no raw HTML shown to user.
    """
    full = INLINE_BASE_STYLES + content
    st.html(full)


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
# PHASE 51 — WCAG 2.1 AA Accessibility (a11y)
# ============================================================================
# Skip-link for keyboard/screen-reader users (WCAG 2.4.1).
# Visually hidden until focused; first Tab on the page lands here.
st.markdown(
    '<a href="#main-content" class="skip-link" tabindex="0">'
    'Skip to main content | تخطّي إلى المحتوى الرئيسي'
    '</a>',
    unsafe_allow_html=True,
)

# <html lang> for AR + EN so screen readers pick the right pronunciation
st.markdown(
    '<script>document.documentElement.lang = "ar";</script>',
    unsafe_allow_html=True,
)


# ============================================================================
# Session State Init (Iron Law #48 — Separated)
# ============================================================================


def init_all_session_state() -> None:
    """Initialize all session state variables in one place.
    
    This is the SINGLE canonical session state initialization for the Alpha Wolf UI.
    All pages must use these keys. Do not create parallel initializations.
    """
    # Core session keys (canonical)
    if "active_conversation_id" not in st.session_state:
        st.session_state.active_conversation_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "streaming_active" not in st.session_state:
        st.session_state.streaming_active = False
    if "page" not in st.session_state:
        st.session_state.page = "Chat"
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None
    if "model" not in st.session_state:
        st.session_state.model = "alpha-wolf-agent-v8"  # FIX 2026-10-06: original broken
    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.7
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    if "conversations_cache" not in st.session_state:
        st.session_state.conversations_cache = None
    if "conversations_cache_ts" not in st.session_state:
        st.session_state.conversations_cache_ts = 0
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    if "settings_open" not in st.session_state:
        st.session_state.settings_open = False
    # Agent lifecycle keys (restart / stop)
    if "stop_requested" not in st.session_state:
        st.session_state.stop_requested = False
    if "streaming_partial" not in st.session_state:
        st.session_state.streaming_partial = None
    if "agent_notice" not in st.session_state:
        st.session_state.agent_notice = None


# ============================================================================
# Page Routing (Canonical - Iron Law #48)
# ============================================================================

# Canonical page names (single source of truth)
CANONICAL_PAGES = {
    "Chat": "💬 Chat",
    "Agent": "🐺 Agent",
    "Memory": "🧠 Memory",
    "Tools": "🛠️ Tools",
    # FIX 2026-10-06 (Phase 46): added the three previously collapsed pages
    # so users can navigate to Projects, Body Health, and Memory Inspector
    # directly. Iron Law #42 keeps each surface in its own canonical slot.
    "Projects": "📁 Projects",
    "Health": "🏥 Health",
    "Inspector": "🔍 Inspector",
}

def get_canonical_page() -> str:
    """Get the canonical page name, normalizing any legacy values."""
    page = st.session_state.get("page", "Chat")
    # Map legacy page names to canonical
    legacy_map = {
        "Body Health": "Memory",
        "Memory Inspector": "Memory",
        "Tools Registry": "Tools",
        "Project Awareness": "Memory",
    }
    return legacy_map.get(page, page)

def set_canonical_page(page: str) -> None:
    """Set page using canonical name (BEFORE: stored value with emoji, caused
    routing bug — FIXED in Phase 11+ v4.2 to store the key not the value)."""
    # PHASE 11+ v4.2 FIX: Store the canonical key (e.g., "Memory") not the
    # value (e.g., "🧠 Memory") so route_page() can match the routing condition.
    st.session_state.page = page
    st.rerun()


# ============================================================================
# AGENT LIFECYCLE (Restart / Stop — single source of truth)
# ============================================================================
# FIX 2026-09-26: the two "Restart UI" buttons previously contained duplicated
# inline logic and showed st.success() right before st.rerun() — the message
# was discarded with the current run and never displayed. Both buttons now
# call restart_agent(). A Stop button was added: it sets stop_requested,
# which the streaming loops check on every SSE event; the partial reply is
# persisted each chunk so interrupting mid-generation keeps what arrived.

# Config keys preserved across a restart (everything else is reset).
RESTART_KEEP_KEYS = frozenset({"model", "temperature", "theme", "page"})


def _L(key: str, fallback: str) -> str:
    """Bilingual label lookup resilient to a stale cached utils module.

    قراءة تسمية ثنائية اللغة بمقاومة لموديول utils قديم مخزّن.

    Streamlit re-executes this script on every rerun but keeps already-
    imported modules (like utils) cached for the process lifetime. If the
    frontend process predates a utils.py change, T[...] would raise
    KeyError and crash the whole page. T.get() with a literal fallback
    keeps the UI alive; restarting the frontend loads the fresh module.
    """
    try:
        return T.get(key, fallback)  # type: ignore[union-attr]
    except Exception:
        return fallback


def restart_agent() -> None:
    """Reset agent runtime state and start fresh (restart).

    إعادة تشغيل الوكيل: تصفير الحالة والبدء من جديد.

    Keeps model/temperature/theme/page. Clears messages, active
    conversation, caches, pending prompts/files, streaming flags and any
    partial reply. Shows confirmation AFTER rerun via agent_notice
    (calling st.success() before st.rerun() would discard the message).
    """
    keep = {k: st.session_state[k] for k in RESTART_KEEP_KEYS if k in st.session_state}
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    for k, v in keep.items():
        st.session_state[k] = v
    init_all_session_state()
    st.session_state.agent_notice = _L(
        "agent_restarted", "Agent restarted — fresh state | تمت إعادة تشغيل الوكيل — حالة جديدة"
    )
    st.rerun()


def request_agent_stop() -> None:
    """Request the agent to stop the ongoing generation (stop).

    طلب إيقاف الوكيل: يوقف التوليد الجاري فوراً.

    Sets stop_requested. If a stream is running, Streamlit interrupts the
    run on this interaction; the next run finalizes the persisted partial
    reply (see _finalize_stopped_stream). If idle, just shows a notice.
    """
    if st.session_state.get("streaming_active"):
        st.session_state.stop_requested = True
    else:
        st.session_state.agent_notice = _L(
            "no_active_generation", "No active generation to stop | لا يوجد توليد جارٍ لإيقافه"
        )
    st.rerun()


def stop_everything_agent() -> None:
    """Stop backend + frontend completely (Phase 35 — Stop Everything button).

    إيقاف الخادم والواجهة بالكامل عبر endpoint /v1/admin/stop-all.

    Strategy:
    1. Call POST /v1/admin/stop-all (backend kills Streamlit + SIGTERMs itself).
    2. Show a notice then sleep briefly so the user sees it.
    3. Rerun — Streamlit itself will be killed by the backend, so the rerun
       will start failing and the page will close.
    """
    api = get_api_client()
    if not get_backend_status()[0]:
        st.session_state.agent_notice = _L(
            "stop_disabled_no_backend",
            "Backend offline — cannot stop remotely | الخادم متوقف — لا يمكن الإيقاف عن بُعد",
        )
        st.rerun()
        return

    st.session_state.agent_notice = _L(
        "stopping_now", "Stopping... You can close this tab. | جاري الإيقاف... يمكنك إغلاق هذا التبويب."
    )

    # Fire-and-don't-wait: the backend will kill us shortly.
    try:
        # Use a thread so the UI thread isn't blocked if backend hangs.
        import threading
        def _call():
            api.admin_stop_all(timeout=3.0)
        threading.Thread(target=_call, daemon=True).start()
    except Exception as exc:
        logger.warning("stop_everything_agent failed: %s", exc)

    # Give the notice 1.5s to render, then rerun (will likely fail because
    # backend killed us). Either way, the user sees confirmation.
    import time as _time
    _time.sleep(1.5)
    st.rerun()


def _persist_stream_partial(
    conv_id: str,
    accumulated: str,
    accumulated_reasoning: str,
    tool_calls_meta: list,
) -> None:
    """Persist the in-flight reply so a Stop/restart keeps what arrived.

    حفظ الرد الجزئي أثناء البث حتى لا يضيع عند الإيقاف.
    """
    st.session_state.streaming_partial = {
        "conv_id": conv_id,
        "content": accumulated,
        "reasoning": accumulated_reasoning,
        "tool_calls": [dict(tc) for tc in tool_calls_meta],
    }


def _clear_stream_state() -> None:
    """Clear all streaming flags after a stream finishes or is stopped."""
    st.session_state.streaming_active = False
    st.session_state.stop_requested = False
    st.session_state.streaming_partial = None


def _finalize_stopped_stream() -> None:
    """Finalize a stream interrupted via Stop (runs at start of next run).

    إنهاء البث الموقوف: يحفظ الرد الجزئي كرسالة مساعد.

    Called from main() before rendering. If stop was requested while a
    stream was active, the persisted partial reply is saved to history
    (UI + backend) and flags are cleared.
    """
    if not st.session_state.get("stop_requested"):
        return
    if not st.session_state.get("streaming_active"):
        st.session_state.stop_requested = False
        return
    partial = st.session_state.get("streaming_partial") or {}
    content = (partial.get("content") or "").strip()
    stopped_label = _L("agent_stopped", "Agent stopped | تم إيقاف الوكيل")
    stopped_partial = _L(
        "agent_stopped_partial",
        "Generation stopped by user — partial reply kept | تم إيقاف التوليد — تم الاحتفاظ بالرد الجزئي",
    )
    if not content:
        content = f"⏹ {stopped_label}"
    else:
        content = f"{content}\n\n⏹ {stopped_partial}"
    messages = st.session_state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": content,
        "ts": format_timestamp(None),
        "tool_calls": partial.get("tool_calls", []),
        "reasoning": partial.get("reasoning", ""),
        "stopped": True,
    })
    st.session_state.messages = messages
    conv_id = partial.get("conv_id") or st.session_state.get("active_conversation_id")
    if conv_id:
        try:
            get_api_client().add_message(conv_id, "assistant", content, importance=5)
        except Exception as exc:
            logger.warning("persist stopped reply failed: %s", exc)
    _clear_stream_state()
    st.session_state.agent_notice = f"⏹ {_L('agent_stopped', 'Agent stopped | تم إيقاف الوكيل')}"


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

    model = get_session("model", "alpha-wolf-agent-v8")  # FIX 2026-10-06: original broken
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
    """Welcome screen when no conversation is active.

    Per UX fix 2026-09-25: quickstart cards and metric cards REMOVED.
    User wanted minimal welcome — just the hero, with a hint to start
    the conversation from the chat input below. Onboarding removed for
    a clean, focused experience.
    """
    api = get_api_client()
    is_online = api.health_check()

    # Hero section only — minimal, focused welcome.
    safe_html(
        f"""
        <div class="wolf-welcome">
            <div class="wolf-welcome-logo">{T['wolf_emoji']}</div>
            <h1 class="wolf-welcome-title">{T['app_name']}</h1>
            <p class="wolf-welcome-subtitle">{T['app_tagline']}</p>
            <p class="wolf-welcome-subtitle-ar">{T['app_tagline_ar']}</p>
            <p style="margin-top:32px; color:var(--text-tertiary); font-size:14px;">
                Start chatting from the input below | ابدأ المحادثة من الأسفل
            </p>
        </div>
        """,
        height=240,
    )
    # NOTE: Quick start cards (2x2 grid) and backend metric cards were
    # REMOVED per UX fix 2026-09-25 (user feedback: "cleanup welcome,
    # remove onboarding"). Counters are now exclusively in the sidebar
    # Settings expander (see _render_sidebar_settings).


# ============================================================================
# SIDEBAR (Collapsible left panel — ChatGPT-style)
# ============================================================================


def render_sidebar() -> None:
    """Sidebar with conversation list + page navigation."""
    with st.sidebar:
        # PHASE 51 a11y: announce the navigation region so screen-reader users
        # know the sidebar is a navigation landmark (WCAG 4.1.2).
        st.markdown(
            '<div role="navigation" aria-label="Primary navigation | التنقل الرئيسي">',
            unsafe_allow_html=True,
        )
        # ===== Header with Restart Button =====
        col_header, col_restart = st.columns([4, 1])
        with col_header:
            st.markdown(
                f'<div style="display:flex; align-items:center; gap:8px; padding:8px 0;">'
                f'<span style="font-size:24px;">{T["wolf_emoji"]}</span>'
                f'<span style="font-weight:600; font-size:15px;">{T["app_name"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_restart:
            # Restart agent — always visible in header (delegates to restart_agent)
            if st.button(
                "\U0001F504",
                key="btn_restart_ui_header",
                use_container_width=True,
                help=_L(
                    "restart_agent_help",
                    "Reset agent state and start fresh (keeps model settings) | تصفير حالة الوكيل والبدء من جديد (مع الاحتفاظ بإعدادات النموذج)",
                ),
            ):
                restart_agent()

        # FIX (Phase UI-UX): Removed "New Chat" button per user feedback.
        # New conversations can still be created via:
        #   - Selecting an existing conversation from the list
        #   - Auto-created when sending first message (see _send_user_message_streaming)
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

        # ===== Page Navigation (Canonical) =====
        st.markdown(
            f'<div style="font-size:11px; color:var(--text-tertiary); '
            f'text-transform:uppercase; letter-spacing:0.05em; margin:8px 0 4px 0; '
            f'font-weight:600;">Navigation | التنقل</div>',
            unsafe_allow_html=True,
        )

        current_page = get_canonical_page()
        for page_key, page_label in CANONICAL_PAGES.items():
            if st.button(
                page_label,
                key=f"nav_{page_key}",
                use_container_width=True,
                type="secondary" if page_key != current_page else "primary",
                disabled=(page_key == current_page),
            ):
                set_canonical_page(page_key)

        st.markdown("---")

        # ===== Status Footer =====
        _render_sidebar_footer()

        # PHASE 51 a11y — close the <div role="navigation"> opened in render_sidebar()
        st.markdown("</div>", unsafe_allow_html=True)


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
    """Render the settings panel in the sidebar (collapsible).

    Per UX feedback (Phase X): we now expose **two** collapsibles in
    the sidebar — (1) General (model + temperature) and (2) Conversation
    Info (counters that were previously rendered inline in the chat
    area, e.g., "💬 {conv_id} · {N} messages").
    """
    with st.expander(f"\u2699\uFE0F {T['settings_general']}", expanded=False):
        st.caption(T["model_label"])
        st.session_state.model = st.text_input(
            T["model_label"],
            value=get_session("model", "alpha-wolf-agent-v8"),  # FIX 2026-10-06
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

    # NEW: Conversation Info panel — moved constants from chat area
    with st.expander(f"\U0001F4AC {T['settings_advanced']}", expanded=False):
        conv_id = get_session("active_conversation_id", None)
        messages = get_session("messages", [])
        msg_count = len(messages)

        if conv_id:
            st.caption(
                f"**{T['conversations']}:** `{truncate(conv_id, 16)}`"
            )
        else:
            st.caption(f"_{T['no_conversations']}_")

        st.caption(f"**Messages in memory:** `{msg_count}`")

        # Clear conversation button (actuator) — useful when in a long chat
        if conv_id and msg_count > 0:
            if st.button(
                "\U0001F5D1 " + T["clear_chat"],
                key="sidebar_clear_chat_btn",
                use_container_width=True,
                help=T["clear_confirm"],
            ):
                set_session("messages", [])
                st.rerun()


def _render_sidebar_footer() -> None:
    """Render the sidebar footer (status + agent controls + user info)."""
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

    # One-shot notice (set BEFORE rerun by restart/stop, shown here).
    notice = st.session_state.get("agent_notice")
    if notice:
        st.success(notice)
        st.session_state.agent_notice = None

    # Agent controls: Restart (reset state) + Stop (halt generation)
    col_restart, col_stop = st.columns(2)
    with col_restart:
        if st.button(
            f"\U0001F504 {_L('restart_agent', 'Restart agent | إعادة تشغيل الوكيل')}",
            key="btn_restart_ui_footer",
            use_container_width=True,
            help=_L(
                "restart_agent_help",
                "Reset agent state and start fresh (keeps model settings) | تصفير حالة الوكيل والبدء من جديد (مع الاحتفاظ بإعدادات النموذج)",
            ),
        ):
            restart_agent()
    with col_stop:
        stop_disabled = not st.session_state.get("streaming_active", False)
        if st.button(
            f"⏹ {_L('stop_agent', 'Stop agent | إيقاف الوكيل')}",
            key="btn_stop_agent_footer",
            use_container_width=True,
            help=_L(
                "stop_agent_help",
                "Stop the ongoing generation immediately | إيقاف التوليد الجاري فوراً",
            ),
            disabled=stop_disabled,
        ):
            request_agent_stop()

    # Phase 35: Stop Everything button — kills backend + frontend completely.
    # Uses a confirmation dialog so an accidental click doesn't shut down
    # the running app.
    with st.expander("🛑", expanded=False):
        is_online, _ = get_backend_status()
        st.caption(_L(
            "stop_everything_help",
            "Stop backend + frontend completely (closes this app) | إيقاف الخادم والواجهة بالكامل (يُغلق هذا التطبيق)",
        ))
        if st.button(
            f"\U0001F6D1 {_L('stop_everything', 'Stop Everything | إيقاف كل شيء')}",
            key="btn_stop_everything",
            use_container_width=True,
            type="secondary",
            disabled=not is_online,
            help=_L(
                "stop_everything_help",
                "Stop backend + frontend completely (closes this app) | إيقاف الخادم والواجهة بالكامل (يُغلق هذا التطبيق)",
            ),
        ):
            stop_everything_agent()

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
    """Render the main chat page.

    PHASE 35 FIX (circular call): Previously this imported `views/chat.py`
    which in turn did `from streamlit_preview import _render_chat_inline` —
    a circular import that double-rendered the chat UI. We now call the
    inline renderer directly. The `views/chat.py` module is kept for
    potential future reuse but is no longer wired into the default path.
    """
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

    # FIX (Phase UI-UX): Removed welcome screen + quick-start cards per
    # user feedback. Main chat area now only shows messages + input.
    # If user opens the app with no conversation, they'll see an empty
    # chat list (cleaner, no marketing clutter).
    # NOTE: The "💬 conv_id · N messages" counter was REMOVED from the main
    # chat area per UX feedback (Phase X). It's now exposed via the sidebar
    # settings panel (see _render_sidebar_settings + sidebar_status_line).

    # ===== Phase 48 (P1) — Rate this conversation button =====
    if conv_id:
        _rate_col, _resume_col, _spacer_col = st.columns([1, 1, 5])
        with _rate_col:
            if st.button("⭐ Rate | تقييم", key=f"rate_conv_{conv_id}"):
                eval_res = _safe_api_call(
                    lambda cid=conv_id: api.evaluate_conversation(cid), default=None
                )
                if eval_res and not eval_res.get("error"):
                    score = (
                        eval_res.get("score")
                        or eval_res.get("quality_score")
                        or eval_res.get("evaluation", {}).get("score")
                    )
                    if score is not None:
                        st.success(f"Score: {score}")
                    else:
                        st.success("Evaluation complete.")
                    with st.expander("Details", expanded=False):
                        st.json(eval_res)
                else:
                    st.info("Evaluation endpoint did not return data.")
        with _resume_col:
            if st.button(
                "▶️ Resume Stream", key=f"resume_stream_{conv_id}",
                help="Probe GET /v1/chat/stream/resume/{conv_id}",
            ):
                with st.spinner("Probing stream resume endpoint..."):
                    resume_res = _safe_api_call(
                        lambda cid=conv_id: api.resume_stream(cid, from_chunk=0),
                        default=None,
                    )
                if resume_res and resume_res.get("error"):
                    st.warning(f"⚠️ {resume_res['error']}")
                else:
                    st.success("✅ Stream endpoint reachable.")
                with st.expander("Stream Resume Details", expanded=True):
                    st.json(resume_res)

    # ===== MESSAGE CONTAINER (above input) =====
    # Create a container for messages that will hold both history and streaming content
    message_container = st.container()
    
    with message_container:
        _render_message_history(messages)
        
        # Placeholder for streaming assistant response
        streaming_placeholder = st.empty()

    pending_prompt = get_session("pending_prompt")
    if pending_prompt:
        set_session("pending_prompt", None)
        _send_user_message_streaming(api, pending_prompt, streaming_placeholder)
        return

    _render_chat_input_area(api)

    # Footer disclaimer removed per القائد هشام directive (2026-09-25):
    # "Alpha Wolf Agent can make mistakes. Verify important info. | قد يخطئ الذئب. تحقق من المعلومات المهمة."
    # The agent should display professional, confident output — not disclaim errors.
    # See PROJECT_LOG.md Phase 14 entry for full context.


def _render_message_history(messages: list) -> None:
    """Render all messages in the conversation."""
    for msg in messages:
        _render_single_message(msg)


def _render_single_message(msg: dict) -> None:
    """Render a single message bubble."""
    role = msg.get("role", "user")
    content = msg.get("content", "")
    ts = msg.get("ts") or msg.get("created_at")
    reasoning = msg.get("reasoning", "")

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
        # Show reasoning/thinking in a collapsible section (if available)
        if reasoning and reasoning.strip():
            with st.expander("\U0001F4AD Thinking Process | عملية التفكير", expanded=False):
                st.markdown(reasoning)
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
    """Render the chat input area using Streamlit's native chat_input with
    built-in file upload (Streamlit 1.40+ feature).

    Per القائد هشام directive (2026-09-25):
    - File upload button must be positioned right next to the send button
      (matching professional patterns like ChatGPT/Claude).
    - The input must be PINNED to the BOTTOM of the page (ChatGPT/Claude style).

    PHASE 14 v6 (FINAL): Use Streamlit's native `st.chat_input(accept_file=True)`
    which gives us:
    - Pinned-to-bottom text input (Streamlit native)
    - File upload button RIGHT next to send button (Streamlit native)
    - No custom CSS hacks needed — Streamlit handles the layout
    - File uploaded via Streamlit's `ChatInputValue` returned object

    Earlier attempts failed because:
    - st.form filled entire viewport (CSS couldn't constrain)
    - st.file_uploader outside the form appeared in the wrong column
    - Custom HTML upload button required JS to wire to file picker
    """
    # Show pending file badge above the chat input (compact)
    pending_file = get_session("pending_file")
    if pending_file:
        col_badge, col_clear = st.columns([0.9, 0.1])
        with col_badge:
            st.caption(f"\U0001F4CE {pending_file['name']}")
        with col_clear:
            if st.button(
                "✕",
                key="chat_clear_pending_file",
                help="Remove attached file",
            ):
                set_session("pending_file", None)
                st.rerun()

    # PHASE 14 v6: Streamlit 1.40+ supports accept_file in chat_input.
    # This gives us the native ChatGPT-style layout (text input + send button
    # + upload button all in one pinned component).
    # PHASE 51 a11y: max_chars provides a soft upper bound; the bilingual
    # placeholder + aria-label-via-help give screen-reader users a usable name.
    submitted_input = st.chat_input(
        placeholder=T["chat_placeholder"],
        key="wolf_chat_input",
        accept_file=True,
        file_type=["txt", "md", "py", "json", "yaml", "yml", "csv", "log"],
        max_chars=8000,
    )

    if submitted_input is not None:
        # In Streamlit 1.40+, chat_input returns a ChatInputValue with .text
        # and .files attributes. In earlier versions it returned a plain str.
        prompt = ""
        uploaded_files = []
        if hasattr(submitted_input, "text"):
            prompt = (submitted_input.text or "").strip()
            try:
                uploaded_files = submitted_input.files or []
            except Exception:
                uploaded_files = []
        else:
            prompt = (str(submitted_input) or "").strip()

        # Handle uploaded files — read them into session state
        for uploaded_file in uploaded_files:
            try:
                file_content = uploaded_file.read().decode("utf-8", errors="replace")
                set_session(
                    "pending_file",
                    {"name": uploaded_file.name, "content": file_content},
                )
            except Exception as exc:
                st.error(f"File read error: {exc}")

        if prompt or get_session("pending_file"):
            _send_user_message_streaming(api, prompt, None)


def _send_user_message_streaming(api: APIClient, prompt: str, streaming_placeholder) -> None:
    """Send a user message: persist + stream assistant response with optional streaming placeholder."""
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
    
    # Include file content if attached
    pending_file = get_session("pending_file")
    if pending_file:
        prompt = f"[File: {pending_file['name']}]\n{pending_file['content']}\n\n{prompt}"
        set_session("pending_file", None)  # Clear after use
    
    user_msg = {"role": "user", "content": prompt, "ts": format_timestamp(None)}
    messages.append(user_msg)
    set_session("messages", messages)

    api.add_message(conv_id, "user", prompt, importance=5)

    # Mark generation as active so the Stop button enables and the
    # streaming loops persist partial replies for interruption.
    st.session_state.streaming_active = True
    st.session_state.stop_requested = False
    st.session_state.streaming_partial = None

    # If streaming_placeholder is provided, use it for streaming; otherwise use default
    if streaming_placeholder is not None:
        _stream_response_with_placeholder(api, conv_id, messages, streaming_placeholder)
    else:
        _stream_response(api, conv_id, messages)


def _render_streaming_content(content: str) -> None:
    """Render streaming content with markdown + code highlighting."""
    if not content:
        return
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

    body_parts.append('</div></div></div>')
    full_html = "".join(body_parts)
    st.markdown(full_html, unsafe_allow_html=True)


# Regex for stripping XML-style tool_call tags from streamed content.
# The model sometimes emits inline <tool_call name="...">...</tool_call> in the
# content stream. We don't want those to leak into the user-visible message —
# they are already surfaced as separate `tool_call` events with their own
# rendered panel.
_TOOL_CALL_TAG_RE = re.compile(
    r"<tool_call\b[^>]*>.*?</tool_call>", re.DOTALL | re.IGNORECASE
)
_TOOL_CALL_SELF_CLOSING_RE = re.compile(
    r"<tool_call\b[^/>]*/>", re.IGNORECASE
)
_LEAKY_TAG_RE = re.compile(r"<tool_call\b[^>]*>(?:[^<]|<(?!/tool_call))*", re.IGNORECASE)


def _strip_tool_call_tags(text: str) -> str:
    """Remove <tool_call ...>...</tool_call> blocks from streamed content.

    The tool_call events arrive as separate SSE events with their own UI panel,
    so any inline tool_call tags in the content stream are duplicates that
    would otherwise show up as raw XML in the assistant's reply.
    """
    if not text:
        return text
    cleaned = _TOOL_CALL_TAG_RE.sub("", text)
    cleaned = _TOOL_CALL_SELF_CLOSING_RE.sub("", cleaned)
    # Catch half-typed tags (model sometimes stops mid-tag)
    cleaned = _LEAKY_TAG_RE.sub("", cleaned)
    # Collapse 3+ consecutive newlines that may result from stripping
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.rstrip()


def _render_streaming_view(
    accumulated: str,
    accumulated_reasoning: str,
    tool_calls_meta: list,
    *,
    show_thinking_panel: bool = True,
) -> str:
    """Render the full streaming view HTML — combines thinking, tool panels, and content.

    Returns a single HTML string that can be safely rendered with st.markdown.
    Sections are styled to look like ChatGPT/Claude skill indicators.
    """
    parts: list[str] = []

    # 1. Thinking panel (live reasoning, scrollable)
    if show_thinking_panel and accumulated_reasoning.strip():
        reasoning_escaped = escape_html(accumulated_reasoning[:1500])
        # Truncate cleanly at last word boundary if too long
        if len(accumulated_reasoning) > 1500:
            reasoning_escaped += "<span style='opacity:.5'>… (more)</span>"
        parts.append(
            f'<div class="wolf-thinking-panel">'
            f'<div class="wolf-tool-panel-header" style="color:#FCD34D">'
            f'<span class="wolf-tool-panel-icon">🧠</span>'
            f'<span>Thinking  |  التحليل العميق</span>'
            f'</div>'
            f'<div style="margin-top:6px; font-size:12px; line-height:1.5;">{reasoning_escaped}</div>'
            f'</div>'
        )

    # 2. Tool call panels (live, animated)
    for tc in tool_calls_meta:
        name = escape_html(str(tc.get("name", "?")))
        args_obj = tc.get("arguments", {})
        result_obj = tc.get("result", {})
        # Pretty-print arguments (truncated)
        args_str = json.dumps(args_obj, ensure_ascii=False, indent=2)[:400] if args_obj else ""
        # Pretty-print result (truncated)
        if result_obj:
            success = tc.get("success", True)
            result_class = "" if success else " wolf-tool-panel-result-error"
            result_str = json.dumps(result_obj, ensure_ascii=False, indent=2, default=str)[:600]
            result_block = (
                f'<div class="wolf-tool-panel-result{result_class}">'
                f'<strong>Result:</strong> <pre style="margin:4px 0; white-space:pre-wrap;">{escape_html(result_str)}</pre>'
                f'</div>'
            )
        else:
            result_block = ""
        parts.append(
            f'<div class="wolf-tool-panel">'
            f'<div class="wolf-tool-panel-header">'
            f'<span class="wolf-tool-panel-icon">🔧</span>'
            f'<span>Tool Call: <code style="background:rgba(168,85,247,.15); padding:2px 6px; border-radius:3px; color:#DDD6FE;">{name}</code></span>'
            f'</div>'
            f'<div class="wolf-tool-panel-body"><strong>Args:</strong> <pre style="margin:4px 0; white-space:pre-wrap;">{escape_html(args_str)}</pre></div>'
            f'{result_block}'
            f'</div>'
        )

    # 3. Main content (markdown)
    if accumulated.strip():
        # Convert accumulated to safe HTML via the renderer
        parts.append(_render_streaming_content_to_html(accumulated))

    return "\n".join(parts)


def _render_streaming_content_to_html(content: str) -> str:
    """Convert plain text content into the streaming content HTML (no markdown — safe for in-stream updates)."""
    segments = split_text_by_code(content)
    body: list[str] = ['<div class="wolf-streaming-content">']
    for seg in segments:
        if seg["type"] == "text":
            if seg["content"].strip():
                # Minimal text-to-HTML: escape and linkify code blocks inline
                body.append(f'<div>{escape_html(seg["content"]).replace(chr(10), "<br>")}</div>')
        elif seg["type"] == "code":
            lang = seg.get("lang", "text")
            code = escape_html(seg["content"])
            body.append(
                f'<div class="wolf-code-block-wrapper">'
                f'<div class="wolf-code-header">'
                f'<span class="wolf-code-lang">{lang}</span>'
                f'<span class="wolf-code-copy">copy</span>'
                f'</div>'
                f'<pre><code class="language-{lang}">{code}</code></pre>'
                f'</div>'
            )
    body.append('</div>')
    return "".join(body)


def _stream_response(api: APIClient, conv_id: str, messages: list) -> None:
    """Stream assistant response via SSE with real-time UI updates.

    PHASE 14: Now shows thinking + tool calls + content in a professional panel layout
    (see `_render_streaming_view` for details).
    """
    # Single placeholder used for the entire live region (think + tools + content)
    live_placeholder = st.empty()
    live_placeholder.markdown(
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
        unsafe_allow_html=True,
    )

    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

    accumulated = ""
    accumulated_reasoning = ""
    tool_calls_meta: list = []
    error_occurred = False
    stopped_by_user = False
    start_time = time.time()

    try:
        for event in api.stream_chat(
            api_messages,
            conversation_id=conv_id,
            auto_tools=True,
        ):
            # Stop requested via ⏹ button — halt now, keep partial reply.
            if st.session_state.get("stop_requested"):
                stopped_by_user = True
                break
            ev_type = event.get("type", "message")

            if ev_type == "token":
                chunk = event.get("chunk", "")
                # Strip any inline <tool_call> tags — those arrive as separate
                # tool_call events with their own rendered panel, so duplicates
                # in the content stream would otherwise show as raw XML.
                accumulated += _strip_tool_call_tags(chunk)
                # Hide the "Alpha Wolf is thinking..." initial header on first token
                live_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=False,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "reasoning":
                # Live reasoning — panel shows as soon as reasoning arrives
                chunk = event.get("chunk", "")
                accumulated_reasoning += chunk
                live_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=True,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "tool_call":
                name = event.get("name", "")
                args = event.get("arguments", {})
                tool_calls_meta.append(
                    {"name": name, "arguments": args, "ts": format_timestamp(None)}
                )
                live_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=True,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "tool_result":
                # Attach the result to the last tool call entry
                # FIX 2026-10-06 (Phase 46): backend emits "tool_name" via ToolResult.to_dict(),
                # not "name". Reading "name" here caused every tool name to render as "".
                name = event.get("tool_name", "") or event.get("name", "")
                output = event.get("output", {})
                success = bool(output) and not (isinstance(output, dict) and output.get("error"))
                # Merge into last matching tool_call
                merged = False
                for tc in reversed(tool_calls_meta):
                    if tc.get("name") == name and "result" not in tc:
                        tc["result"] = output
                        tc["success"] = success
                        merged = True
                        break
                if not merged:
                    tool_calls_meta.append(
                        {"name": name, "result": output, "success": success, "ts": format_timestamp(None)}
                    )
                live_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=True,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "error":
                error_occurred = True
                # FIX 2026-10-04 (Phase 41 — RC2): backend streams
                # {"error": "...", "type": "stream_error"} but we used to read
                # only "message", which made every error render as "Unknown
                # error". Accept either key so the user sees the real reason.
                error_msg = event.get("message") or event.get("error") or "Unknown error"
                accumulated += f"\n\n\u26A0\uFE0F {T['error']}: {error_msg}"
                live_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=True,
                    ),
                    unsafe_allow_html=True,
                )
                break
            elif ev_type == "restart":
                # Backend discarded the pre-tool draft (e.g. refusal text) and
                # streams the final answer fresh — reset content, keep panels.
                accumulated = ""
                accumulated_reasoning = ""
                live_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=False,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "done":
                break

            # Persist partial reply every event so Stop keeps what arrived.
            _persist_stream_partial(conv_id, accumulated, accumulated_reasoning, tool_calls_meta)

    except Exception as exc:
        error_occurred = True
        accumulated += f"\n\n\u26A0\uFE0F {T['error']}: {exc}"
        logger.exception("Stream chat failed")
        live_placeholder.markdown(
            _render_streaming_view(
                accumulated,
                accumulated_reasoning,
                tool_calls_meta,
                show_thinking_panel=True,
            ),
            unsafe_allow_html=True,
        )

    if stopped_by_user:
        # Stopped via ⏹ — finalize here (same run): keep partial reply.
        if not accumulated.strip():
            accumulated = f"⏹ {_L('agent_stopped', 'Agent stopped | تم إيقاف الوكيل')}"
        else:
            accumulated = (
                f"{accumulated}\n\n⏹ "
                + _L(
                    "agent_stopped_partial",
                    "Generation stopped by user — partial reply kept | تم إيقاف التوليد — تم الاحتفاظ بالرد الجزئي",
                )
            )

    if not accumulated.strip():
        accumulated = f"\u26A0\uFE0F {T['error']}: empty response from backend"

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Stream complete: %d chars in %dms (tools: %d)",
        len(accumulated), elapsed_ms, len(tool_calls_meta)
    )

    # Final render — show everything (thinking + tools + content)
    live_placeholder.markdown(
        _render_streaming_view(
            accumulated,
            accumulated_reasoning,
            tool_calls_meta,
            show_thinking_panel=True,
        ),
        unsafe_allow_html=True,
    )

    api.add_message(conv_id, "assistant", accumulated, importance=5)

    messages.append(
        {
            "role": "assistant",
            "content": accumulated,
            "ts": format_timestamp(None),
            "tool_calls": tool_calls_meta,
            "reasoning": accumulated_reasoning,
        }
    )
    set_session("messages", messages)
    _clear_stream_state()
    st.rerun()


def _stream_response_with_placeholder(api: APIClient, conv_id: str, messages: list, streaming_placeholder) -> None:
    """Stream assistant response via SSE with real-time UI updates using a provided placeholder.

    PHASE 14: see `_render_streaming_view` for the unified thinking/tools/content layout.
    """
    streaming_placeholder.markdown(
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
        unsafe_allow_html=True,
    )

    accumulated = ""
    accumulated_reasoning = ""
    tool_calls_meta: list = []
    error_occurred = False
    stopped_by_user = False
    start_time = time.time()

    try:
        for event in api.stream_chat(
            [{"role": m["role"], "content": m["content"]} for m in messages],
            conversation_id=conv_id,
            auto_tools=True,
        ):
            # Stop requested via ⏹ button — halt now, keep partial reply.
            if st.session_state.get("stop_requested"):
                stopped_by_user = True
                break
            ev_type = event.get("type", "message")

            if ev_type == "token":
                chunk = event.get("chunk", "")
                # Strip inline <tool_call> tags (same as _stream_response —
                # FIX 2026-09-26: raw tags previously leaked into saved replies).
                accumulated += _strip_tool_call_tags(chunk)
                streaming_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=False,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "reasoning":
                chunk = event.get("chunk", "")
                accumulated_reasoning += chunk
                streaming_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=True,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "tool_call":
                name = event.get("name", "")
                args = event.get("arguments", {})
                tool_calls_meta.append(
                    {"name": name, "arguments": args, "ts": format_timestamp(None)}
                )
                streaming_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=True,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "tool_result":
                # FIX 2026-10-06 (Phase 46): backend emits "tool_name" via ToolResult.to_dict(),
                # not "name". Reading "name" here caused every tool name to render as "".
                name = event.get("tool_name", "") or event.get("name", "")
                output = event.get("output", {})
                success = bool(output) and not (isinstance(output, dict) and output.get("error"))
                merged = False
                for tc in reversed(tool_calls_meta):
                    if tc.get("name") == name and "result" not in tc:
                        tc["result"] = output
                        tc["success"] = success
                        merged = True
                        break
                if not merged:
                    tool_calls_meta.append(
                        {"name": name, "result": output, "success": success, "ts": format_timestamp(None)}
                    )
                streaming_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=True,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "error":
                error_occurred = True
                # FIX 2026-10-04 (Phase 41 — RC2): backend streams
                # {"error": "...", "type": "stream_error"} but we used to read
                # only "message", which made every error render as "Unknown
                # error". Accept either key so the user sees the real reason.
                error_msg = event.get("message") or event.get("error") or "Unknown error"
                accumulated += f"\n\n\u26A0\uFE0F {T['error']}: {error_msg}"
                streaming_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=True,
                    ),
                    unsafe_allow_html=True,
                )
                break
            elif ev_type == "restart":
                # Backend discarded the pre-tool draft — reset content, keep panels.
                accumulated = ""
                accumulated_reasoning = ""
                streaming_placeholder.markdown(
                    _render_streaming_view(
                        accumulated,
                        accumulated_reasoning,
                        tool_calls_meta,
                        show_thinking_panel=False,
                    ),
                    unsafe_allow_html=True,
                )
            elif ev_type == "done":
                break

            # Persist partial reply every event so Stop keeps what arrived.
            _persist_stream_partial(conv_id, accumulated, accumulated_reasoning, tool_calls_meta)

    except Exception as exc:
        error_occurred = True
        accumulated += f"\n\n\u26A0\uFE0F {T['error']}: {exc}"
        logger.exception("Stream chat failed")
        streaming_placeholder.markdown(
            _render_streaming_view(
                accumulated,
                accumulated_reasoning,
                tool_calls_meta,
                show_thinking_panel=True,
            ),
            unsafe_allow_html=True,
        )

    if stopped_by_user:
        # Stopped via ⏹ — finalize here (same run): keep partial reply.
        if not accumulated.strip():
            accumulated = f"⏹ {_L('agent_stopped', 'Agent stopped | تم إيقاف الوكيل')}"
        else:
            accumulated = (
                f"{accumulated}\n\n⏹ "
                + _L(
                    "agent_stopped_partial",
                    "Generation stopped by user — partial reply kept | تم إيقاف التوليد — تم الاحتفاظ بالرد الجزئي",
                )
            )

    if not accumulated.strip():
        accumulated = f"\u26A0\uFE0F {T['error']}: empty response from backend"

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Stream complete: %d chars in %dms (tools: %d)",
        len(accumulated), elapsed_ms, len(tool_calls_meta)
    )

    # Final render
    streaming_placeholder.markdown(
        _render_streaming_view(
            accumulated,
            accumulated_reasoning,
            tool_calls_meta,
            show_thinking_panel=True,
        ),
        unsafe_allow_html=True,
    )

    api.add_message(conv_id, "assistant", accumulated, importance=5)

    messages.append(
        {
            "role": "assistant",
            "content": accumulated,
            "ts": format_timestamp(None),
            "tool_calls": tool_calls_meta,
            "reasoning": accumulated_reasoning,  # Store reasoning separately (hidden from main view)
        }
    )
    set_session("messages", messages)
    _clear_stream_state()
    st.rerun()


# ============================================================================
# MEMORY INSPECTOR PAGE (Sidebar nav)
# ============================================================================


def render_memory_page() -> None:
    """Memory Inspector page (delegated to views/ or inline)."""
    try:
        from views import memory_inspector
        memory_inspector.render()
    except Exception:
        _render_memory_inline()


def render_agent_page() -> None:
    """Agent self-awareness console (delegated to views/agent.py)."""
    try:
        from views import agent as agent_view
        agent_view.render()
    except Exception as exc:
        logger.warning("views/agent.py not available: %s", exc)
        st.error(f"{T['error']}: agent console page not found")


def render_tools_page() -> None:
    """Tools Registry page (delegated to views/ or inline)."""
    try:
        from views import tools_registry
        tools_registry.render()
    except Exception:
        _render_tools_inline()


def render_projects_page() -> None:
    """Project Awareness — list projects + body browse + live-context + tools discover."""
    # Preferred path: delegate to views/project_awareness.py if available.
    try:
        from views import project_awareness as _proj_view
        _proj_view.render()
        return
    except Exception as exc:
        logger.debug("views/project_awareness.py not used: %s", exc)

    api = get_api_client()
    st.subheader("📁 Projects Awareness | وعي المشاريع")

    # Phase 46: use APIClient methods for several endpoints to lift integration %.

    # 1. /v1/memory/goal — per-project tracking
    goals = _safe_api_call(lambda: api.list_goals(limit=20), default=[])
    if goals:
        st.markdown("### Active Goals | الأهداف النشطة")
        for g in goals[:20]:
            with st.expander(
                f"🎯 {g.get('title') or g.get('name') or g.get('id', 'goal')[:8]}"
            ):
                st.json(g, expanded=False)

    # 2. /v1/body/browse — body filesystem listing
    browse = _safe_api_call(lambda: api.body_browse(limit=30), default=None)
    if isinstance(browse, list):
        st.markdown("### Body Files | ملفات الجسم")
        for entry in browse[:30]:
            path = entry.get("path") if isinstance(entry, dict) else str(entry)
            kind = entry.get("kind", "?") if isinstance(entry, dict) else "?"
            st.markdown(f"- `{kind}` — `{path}`")
    else:
        st.info("Body browse endpoint returned an unexpected payload.")

    # 3. /v1/tools/discover — discoverable tools (Phase 46 integration)
    discovered = _safe_api_call(api.list_tools_discover, default=None)
    if discovered and isinstance(discovered, dict):
        with st.expander("🔍 Discovered Tools | الأدوات المكتشفة"):
            st.json(discovered)

    # 4. /v1/live-context/search — live project search (Phase 46 integration)
    lq = st.text_input("Live context search | بحث السياق الحي", key="proj_live_q")
    if lq:
        with st.spinner("Searching live context..."):
            live_resp = _safe_api_call(
                lambda: api.live_context_search(lq, top_k=5),
                default=None,
            )
        if live_resp:
            st.json(live_resp, expanded=False)

    # ===== Phase 48 (P1) — Live Context Injection =====
    st.markdown("### 💉 Inject Live Context | حقن السياق الحي")
    inject_q = st.text_input(
        "Query for context injection | استعلام الحقن",
        key="proj_inject_q",
        placeholder="e.g. wolf memory architecture",
    )
    inject_cols = st.columns([1, 1, 4])
    with inject_cols[0]:
        max_depth = st.number_input(
            "Max depth | عمق", min_value=1, max_value=4, value=2, key="proj_inject_depth"
        )
    with inject_cols[1]:
        top_k = st.number_input(
            "Top-K", min_value=1, max_value=10, value=3, key="proj_inject_topk"
        )
    if st.button("💉 Inject Live Context", key="proj_inject_btn"):
        if inject_q:
            with st.spinner("Injecting live context..."):
                inject_res = _safe_api_call(
                    lambda q=inject_q: api.inject_live_context(
                        q, max_depth=int(max_depth), top_k=int(top_k)
                    ),
                    default=None,
                )
            if inject_res:
                st.session_state["last_inject_result"] = inject_res
                st.json(inject_res, expanded=False)
            else:
                st.info("Inject endpoint returned no data.")
        else:
            st.warning("Enter a query first.")

    # ===== Phase 48 (P1) — RAG Job Status tracker =====
    last_job_id = st.session_state.get("last_rag_job_id")
    if last_job_id:
        st.markdown("### 📊 Last RAG Job | آخر وظيفة RAG")
        job_resp = _safe_api_call(
            lambda j=last_job_id: api.get_rag_job(j), default=None
        )
        if job_resp:
            status = job_resp.get("status", "unknown")
            progress = float(job_resp.get("progress", 0) or 0)
            st.progress(min(progress, 1.0), text=f"Status: {status} — {int(progress*100)}%")
            with st.expander("Job details", expanded=False):
                st.json(job_resp)
        else:
            st.info(f"Job '{last_job_id}' not found or expired.")


def render_health_page() -> None:
    """Body Health — chromadb / sqlite / disk / GPU / vision / cache / rope."""
    # Preferred path: delegate to views/body_health.py if available.
    try:
        from views import body_health as _health_view
        _health_view.render()
        return
    except Exception as exc:
        logger.debug("views/body_health.py not used: %s", exc)

    api = get_api_client()
    st.subheader("🏥 Body Health | صحة الجسم")

    if st.button("🔄 Refresh | تحديث", key="health_refresh"):
        st.rerun()

    health = _safe_api_call(api.body_health, default=None)
    if health and isinstance(health, dict):
        cols = st.columns(2)
        for idx, (k, v) in enumerate(health.items()):
            with cols[idx % 2]:
                st.markdown(f"**{k}**")
                st.code(json.dumps(v, ensure_ascii=False, indent=2)[:600],
                        language="json")
    else:
        st.warning("Body health endpoint not reachable.")

    # Phase 46: integrate more endpoints so the UI surfaces them.
    tab_admin, tab_vision, tab_cache, tab_rope = st.tabs(
        ["Admin", "Vision", "Cache", "RoPE"]
    )
    with tab_admin:
        status = _safe_api_call(api.admin_status if hasattr(api, "admin_status") else None,
                                default=None)
        # fallback if admin_status isn't a method
        if status is None:
            status = _safe_api_get(api, "/v1/admin/status", default=None)
        if status and isinstance(status, dict):
            st.json(status)
        else:
            st.info("Admin status unavailable.")

    with tab_vision:
        vstatus = _safe_api_call(api.vision_status, default=None)
        if vstatus:
            st.json(vstatus)
        if st.button("Run vision self-test", key="vision_test_btn"):
            vtest = _safe_api_call(api.vision_test, default=None)
            if vtest:
                st.json(vtest)

    with tab_cache:
        cstats = _safe_api_call(api.cache_stats, default=None)
        if cstats:
            st.json(cstats)
        if st.button("Clear cache", key="cache_clear_btn"):
            cres = _safe_api_call(api.cache_clear, default=None)
            if cres:
                st.success(f"Cache cleared: {cres}")

    with tab_rope:
        rope = _safe_api_call(api.rope_config, default=None)
        if rope:
            st.json(rope)
        else:
            st.info("RoPE config unavailable.")


def render_inspector_page() -> None:
    """Memory Inspector — episodes + unified recall + sessions + short-term + RAG + checkpoints."""
    # Preferred path: delegate to views/memory_inspector.py if available.
    try:
        from views import memory_inspector as _inspector_view
        _inspector_view.render()
        return
    except Exception as exc:
        logger.debug("views/memory_inspector.py not used: %s", exc)

    api = get_api_client()
    st.subheader("🔍 Memory Inspector | فحص الذاكرة")

    tab_eps, tab_recall, tab_sessions, tab_short, tab_rag, tab_ckpt = st.tabs(
        ["Episodes", "Recall", "Sessions", "Short-term", "RAG", "Checkpoints"]
    )
    with tab_eps:
        episodes = _safe_api_call(lambda: api.list_episodes(limit=20), default=[])
        if episodes:
            for ep in episodes[:20]:
                with st.expander(
                    f"🧩 {ep.get('id', 'ep')[:10]} — "
                    f"{ep.get('created_at', '')[:19] or '?'}"
                ):
                    st.json(ep, expanded=False)
        else:
            st.info("No episodes recorded.")
    with tab_recall:
        query = st.text_input("Recall query | استعلام", key="recall_q")
        if query:
            with st.spinner("Searching..."):
                resp = _safe_api_call(lambda: api.unified_recall(query, top_k=5),
                                      default=None)
            if resp:
                st.json(resp, expanded=False)
            else:
                st.warning("Recall endpoint returned no data.")
    with tab_sessions:
        sessions = _safe_api_call(api.list_sessions, default=[])
        if isinstance(sessions, list) and sessions:
            for s in sessions[:30]:
                sid = s.get("id", "?") if isinstance(s, dict) else str(s)
                st.markdown(f"- `{sid}`")
        else:
            st.info("No active sessions.")
    with tab_short:
        st.markdown("### Short-term memory | الذاكرة قصيرة المدى")
        stm = _safe_api_call(api.short_term_memory, default=None)
        if stm:
            st.json(stm, expanded=False)
        if st.button("Clear short-term", key="clear_stm_btn"):
            cleared = _safe_api_call(api.clear_short_term, default=None)
            if cleared is not None:
                st.success("Short-term memory cleared.")
    with tab_rag:
        rag_q = st.text_input("RAG query | استعلام RAG", key="rag_q")
        if rag_q:
            with st.spinner("RAG search..."):
                r = _safe_api_call(lambda: api.rag_query(rag_q, top_k=5),
                                   default=None)
            if r:
                st.json(r, expanded=False)
    with tab_ckpt:
        ckpt_conv = st.text_input("Conversation ID | معرف المحادثة",
                                  key="ckpt_conv")
        if ckpt_conv:
            ckpts = _safe_api_call(lambda: api.list_checkpoints(ckpt_conv),
                                   default=None)
            if isinstance(ckpts, list):
                for ck in ckpts[:20]:
                    with st.expander(f"📌 {ck.get('iteration', '?')}"):
                        st.json(ck, expanded=False)
            cur = _safe_api_call(lambda: api.get_checkpoint(ckpt_conv),
                                 default=None)
            if cur:
                with st.expander("Current checkpoint"):
                    st.json(cur, expanded=False)


# Helpers for the new pages — fail-soft so a missing endpoint never breaks
# the rest of the UI.
def _safe_api_get(api, path: str, default=None):
    try:
        return api.get(path)
    except Exception as exc:
        logger.debug("GET %s failed: %s", path, exc)
        return default

def _safe_api_post(api, path: str, body: dict, default=None):
    try:
        return api.post(path, json_body=body)
    except Exception as exc:
        logger.debug("POST %s failed: %s", path, exc)
        return default


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

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"\U0001F3AF {T['active_goals']}",
        f"\u26A0\uFE0F {T['recent_mistakes']}",
        f"\U0001F4A1 {T['recent_reflections']}",
        f"\U0001F4DD {T['recent_episodes']}",
        "\U0001F4CA Training Insights",
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
        safe_html('<div class="wolf-info">Reflections endpoint is POST-only - add a new one below</div>', height=60)
        st.markdown("**💭 Add a Reflection**")
        with st.form("reflection_form_inline", clear_on_submit=True):
            refl_topic = st.text_input("Topic", key="refl_topic")
            refl_insight = st.text_area("Insight", key="refl_insight", height=100)
            refl_actionable = st.text_area(
                "Actionable Next Step (optional)",
                key="refl_actionable", height=80,
            )
            if st.form_submit_button("💭 Save Reflection"):
                api = get_api_client()
                with st.spinner("POST /v1/memory/reflection ..."):
                    result = api.reflect(
                        refl_topic, refl_insight, refl_actionable
                    )
                if result and result.get("error"):
                    st.error(f"❌ {result['error']}")
                elif result:
                    st.success("✅ Reflection saved.")
                else:
                    st.warning("⚠️ No response from backend.")
                st.json(result, expanded=True)

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

    # ===== Phase 48 (P1) — Training Insights tab =====
    with tab5:
        safe_html(
            '<div class="wolf-info">📈 <b>Training Insights</b> | '
            'تحليل بيانات التدريب</div>',
            height=40,
        )
        training = _safe_api_call(api.analyze_training_data, default=None)
        if training and isinstance(training, dict):
            weaknesses = training.get("weaknesses") or training.get("issues") or []
            suggestions = training.get("suggestions") or training.get("recommendations") or []
            if isinstance(weaknesses, list) and weaknesses:
                st.markdown("**Weaknesses | نقاط الضعف:**")
                for w in weaknesses[:20]:
                    if isinstance(w, dict):
                        wtxt = w.get("topic") or w.get("description") or w.get("text") or str(w)
                    else:
                        wtxt = str(w)
                    safe_html(
                        f'<div class="wolf-tool-call" style="margin:4px 0;">'
                        f'<span>⚠️</span>'
                        f'<span style="margin-left:8px;">{escape_html(str(wtxt))}</span>'
                        f'</div>',
                        height=36,
                    )
            if isinstance(suggestions, list) and suggestions:
                st.markdown("**Suggestions | اقتراحات:**")
                for s in suggestions[:20]:
                    safe_html(
                        f'<div class="wolf-tool-call" style="margin:4px 0;">'
                        f'<span>💡</span>'
                        f'<span style="margin-left:8px;">{escape_html(str(s))}</span>'
                        f'</div>',
                        height=36,
                    )
            if not weaknesses and not suggestions:
                st.json(training, expanded=True)
        else:
            st.info("Training analyze endpoint unavailable or returned no data.")

    # ===== Phase 49 (P2) — Memory Episodes section (plural endpoint) =====
    safe_html(
        '<div class="wolf-info" style="margin-top:24px;">📜 '
        '<b>Memory Episodes</b> | الحلقات (RESTful /v1/memory/episodes)</div>',
        height=40,
    )
    mp1, mp2, mp3 = st.columns([1, 1, 4])
    with mp1:
        ep_min_imp = st.number_input(
            "Min importance",
            min_value=0,
            max_value=10,
            value=5,
            step=1,
            key="ep_min_importance",
        )
    with mp2:
        ep_limit = st.number_input(
            "Limit",
            min_value=1,
            max_value=100,
            value=20,
            step=5,
            key="ep_limit",
        )
    with mp3:
        ep_load = st.button("📜 Load Episodes", key="ep_load_btn")

    if ep_load or st.session_state.get("episodes_loaded"):
        with st.spinner("Fetching episodes..."):
            ep_data = _safe_api_call(
                lambda mi=ep_min_imp, lim=ep_limit: api.list_episodes_plural(
                    min_importance=mi, limit=lim
                ),
                default=None,
            )
        st.session_state["episodes_loaded"] = True
        if ep_data is None:
            st.error("Failed to fetch episodes — backend returned no data.")
        elif isinstance(ep_data, list) and ep_data:
            st.caption(f"Showing {len(ep_data)} episode(s) with importance ≥ {ep_min_imp}")
            for ep in ep_data[:30]:
                occurred = ep.get("occurred_at") or ep.get("created_at") or "?"
                occurred_short = str(occurred)[:10] if occurred else "?"
                trigger = ep.get("trigger_type", "?")
                importance = ep.get("importance", "?")
                content = ep.get("content", "")
                tags = ep.get("tags", [])
                title = f"📅 {occurred_short} | {trigger} | importance {importance}/10"
                with st.expander(title):
                    st.markdown(f"**ID:** `{ep.get('id', '?')}`")
                    if tags:
                        st.markdown(f"**Tags:** {', '.join(str(t) for t in tags)}")
                    st.markdown("**Content | المحتوى:**")
                    st.code(content[:1000] + ("…" if len(content) > 1000 else ""), language="text")
                    if ep.get("summary"):
                        st.markdown(f"**Summary:** {ep['summary']}")
        elif isinstance(ep_data, list) and not ep_data:
            st.info(f"No episodes with importance ≥ {ep_min_imp}.")
        else:
            st.json(ep_data, expanded=False)


# ============================================================================
# TOOLS REGISTRY PAGE (Sidebar nav)
# ============================================================================
# (Phase 35: removed duplicate render_tools_page() that shadowed the one
# defined earlier in this file. The earlier definition (which falls back to
# _render_tools_inline() on ImportError) is the canonical entry point used
# by route_page().)


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

    # ===== Phase 48 (P1) — Auto-Generated Skills section =====
    safe_html(
        '<div class="wolf-info" style="margin-top:20px;">⚡ '
        '<b>Auto-Generated Skills</b> | مهارات مُولَّدة تلقائياً</div>',
        height=40,
    )
    auto_skills = _safe_api_call(api.list_auto_skills, default=None)
    if auto_skills and isinstance(auto_skills, dict):
        skills_list = (
            auto_skills.get("skills")
            or auto_skills.get("auto_skills")
            or auto_skills.get("items")
            or []
        )
        if isinstance(skills_list, list) and skills_list:
            for sk in skills_list[:30]:
                sname = sk.get("name", "unknown") if isinstance(sk, dict) else str(sk)
                stitle = sk.get("title", "") if isinstance(sk, dict) else ""
                col1, col2 = st.columns([5, 1])
                with col1:
                    safe_html(
                        '<div class="wolf-tool-call" style="margin:4px 0;">'
                        '<span>⚡</span>'
                        f'<span style="margin-left:8px;">{escape_html(sname)}</span>'
                        + (
                            '<span style="margin-left:8px;color:var(--text-tertiary);">'
                            f'{escape_html(stitle)}</span>' if stitle else ""
                        )
                        + '</div>',
                        height=40,
                    )
                with col2:
                    if st.button("Delete", key=f"del_skill_{sname}"):
                        res = _safe_api_call(lambda n=sname: api.delete_skill(n), default=None)
                        if res and not res.get("error"):
                            st.success(f"Skill '{sname}' removed.")
                            st.rerun()
                        else:
                            st.warning(f"Could not delete '{sname}'.")
        else:
            safe_html('<div class="wolf-info">No auto-generated skills yet.</div>', height=40)
    else:
        safe_html('<div class="wolf-info">Auto-skills endpoint unavailable.</div>', height=40)

    # ===== Phase 49 (P2) — Skill Manager section (forge + install from text) =====
    safe_html(
        '<div class="wolf-info" style="margin-top:24px;">🛠️ '
        '<b>Skill Manager</b> | مدير المهارات (forge + نص)</div>',
        height=40,
    )
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📥 Install Skill from Text | تثبيت من نص**")
        with st.form("install_skill_form", clear_on_submit=False):
            install_name = st.text_input(
                "Skill name (snake_case)",
                key="install_skill_name",
                placeholder="my_custom_skill",
            )
            install_source = st.text_area(
                "Python source",
                height=180,
                key="install_skill_source",
                placeholder="def run(x: int) -> int:\n    return x * 2",
            )
            install_submit = st.form_submit_button("📥 Install")
        if install_submit:
            if not install_name or not install_source:
                st.warning("Name and source required.")
            else:
                with st.spinner("Installing skill..."):
                    res = _safe_api_call(
                        lambda n=install_name, s=install_source: api.install_skill_text(n, s),
                        default=None,
                    )
                if res and res.get("success"):
                    st.success(f"✅ Skill '{install_name}' installed!")
                    st.json(res.get("metadata") or res, expanded=False)
                elif res and res.get("error"):
                    st.error(f"❌ {res['error']}")
                else:
                    st.error("Install failed — backend returned no data.")

    with col2:
        st.markdown("**🔨 Forge Skill (Auto-Generate) | توليد تلقائي**")
        with st.form("forge_skill_form", clear_on_submit=False):
            forge_name = st.text_input(
                "Skill name",
                key="forge_skill_name",
                placeholder="auto_skill_xx",
            )
            forge_desc = st.text_area(
                "Description (AR + EN)",
                height=80,
                key="forge_skill_desc",
                placeholder="Brief description of what this skill does",
            )
            forge_template = st.text_area(
                "Code template",
                height=120,
                key="forge_skill_template",
                placeholder="def run(x: int) -> int:\n    return x * 2",
            )
            forge_submit = st.form_submit_button("🔨 Forge")
        if forge_submit:
            if not forge_name or not forge_desc or not forge_template:
                st.warning("All fields required.")
            else:
                with st.spinner("Forging skill..."):
                    res = _safe_api_call(
                        lambda n=forge_name, d=forge_desc, c=forge_template: api.forge_skill(
                            name=n, description=d, code_template=c, tags=[], auto_save=False
                        ),
                        default=None,
                    )
                if res and res.get("success"):
                    st.success(f"✅ Skill '{forge_name}' forged!")
                    if res.get("validation"):
                        st.caption(f"Validation: {res['validation']}")
                    st.json(res, expanded=False)
                elif res and res.get("error"):
                    st.error(f"❌ {res['error']}")
                else:
                    st.error("Forge failed — backend returned no data.")

    # ===== Phase 49 (P2) — Code Playground section =====
    safe_html(
        '<div class="wolf-info" style="margin-top:24px;">🧪 '
        '<b>Code Playground</b> | ملعب تنفيذ الأكواد '
        '<span style="color:var(--accent-gold);">(AST check + sandbox)</span></div>',
        height=40,
    )
    with st.form("code_playground", clear_on_submit=False):
        playground_code = st.text_area(
            "Python code",
            height=180,
            key="playground_code",
            value="# Sandbox: print, math, json, list, dict, str (no os, sys, subprocess)\n"
            "print('Wolf v8 alive!')\n"
            "import math\nprint('sqrt(2) =', round(math.sqrt(2), 4))",
        )
        pc1, pc2, pc3 = st.columns([1, 1, 4])
        with pc1:
            pc_check = st.form_submit_button("🛡️ Check Safety")
        with pc2:
            pc_run = st.form_submit_button("▶️ Execute")
        with pc3:
            pc_timeout = st.selectbox(
                "Timeout (sec)",
                options=[5, 10, 15, 20],
                index=1,
                key="playground_timeout",
            )

    if pc_check:
        with st.spinner("Running AST safety check..."):
            res = _safe_api_call(
                lambda code=playground_code: api.safety_check_code(code),
                default=None,
            )
        if res is None:
            st.error("Safety check failed — no response.")
        elif res.get("passed") is True:
            st.success("✅ Code passed safety check — safe to execute.")
        else:
            st.warning(f"⚠️ Safety violations: {res.get('violations', res.get('error', 'unknown'))}")
        st.json(res, expanded=True)

    if pc_run:
        with st.spinner(f"Executing (timeout {pc_timeout}s)..."):
            res = _safe_api_call(
                lambda code=playground_code, t=pc_timeout: api.execute_code(code, timeout_sec=t),
                default=None,
            )
        if res is None:
            st.error("Execution failed — no response.")
        elif res.get("success") is False:
            err = res.get("error") or res.get("stderr") or "Unknown error"
            st.error(f"❌ Execution failed: {err}")
        else:
            st.success("✅ Execution complete.")
            stdout = res.get("stdout", "")
            stderr = res.get("stderr", "")
            rc = res.get("returncode", "?")
            if stdout:
                st.markdown("**stdout:**")
                st.code(stdout, language="text")
            if stderr:
                st.markdown("**stderr:**")
                st.code(stderr, language="text")
            st.caption(f"returncode: {rc}")

    # ===== Phase 50 (P3) — 12 endpoints coverage: Legacy + Graph + Training =====
    safe_html(
        '<div class="wolf-info" style="margin-top:24px;">🔧 '
        '<b>P3 Coverage Tools</b> | أدوات التغطية الشاملة '
        '<span style="color:var(--accent-gold);">(Legacy · KG · Training)</span></div>',
        height=40,
    )
    tab_legacy, tab_graph, tab_training = st.tabs(
        ["Legacy APIs", "Knowledge Graph", "Training Pipeline"]
    )
    with tab_legacy:
        st.caption("⚠️ Deprecated — use v2 endpoints instead")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔧 Test Legacy Install Skill", key="btn_legacy_install"):
                api = get_api_client()
                with st.spinner("POST /v1/install_skill ..."):
                    result = api.install_skill_legacy(
                        "test_legacy", "def run(): return 42"
                    )
                st.json(result, expanded=True)
            if st.button("🔧 Test Legacy Recall", key="btn_legacy_recall"):
                api = get_api_client()
                with st.spinner("POST /v1/recall ..."):
                    result = api.recall_legacy("wolf", top_k=3)
                st.json(result, expanded=True)
        with col2:
            if st.button("🔧 Test Legacy Run Skill", key="btn_legacy_run"):
                api = get_api_client()
                with st.spinner("POST /v1/run_skill ..."):
                    result = api.run_skill_legacy("brainstorming", {})
                st.json(result, expanded=True)
            if st.button("🔧 Test Skills Install v2", key="btn_skills_install_v2"):
                api = get_api_client()
                with st.spinner("POST /v1/skills/install ..."):
                    result = api.install_skill_v2(
                        "test_v2", "def run(): return 42"
                    )
                st.json(result, expanded=True)

    with tab_graph:
        st.caption("📊 Knowledge Graph (NetworkX)")
        with st.form("add_entity_form", clear_on_submit=True):
            ent_name = st.text_input("Entity Name", key="ent_name")
            ent_type = st.text_input(
                "Type (e.g., concept, tool, agent)", key="ent_type"
            )
            ent_desc = st.text_area("Description", key="ent_desc")
            if st.form_submit_button("➕ Add Entity"):
                api = get_api_client()
                with st.spinner("POST /v1/graph/entity ..."):
                    result = api.add_graph_entity(ent_name, ent_type, ent_desc)
                st.json(result, expanded=True)

        with st.form("add_relation_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                src = st.text_input("Source", key="rel_src")
            with c2:
                tgt = st.text_input("Target", key="rel_tgt")
            rel_type = st.text_input(
                "Relation Type", value="related", key="rel_type"
            )
            if st.form_submit_button("🔗 Add Relation"):
                api = get_api_client()
                with st.spinner("POST /v1/graph/relation ..."):
                    result = api.add_graph_relation(src, tgt, rel_type)
                st.json(result, expanded=True)

    with tab_training:
        st.caption("📈 Self-Improvement Pipeline (LoRA training)")

        st.markdown("**📦 Export Training Data**")
        c1, c2 = st.columns(2)
        with c1:
            min_score = st.number_input(
                "Min Score", min_value=0.0, max_value=10.0,
                value=7.0, step=0.5, key="train_min_score",
            )
        with c2:
            limit = st.number_input(
                "Limit", min_value=1, max_value=1000,
                value=100, step=10, key="train_limit",
            )
        if st.button("📤 Export to JSONL", key="btn_export_training"):
            api = get_api_client()
            with st.spinner("POST /v1/training/export ..."):
                result = api.export_training_data(min_score, limit)
            st.json(result, expanded=True)

        st.markdown("**🎯 Trigger Training Round**")
        st.warning(
            "⚠️ Requires ALPHA_WOLF_TRAIN_TOKEN env var on backend. "
            "Without a valid token, expect 401/403."
        )
        c1, c2 = st.columns(2)
        with c1:
            train_epochs = st.number_input(
                "Epochs", min_value=1, max_value=10,
                value=1, step=1, key="train_epochs",
            )
        with c2:
            train_adapter = st.text_input(
                "Adapter Name", value="v_self_improve", key="train_adapter_name",
            )
        train_token = st.text_input(
            "Confirm Token (from env)", type="password", key="train_token",
        )
        if st.button("🚀 Start Training", key="btn_start_training"):
            api = get_api_client()
            with st.spinner("POST /v1/training/train ..."):
                result = api.trigger_training(
                    adapter_name=train_adapter,
                    epochs=int(train_epochs),
                    confirm_token=train_token if train_token else None,
                )
            st.json(result, expanded=True)

        st.markdown("**🧩 Body Tools (Internal)**")
        if st.button("🔍 GET /v1/body/tools", key="btn_body_tools"):
            api = get_api_client()
            with st.spinner("GET /v1/body/tools ..."):
                result = api.body_tools(action="list")
            st.json(result, expanded=True)


# ============================================================================
# HELPERS
# ============================================================================


def escape_html(text: str) -> str:
    """Escape HTML special characters for safe rendering."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(chr(34), "&quot;")
        .replace(chr(39), "&#x27;")
    )


def route_page() -> None:
    """Route to the selected page using canonical page names."""
    import sys
    page = get_canonical_page()
    # PHASE 11+ v4.2 FIX (Bug #1 — sidebar pages not rendering):
    # Strip emoji prefix from page name for comparison (CANONICAL_PAGES uses
    # emojis as visual prefixes but routing should match the canonical key).
    page_key = page.split(" ", 1)[-1] if " " in page else page

    # PHASE 35 FIX (Bug — double-render of chat fallback):
    # The previous else clause called render_chat_page() twice in a row and
    # also set session_state.page to "Chat" before the second render. This
    # caused the chat UI to render twice per rerun (visible flicker + waste).
    # Now: route ONCE, and only fall back to chat if no canonical key matches.
    if page_key == "Chat" or page == "Chat":
        render_chat_page()
    elif page_key == "Agent" or page == "Agent":
        render_agent_page()
    elif page_key == "Memory" or page == "Memory":
        render_memory_page()
    elif page_key == "Tools" or page == "Tools":
        render_tools_page()
    elif page_key == "Projects" or page == "Projects":
        render_projects_page()
    elif page_key == "Health" or page == "Health":
        render_health_page()
    elif page_key == "Inspector" or page == "Inspector":
        render_inspector_page()
    else:
        # Unknown page — fall back to chat (single render).
        set_canonical_page("Chat")
        render_chat_page()


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Main entry point."""
    init_all_session_state()
    # Finalize a stream interrupted via Stop (persists the partial reply).
    _finalize_stopped_stream()
    render_topbar()
    render_sidebar()
    # PHASE 51 — semantic <main> wrapper for WCAG 4.1.2 (Name, Role, Value).
    # The skip-link target sits on this element.
    st.markdown(
        '<main id="main-content" role="main" aria-label="Alpha Wolf Agent main content" '
        'style="display:block;">',
        unsafe_allow_html=True,
    )
    route_page()
    st.markdown("</main>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
