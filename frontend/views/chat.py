#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Chat Page (ChatGPT Desktop Style)
=====================================================

Main chat interface with streaming, tool calls, code highlighting, file upload.
Updated for Phase 14+ (ChatGPT desktop style rewrite).

Iron Laws Applied:
- #22 (Autonomous) — no questions asked
- #33 (Lessons -> Code) — clean modular architecture
- #41 (Conflict Disclosure) — backend offline fallback visible
- #47 (Bilingual) — every label is AR + EN
- #48 (Separated) — delegated to streamlit_preview.py for most logic
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
    format_timestamp,
    truncate,
)

logger = logging.getLogger("alpha_wolf_chat_page")

# ============================================================================
# Render — Delegate to streamlit_preview.py inline implementation
# ============================================================================


def render() -> None:
    """Render the chat page.

    Note: This delegates to streamlit_preview.py's _render_chat_inline()
    to keep the chat logic in ONE place (Iron Law #48 — Separated).
    """
    try:
        # Lazy import to avoid circular dependencies
        from streamlit_preview import _render_chat_inline
        _render_chat_inline()
    except ImportError as exc:
        logger.error("streamlit_preview not available: %s", exc)
        st.error(f"{T.get('error', 'Error')}: chat module not found")


if __name__ == "__main__":
    render()
