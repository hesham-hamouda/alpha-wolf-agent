#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Chat Page (Standalone Module)
================================================

Minimal chat renderer that works WITHOUT importing streamlit_preview.
Previously this module tried to import streamlit_preview._render_chat_inline,
which created a circular import (streamlit_preview.render_chat_page also
imported from views/chat) and caused a double-render bug (Phase 35 fix).

Iron Laws Applied:
- #22 (Autonomous) — no questions asked
- #33 (Lessons -> Code) — clean modular architecture
- #41 (Conflict Disclosure) — backend offline fallback visible
- #47 (Bilingual) — every label is AR + EN
- #48 (Separated) — standalone, no circular dependency
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

# Frontend utils
sys.path.insert(0, str(PROJECT_ROOT / "frontend"))
from utils import (
    T,
    get_api_client,
    get_backend_status,
)

logger = logging.getLogger("alpha_wolf_chat_page_standalone")


def render() -> None:
    """Standalone chat renderer (no circular dependency).

    رندر مستقل للدردشة (بدون اعتماد دائري).

    The production UI in streamlit_preview.py now uses _render_chat_inline()
    directly. This module is kept as a callable entrypoint for scripts that
    want to embed a minimal chat UI (e.g., `python -m frontend.views.chat`).
    """
    api = get_api_client()
    is_online, _ = get_backend_status()

    if not is_online:
        st.error(
            f"{T.get('error_backend_offline', 'Backend offline')}: "
            f"Start with `python backend/run_server.py`"
        )
        return

    messages = st.session_state.get("messages", [])
    conv_id = st.session_state.get("active_conversation_id")

    # Render message history
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            with st.chat_message("user", avatar="\U0001F64B"):
                st.markdown(content)
        elif role == "assistant":
            with st.chat_message("assistant", avatar="\U0001F43A"):
                st.markdown(content)

    # Chat input (non-streaming fallback)
    if prompt := st.chat_input(T.get("chat_placeholder", "Message Alpha Wolf...")):
        if not conv_id:
            conv = api.create_conversation()
            if conv and "conversation_id" in conv:
                st.session_state.active_conversation_id = conv["conversation_id"]
                conv_id = conv["conversation_id"]
        if conv_id:
            st.session_state.messages = messages + [
                {"role": "user", "content": prompt, "ts": None}
            ]
            api.add_message(conv_id, "user", prompt)
            # Simple non-streaming response for standalone mode
            resp = api.chat([{"role": "user", "content": prompt}])
            if resp and "choices" in resp:
                answer = resp["choices"][0]["message"]["content"]
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "ts": None}
                )
                api.add_message(conv_id, "assistant", answer)
            st.rerun()


if __name__ == "__main__":
    render()