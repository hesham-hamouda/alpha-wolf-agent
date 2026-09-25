#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Body Health Page
====================================
Visualizes the Alpha Wolf body state:
- ChromaDB collections + counts
- NetworkX knowledge graph (nodes/edges)
- SQLite tables + sizes
- zvec embeddings status
- Disk usage
- Self-summary (Wolf Trait #6)
- Backup trigger

Iron Laws:
- #15 Verify: live data only, no mocks
- #41 Conflict: clear messaging when backend offline
- #47 Bilingual: every label AR + EN
"""

from __future__ import annotations

import logging
import sys
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
)

logger = logging.getLogger("alpha_wolf_body_health_page")


def render() -> None:
    api = get_api_client()
    is_online, _ = get_backend_status()

    if not is_online:
        st.error(
            f"⚠️ {T['error']}: Backend offline — start with `python -m uvicorn backend.main:app --port 8001`"
        )
        return

    # Header
    st.markdown(
        f"""
        <div class="wolf-header-gradient">
            <h1>📊 {T['body_status']}</h1>
            <p>Real-time body state across ChromaDB, NetworkX, SQLite, zvec | حالة الجسم الحية</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Refresh + backup actions
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button(f"🔄 {T['refresh']}", use_container_width=True):
            st.rerun()
    with col2:
        if st.button(f"💾 {T['create_backup']}", use_container_width=True):
            with st.spinner(T["loading"]):
                result = api.create_backup()
                if result and "backup_path" in result:
                    st.success(f"✓ {T['backup_created']}: `{result['backup_path']}`")
                else:
                    st.error(f"{T['error']}: backup failed")

    st.markdown("---")

    # Fetch health
    health = api.body_health()
    if not health:
        st.error(f"{T['error']}: cannot fetch body health")
        return

    # Section: Vector DB + Knowledge Graph
    st.markdown(f"### 🧬 Vector Database + Knowledge Graph | قاعدة البيانات المتجهة + خريطة المعرفة")
    cols = st.columns(4)
    with cols[0]:
        _metric_card(
            health["chromadb"]["collections"],
            T["chromadb_collections"],
            "📚",
        )
    with cols[1]:
        _metric_card(
            health["networkx"]["nodes"],
            T["networkx_nodes"],
            "🕸️",
        )
    with cols[2]:
        _metric_card(
            health["networkx"]["edges"],
            T["networkx_edges"],
            "🔗",
        )
    with cols[3]:
        status_ok = "✅" if health["zvec"]["ok"] else "❌"
        _metric_card(
            status_ok,
            T["zvec_status"],
            "🔍",
        )

    # Section: SQLite + Disk
    st.markdown(f"### 💾 SQLite + Disk Usage | SQLite + استخدام القرص")
    cols = st.columns(4)
    with cols[0]:
        _metric_card(
            len(health["sqlite"]["tables"]),
            T["sqlite_tables"],
            "📋",
        )
    with cols[1]:
        _metric_card(
            f"{health['sqlite']['size_mb']:.2f} MB",
            T["sqlite_size"],
            "💿",
        )
    with cols[2]:
        _metric_card(
            health["sqlite"]["integrity"],
            T["integrity"],
            "🛡️",
        )
    with cols[3]:
        disk = health.get("disk_usage", {})
        disk_mb = disk.get("size_mb", 0)
        _metric_card(
            f"{disk_mb:.2f} MB",
            T["disk_usage"],
            "📀",
        )

    # SQLite tables detail
    with st.expander(f"📋 SQLite Tables Detail | تفاصيل جداول SQLite"):
        tables = health["sqlite"].get("tables", [])
        if tables:
            st.write(f"**{len(tables)} tables found:**")
            cols_per_row = 4
            for i in range(0, len(tables), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, tname in enumerate(tables[i : i + cols_per_row]):
                    with cols[j]:
                        st.code(f"📄 {tname}", language=None)

    # Section: Self-Summary (Wolf Trait #6 — Self-Aware)
    st.markdown(f"### 👁️ {T['wolf_self_summary']}")
    with st.spinner(T["loading"]):
        summary = api.self_summary()

    if summary:
        # Pretty-print key fields
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Model | النموذج:**")
            model_name = summary.get("model", summary.get("name", "alpha-wolf-agent"))
            st.code(str(model_name))

            if "version" in summary:
                st.markdown("**Version | الإصدار:**")
                st.code(str(summary["version"]))

            if "phase" in summary:
                st.markdown("**Phase | المرحلة:**")
                st.code(str(summary["phase"]))

        with col2:
            if "training_mix" in summary or "training" in summary:
                st.markdown(f"**{T['training_mix']}:**")
                mix = summary.get("training_mix", summary.get("training", {}))
                st.json(mix)

        # Wolf traits
        if "wolf_traits" in summary:
            st.markdown("### 🐺 Wolf Traits | صفات الذئب")
            traits = summary["wolf_traits"]
            cols = st.columns(7)
            for i, (trait_name, trait_data) in enumerate(list(traits.items())[:7]):
                with cols[i]:
                    emoji = trait_data.get("emoji", "🐺") if isinstance(trait_data, dict) else "🐺"
                    strength = trait_data.get("strength", 1) if isinstance(trait_data, dict) else 1
                    st.markdown(
                        f"""
                        <div class="wolf-metric-card">
                            <div style="font-size: 1.5rem;">{emoji}</div>
                            <div style="font-size: 0.85rem; font-weight: 600;">{trait_name}</div>
                            <div style="font-size: 0.75rem; color: var(--wolf-text-muted);">×{strength}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # Full summary (raw)
        with st.expander("📄 Raw JSON | JSON خام"):
            st.json(summary)
    else:
        st.warning("Self-summary not available")

    # Section: Live Status Indicator
    st.markdown("---")
    st.markdown(f"### ⚡ Status Indicator | مؤشر الحالة")
    st.success(
        f"✅ Body is operational | الجسم يعمل · {T['integrity']}: {health['sqlite']['integrity']}"
    )
    st.caption(f"Last check: {format_timestamp(health.get('timestamp'))}")


def _metric_card(value, label, icon) -> None:
    """Render a metric card using custom CSS."""
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
