#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Tools Registry Page
=======================================
Browse, filter, and test Alpha Wolf's tools.

Features:
- List tools grouped by category
- Try tool: execute tool with custom arguments (interactive)
- Tool count + invocation stats
- Bilingual labels (Iron Law #47)

Iron Laws:
- #15 Verify: tools tested against live backend
- #41 Conflict: clear messaging for backend offline
- #47 Bilingual
- #48 Separated: tools_registry-only code
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
from utils import T, get_api_client, get_backend_status

logger = logging.getLogger("alpha_wolf_tools_registry_page")


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
            <h1>🛠️ {T['nav_tools']}</h1>
            <p>Browse, filter, and test Alpha Wolf's tools | تصفح واختبر أدوات الذئب</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fetch tools + categories
    tools_data = api.list_tools()
    categories = api.tool_categories() or {}

    if not tools_data:
        st.error(f"{T['error']}: cannot load tools")
        return

    tools = tools_data.get("tools", [])
    total = tools_data.get("count", len(tools))

    # Top metrics
    cols = st.columns([2, 1, 4])
    with cols[0]:
        st.markdown(
            f"""
            <div class="wolf-metric-card">
                <div style="font-size: 1.5rem;">🛠️</div>
                <div class="wolf-metric-value">{total}</div>
                <div class="wolf-metric-label">{T['tools_total']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f"""
            <div class="wolf-metric-card">
                <div style="font-size: 1.5rem;">📂</div>
                <div class="wolf-metric-value">{len(categories)}</div>
                <div class="wolf-metric-label">{T['tools_categories']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Filter by category
    category_filter = st.selectbox(
        "Filter by category | تصفية حسب الفئة",
        ["All"] + sorted(categories.keys()),
        key="tools_cat_filter",
    )

    if category_filter != "All":
        tools = [t for t in tools if t.get("category") == category_filter]

    # Tool cards
    st.markdown("---")
    st.markdown(f"### 🛠️ Available Tools | الأدوات المتاحة")

    for tool in tools:
        _render_tool_card(api, tool)


def _render_tool_card(api, tool: dict) -> None:
    name = tool.get("name", "unknown")
    description = tool.get("description", "No description")
    category = tool.get("category", "general")
    invocation = tool.get("invocation", "")
    invocation_count = tool.get("invocation_count", 0)

    # Category emoji
    cat_emoji = {
        "filesystem": "📁",
        "compute": "⚙️",
        "network": "🌐",
        "memory": "🧠",
        "general": "🔧",
    }.get(category, "🔧")

    with st.expander(
        f"{cat_emoji} **{name}** · {category} · invocations: {invocation_count}"
    ):
        st.markdown(f"**{T['tool_description']}:** {description}")

        if invocation:
            st.markdown(f"**{T['tool_invocation']}:**")
            st.code(invocation, language="python")

        # Try tool form
        with st.form(key=f"try_tool_form_{name}"):
            st.markdown(f"**🔬 {T['try_tool']}**")

            # Try to parse invocation for default args
            default_args = "{}"
            if invocation and "=" in invocation:
                # Heuristic: extract param names from invocation
                try:
                    import re
                    params = re.findall(r"(\w+)\s*[:=]", invocation)
                    if params:
                        default_args = "{\n" + ",\n".join(f'  "{p}": "..."' for p in params) + "\n}"
                except Exception:
                    pass

            args_text = st.text_area(
                "Arguments (JSON) | المعاملات (JSON)",
                value=default_args,
                height=120,
                key=f"args_{name}",
            )

            submitted = st.form_submit_button(
                f"▶️ Execute | تنفيذ",
                type="primary",
            )

            if submitted:
                try:
                    args_dict = json.loads(args_text) if args_text.strip() else {}
                except json.JSONDecodeError as exc:
                    st.error(f"Invalid JSON: {exc}")
                    return

                with st.spinner(T["loading"]):
                    result = api.execute_tool(name, args_dict)

                if result:
                    success = result.get("success", True)
                    output = result.get("output", result.get("result", ""))

                    if success:
                        st.success(f"✓ {T['tool_result']}")
                        # Pretty-print if dict/list
                        if isinstance(output, (dict, list)):
                            st.json(output)
                        else:
                            st.code(str(output))
                    else:
                        st.error(f"✗ {T['error']}")
                        st.code(str(output))
                else:
                    st.error(f"✗ {T['error']}: no response from backend")
