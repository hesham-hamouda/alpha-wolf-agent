#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Project Awareness Page
==========================================
Visualizes Alpha Wolf's understanding of the current project folder:
- Project summary (file counts, recent files)
- RAG (Retrieval-Augmented Generation) stats
- Index management (refresh, force re-index)
- Live context injection status

This is the "Alpha Wolf knows what's in your project" page — directly tied
to /v1/live-context/* and /v1/rag/* endpoints.

Iron Laws:
- #15 Verify: live data only
- #41 Conflict: clear messaging for backend offline
- #47 Bilingual
- #48 Separated
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

sys.path.insert(0, str(PROJECT_ROOT / "frontend"))
from utils import T, get_api_client, get_backend_status, format_timestamp

logger = logging.getLogger("alpha_wolf_project_awareness_page")


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
            <h1>📁 {T['nav_project']}</h1>
            <p>Alpha Wolf's awareness of your project folder | وعي الذئب بمجلد المشروع</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Section 1: Live Context Summary
    st.markdown(f"### 🧭 {T['live_context_summary']}")

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(f"🔄 {T['refresh']}", key="lc_refresh", use_container_width=True):
            st.rerun()

    with st.spinner(T["loading"]):
        lc = api.live_context_summary()

    if lc:
        _render_live_context(lc)
    else:
        st.warning("Live context not available")

    st.markdown("---")

    # Section 2: RAG Stats
    st.markdown(f"### 📊 {T['rag_stats']}")
    rag = api.rag_stats()
    if rag:
        cols = st.columns(4)
        # Try common keys
        total_chunks = rag.get("total_chunks", rag.get("chunks", 0))
        total_docs = rag.get("total_documents", rag.get("documents", 0))
        collection = rag.get("collection_name", rag.get("collection", "—"))
        embedding_model = rag.get("embedding_model", rag.get("model", "—"))

        with cols[0]:
            _metric_card(total_chunks, "Total Chunks | القطع", "📦")
        with cols[1]:
            _metric_card(total_docs, "Total Documents | المستندات", "📄")
        with cols[2]:
            _metric_card(collection, "Collection | المجموعة", "🗂️")
        with cols[3]:
            _metric_card(embedding_model, "Embedding Model | النموذج", "🤖")

        # Raw stats
        with st.expander("📄 Raw RAG Stats | إحصائيات خام"):
            st.json(rag)
    else:
        st.info("RAG stats not available")

    st.markdown("---")

    # Section 3: Index Management
    st.markdown(f"### 🔄 Index Management | إدارة الفهرسة")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"📥 {T['index_now']}", use_container_width=True, type="primary"):
            with st.spinner("Indexing... | جاري الفهرسة (قد تستغرق بضع دقائق)..."):
                result = api.rag_index(force=False)
                if result:
                    indexed = result.get("indexed", {})
                    if isinstance(indexed, dict):
                        st.success(
                            f"✓ Indexed {sum(indexed.values())} files | "
                            f"تمت فهرسة {sum(indexed.values())} ملفات"
                        )
                    else:
                        st.success(f"✓ {result}")
                else:
                    st.error(f"{T['error']}: index failed")
    with col2:
        if st.button(f"🔃 Force Re-index | إعادة الفهرسة الكاملة", use_container_width=True):
            with st.spinner("Force re-indexing... | إعادة الفهرسة الكاملة..."):
                result = api.rag_index(force=True)
                if result:
                    st.success("✓ Force re-index complete | تمت إعادة الفهرسة")
                else:
                    st.error(f"{T['error']}: index failed")
    with col3:
        st.caption("⚠️ Re-indexing is slow | إعادة الفهرسة بطيئة")

    st.markdown("---")

    # Section 4: Project Folder (Live Context)
    if lc and isinstance(lc, dict):
        project_root = lc.get("project_root") or lc.get("root")
        if project_root:
            st.markdown(f"### 📂 {T['project_folder']}")
            st.code(project_root, language=None)

        recent = lc.get("recent_files", [])
        if recent:
            st.markdown(f"### 📅 Recent Files | الملفات الحديثة")
            cols = st.columns(2)
            for i, f in enumerate(recent[:10]):
                with cols[i % 2]:
                    name = f.get("name", f.get("path", "?"))
                    modified = f.get("modified_at") or f.get("mtime")
                    st.markdown(
                        f"📄 **{name}** _{format_timestamp(modified)}_"
                    )


def _render_live_context(lc: dict) -> None:
    """Render live context details."""
    # Try common structures
    summary = lc.get("summary") or lc.get("description") or lc.get("context")

    if summary:
        st.markdown("**Summary | الملخص:**")
        st.info(summary)

    # Stats
    files_total = lc.get("total_files", lc.get("file_count"))
    dirs_total = lc.get("total_dirs", lc.get("dir_count"))

    if files_total is not None or dirs_total is not None:
        cols = st.columns(4)
        with cols[0]:
            _metric_card(
                files_total if files_total is not None else "—",
                "Files | ملفات",
                "📄",
            )
        with cols[1]:
            _metric_card(
                dirs_total if dirs_total is not None else "—",
                "Directories | مجلدات",
                "📁",
            )

    # Raw
    with st.expander("📄 Raw Live Context JSON | السياق الخام"):
        st.json(lc)


def _metric_card(value, label, icon) -> None:
    st.markdown(
        f"""
        <div class="wolf-metric-card">
            <div style="font-size: 1.5rem;">{icon}</div>
            <div class="wolf-metric-value" style="font-size: 1.2rem;">{value}</div>
            <div class="wolf-metric-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
