#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Chat Page
=============================
Main chat interface with streaming, tool calls, code highlighting, file upload.

Features:
- Server-Sent Events (SSE) streaming from /v1/chat/stream
- Tool call display (collapsible)
- Code block syntax highlighting
- Multi-turn conversation via /v1/conversations
- File upload (attached to message)
- Bilingual labels (Iron Law #47)
- Auto-create conversation on first message (Iron Law #33 fallback)
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Project setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

# Frontend utils (sibling to pages/)
sys.path.insert(0, str(PROJECT_ROOT / "frontend"))
from utils import (
    T,
    get_api_client,
    get_session,
    set_session,
    get_backend_status,
    format_timestamp,
    truncate,
    split_text_by_code,
)

logger = logging.getLogger("alpha_wolf_chat_page")


# ============================================================================
# Render
# ============================================================================


def render() -> None:
    """Render the main chat interface."""
    api = get_api_client()
    is_online, _ = get_backend_status()

    if not is_online:
        st.error(
            f"""
            ⚠️ **{T['error']}** — Backend is offline.

            Start it with:
            ```
            python -m uvicorn backend.main:app --port 8001
            ```
            """
        )
        return

    messages = get_session("messages", [])
    conv_id = get_session("active_conversation_id")

    # Welcome screen if no conversation active
    if not messages and not conv_id:
        _render_welcome_inline()
    else:
        # Show conversation context
        if conv_id:
            st.caption(f"💬 {truncate(conv_id, 12)} · {len(messages)} messages")

    # Message history
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        ts = msg.get("ts") or msg.get("created_at")
        tool_calls = msg.get("tool_calls") or []

        if role == "user":
            with st.chat_message("user", avatar="🙋"):
                st.markdown(content)
                if ts:
                    st.caption(f"_{format_timestamp(ts)}_")
        elif role == "assistant":
            with st.chat_message("assistant", avatar=T["wolf_emoji"]):
                _render_message_content(content)
                for tc in tool_calls:
                    _render_tool_call(tc)
                if ts:
                    st.caption(f"_{format_timestamp(ts)}_")

    # Process pending prompt (from welcome buttons)
    pending_prompt = get_session("pending_prompt")
    if pending_prompt:
        set_session("pending_prompt", None)
        _send_user_message(api, pending_prompt)
        return

    # Chat input with file uploader
    _render_input_area(api)


# ============================================================================
# Welcome screen
# ============================================================================


def _render_welcome_inline() -> None:
    """Welcome screen with quick-action buttons."""
    api = get_api_client()
    health = api.body_health()

    st.markdown(
        f"""
        <div class="wolf-header-gradient">
            <h1>{T['wolf_emoji']} {T['app_name']}</h1>
            <p>{T['app_tagline']} · {T['app_tagline_ar']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if health:
        cols = st.columns(4)
        metrics = [
            (health["chromadb"]["collections"], T["chromadb_collections"], "📚"),
            (health["networkx"]["nodes"], T["networkx_nodes"], "🕸️"),
            (health["networkx"]["edges"], T["networkx_edges"], "🔗"),
            (len(health["sqlite"]["tables"]), T["sqlite_tables"], "💾"),
        ]
        for col, (value, label, icon) in zip(cols, metrics):
            with col:
                st.markdown(
                    f"""
                    <div class="wolf-metric-card">
                        <div style="font-size: 1.5rem;">{icon}</div>
                        <div class="wolf-metric-value">{value}</div>
                        <div class="wolf-metric-label">{label}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    st.markdown(f"### 🎯 Quick Start | بداية سريعة")

    prompts = [
        ("🔍", T["trait_mistake_hunter"],
         "Show me your 3 most recent mistakes and what you learned from each."),
        ("🎯", T["trait_goal_persistence"],
         "What are your active goals right now and what's the next step?"),
        ("🧠", T["trait_deep_thinking"],
         "Reflect on the most important insight from the last 24 hours."),
        ("💪", T["trait_tenacity"],
         "Tell me about a time you failed and how you recovered."),
        ("🛠️", T["trait_resourceful"],
         "List the top 5 tools you have available and give me an example use case."),
        ("👁️", T["trait_self_aware"],
         "Summarize your current state — what you know, what you're learning, and what's next."),
    ]

    cols = st.columns(2)
    for i, (emoji, label, prompt) in enumerate(prompts):
        with cols[i % 2]:
            if st.button(f"{emoji} {label}", key=f"welcome_btn_{i}", use_container_width=True):
                set_session("pending_prompt", prompt)
                st.rerun()

    st.markdown(
        f"""
        <div class="wolf-empty-state">
            <div class="wolf-empty-state-icon">{T['wolf_emoji']}</div>
            <div class="wolf-empty-state-text">{T['chat_placeholder']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# Input area
# ============================================================================


def _render_input_area(api) -> None:
    """Render chat input + optional file upload."""
    # Optional file uploader (compact, above chat input)
    with st.expander(f"📎 {T['upload_file']}", expanded=False):
        st.caption(T["upload_tooltip"])
        uploaded_file = st.file_uploader(
            T["upload_file"],
            type=["txt", "md", "py", "json", "yaml", "yml", "csv", "log"],
            label_visibility="collapsed",
            key="file_uploader",
        )
        if uploaded_file:
            try:
                content = uploaded_file.read().decode("utf-8", errors="replace")
                set_session("uploaded_file_content", content)
                set_session("uploaded_file_name", uploaded_file.name)
                st.success(f"✓ {uploaded_file.name} ({len(content)} chars)")
            except Exception as exc:
                st.error(f"{T['error']}: {exc}")

    # Chat input (Streamlit native)
    user_input = st.chat_input(
        T["chat_placeholder"],
        key=f"chat_input_{len(get_session('messages', []))}",
    )

    if user_input:
        # Augment with uploaded file content if any
        file_content = get_session("uploaded_file_content")
        file_name = get_session("uploaded_file_name")
        if file_content and file_name:
            user_input = (
                f"{user_input}\n\n---\n"
                f"📎 **Attached file | ملف مرفق**: `{file_name}`\n"
                f"```\n{file_content[:8000]}\n```"
            )
            set_session("uploaded_file_content", None)
            set_session("uploaded_file_name", None)
        _send_user_message(api, user_input)


# ============================================================================
# Send / stream
# ============================================================================


def _send_user_message(api, prompt: str) -> None:
    """Send user message and stream assistant response."""
    # Ensure active conversation
    conv_id = get_session("active_conversation_id")
    if not conv_id:
        conv = api.create_conversation(title=truncate(prompt, 50))
        if conv and "conversation_id" in conv:
            conv_id = conv["conversation_id"]
            set_session("active_conversation_id", conv_id)
        else:
            st.error(f"{T['error']}: cannot create conversation")
            return

    # Append to session
    messages = get_session("messages", [])
    user_msg = {"role": "user", "content": prompt, "ts": format_timestamp(None)}
    messages.append(user_msg)
    set_session("messages", messages)

    # Persist user message
    api.add_message(conv_id, "user", prompt, importance=5)

    # Render user message immediately
    with st.chat_message("user", avatar="🙋"):
        st.markdown(prompt)

    # Stream assistant response
    _stream_response(api, conv_id, messages)


def _stream_response(api, conv_id: str, messages: list[dict]) -> None:
    """Stream assistant response via SSE."""
    with st.chat_message("assistant", avatar=T["wolf_emoji"]):
        placeholder = st.empty()
        accumulated = ""
        tool_calls_meta = []
        error_occurred = False
        start_time = time.time()

        # Build API messages (exclude ts field)
        api_messages = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]

        # Show thinking indicator
        with placeholder.container():
            st.markdown(
                f'<span class="wolf-thinking-pulse">🐺 {T["thinking"]}</span>',
                unsafe_allow_html=True,
            )

        # Stream from backend
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
                    with placeholder.container():
                        _render_message_content(accumulated)

                elif ev_type == "tool_call":
                    name = event.get("name", "")
                    args = event.get("arguments", {})
                    duration = event.get("duration_ms")
                    tool_calls_meta.append(
                        {
                            "name": name,
                            "arguments": args,
                            "duration_ms": duration,
                        }
                    )
                    accumulated += f"\n\n🔧 **{T['tool_calling']}: `{name}`**"
                    if args:
                        accumulated += f"\n```json\n{str(args)[:500]}\n```"
                    accumulated += "\n"
                    with placeholder.container():
                        _render_message_content(accumulated)
                        for tc in tool_calls_meta:
                            _render_tool_call(tc)

                elif ev_type == "tool_result":
                    name = event.get("name", "")
                    output = event.get("output", {})
                    success = event.get("success", True)
                    tool_calls_meta.append(
                        {
                            "name": name,
                            "result": output,
                            "success": success,
                        }
                    )
                    icon = "✅" if success else "❌"
                    accumulated += f"\n{icon} **Result**: `{name}`\n"
                    with placeholder.container():
                        _render_message_content(accumulated)

                elif ev_type == "error":
                    error_occurred = True
                    error_msg = event.get("message", "Unknown error")
                    accumulated += f"\n\n⚠️ {T['error']}: {error_msg}"
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
            logger.exception("Stream chat failed")

        # If still empty, show error
        if not accumulated.strip():
            accumulated = f"⚠️ {T['error']}: empty response from backend"
            with placeholder.container():
                _render_message_content(accumulated)

        elapsed = int((time.time() - start_time) * 1000)

        # Persist assistant message
        api.add_message(
            conv_id,
            "assistant",
            accumulated,
            importance=5,
        )

    # Update session messages
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
# Render helpers
# ============================================================================


def _render_message_content(content: str) -> None:
    """Render content with markdown + code blocks."""
    segments = split_text_by_code(content)
    for seg in segments:
        if seg["type"] == "text":
            if seg["content"].strip():
                st.markdown(seg["content"])
        elif seg["type"] == "code":
            lang = seg.get("lang", "text")
            st.code(seg["content"], language=lang if lang != "text" else None)


def _render_tool_call(tc: dict) -> None:
    """Render a tool call inline."""
    name = tc.get("name", "unknown")
    args = tc.get("arguments", {})
    result = tc.get("result")
    duration = tc.get("duration_ms")
    success = tc.get("success", True)

    # Header
    st.markdown(
        f"""
        <div class="wolf-tool-call">
            <div class="wolf-tool-call-header">🔧 {T['tool_calling']}: <code>{name}</code></div>
        """,
        unsafe_allow_html=True,
    )
    if args:
        st.markdown(
            f'<div class="wolf-tool-call-input"><strong>Input:</strong> <code>{str(args)[:500]}</code></div>',
            unsafe_allow_html=True,
        )

    # Result
    if result is not None:
        cls = "wolf-tool-result" if success else "wolf-tool-result wolf-tool-result-error"
        st.markdown(
            f'<div class="{cls}"><strong>{T["tool_result"]}:</strong> <code>{str(result)[:500]}</code></div>',
            unsafe_allow_html=True,
        )

    if duration is not None:
        st.markdown(
            f'<div style="font-size: 0.75rem; color: #6b7280; margin-top: 4px;">⏱ {T["tool_duration"]}: {duration}ms</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
