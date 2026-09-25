#!/usr/bin/env python3
r"""Alpha Wolf Agent — Streamlit Preview UI (Bilingual AR+EN).

Run:
    cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
    python -m streamlit run frontend/streamlit_preview.py --server.port 8501 --server.headless true

URL: http://127.0.0.1:8501/
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import sqlite3
import streamlit as st

try:
    from body.alpha_wolf_body import AlphaWolfBody
    HAS_BODY = True
except ImportError:
    HAS_BODY = False

st.set_page_config(
    page_title="🐺 Alpha Wolf Agent",
    page_icon="🐺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Bilingual labels
T = {
    # Header
    "title": "🐺 Alpha Wolf Agent — Body Dashboard",
    "subtitle": "بنية الجسم + بروتوكول تصنيف الذئب",
    # Sidebar
    "navigation": "🐺 Wolf Navigation | قائمة الذئب",
    "choose_view": "Choose View | اختر القسم",
    "body_status": "📊 Body Status | حالة الجسم",
    "wolf_traits": "🐺 Wolf Traits | صفات الذئب",
    # Tabs
    "body_health": "📊 Body Health | صحة الجسم",
    "memory_inspector": "🧠 Memory Inspector | مفتش الذاكرة",
    "knowledge_graph": "📁 Knowledge Graph | خريطة المعرفة",
    "classify_dataset": "🔍 Classify Dataset | تصنيف Dataset",
    "tools_registry": "🛠️ Tools Registry | سجل الأدوات",
    "gaps_tracker": "📈 Gaps Tracker | متتبع الفجوات",
    "chat_with_agent": "💬 Chat with Alpha Wolf | محادثة مع الوكيل",
    # Stats
    "chromadb_collections": "ChromaDB Collections | مجموعات ChromaDB",
    "networkx_nodes": "NetworkX Nodes | عقد NetworkX",
    "networkx_edges": "NetworkX Edges | روابط NetworkX",
    "sqlite_tables": "SQLite Tables | جداول SQLite",
    "sqlite_size": "SQLite Size (MB) | حجم SQLite",
    "zvec_ok": "zvec OK | zvec يعمل",
    "integrity": "Integrity | السلامة",
    "disk_usage": "Disk Usage (MB) | استخدام القرص",
    "classifications": "Classifications | التصنيفات",
    "iron_laws_active": "Iron Laws Active | القوانين النشطة",
    # Chat
    "chat_placeholder": "Ask Alpha Wolf anything... | اسأل الذئب أي شيء...",
    "send": "Send | إرسال 📤",
    "chat_disabled": "⚠️ Backend not running. Start with: uvicorn backend.main:app --port 8001 | الخادم غير مشتغل",
    # Memory
    "active_goals": "🎯 Active Goals | الأهداف النشطة",
    "open_goals": "Open Goals | الأهداف المفتوحة",
    "recent_mistakes": "Recent Mistakes + Lessons | الأخطاء والدروس",
    "recent_reflections": "Recent Reflections | التأملات الحديثة",
    "recent_episodes": "Recent Episodes | الحلقات الحديثة",
    "what_went_wrong": "What went wrong | ماذا حدث خطأ",
    "lesson": "Lesson | الدرس",
    "confidence": "Confidence | الثقة",
    "trigger": "Trigger | المُحفِّز",
    "importance": "Importance | الأهمية",
    "severity": "Severity | الشدة",
    "context": "Context | السياق",
    "mark_done": "Mark Done | تم ✅",
    # Classify
    "upload_dataset": "Upload dataset file (.jsonl, .json, .csv, .txt) | ارفع ملف dataset",
    "classify_button": "🔍 Classify | تصنيف",
    "classified_class": "Class | الفئة",
    "classified_confidence": "Confidence | الثقة",
    "classified_reason": "Reason | السبب",
    "classified_patterns": "Detected Patterns | الأنماط المكتشفة",
    # Self
    "self_summary": "Self Summary | الملخص الذاتي",
    "model": "Model | النموذج",
    "training_mix": "Training Mix | خليط التدريب",
    # Footer
    "phase_version": "Phase 11+ v3.2 — Wolf Classification | المرحلة 11+ الإصدار 3.2",
}


def main():
    # Sidebar (bilingual)
    with st.sidebar:
        st.markdown(f"### {T['navigation']}")
        page = st.radio(T["choose_view"], [
            f"💬 {T['chat_with_agent']}",
            f"📊 {T['body_health']}",
            f"🧠 {T['memory_inspector']}",
            f"📁 {T['knowledge_graph']}",
            f"🔍 {T['classify_dataset']}",
            f"🛠️ {T['tools_registry']}",
            f"📈 {T['gaps_tracker']}",
        ])

        st.markdown("---")
        st.markdown(f"### {T['body_status']}")
        if HAS_BODY:
            try:
                body = AlphaWolfBody()
                health = body.health_check()
                body.close()
                st.metric(T["chromadb_collections"], health["chromadb"]["collections"])
                st.metric(T["networkx_nodes"], health["networkx"]["nodes"])
                st.metric(T["networkx_edges"], health["networkx"]["edges"])
                st.metric(T["sqlite_tables"], len(health["sqlite"]["tables"]))
                st.metric(T["zvec_ok"], "✅" if health["zvec"]["ok"] else "❌")
                st.metric(T["integrity"], health["sqlite"]["integrity"])
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.error("Body module not found")

        st.markdown(f"### {T['wolf_traits']}")
        st.markdown(f"**Mistake Hunter (اقتناص الأخطاء):** 3")
        st.markdown(f"**Goal Persistence (تتبع الأهداف):** 3")
        st.markdown(f"**Deep Thinking (التفكير العميق):** 3")
        st.markdown(f"**Resourceful (استخدام الموارد):** 2")

    # Page routing
    if T["chat_with_agent"] in page:
        show_chat()
    elif T["body_health"] in page:
        show_health()
    elif T["memory_inspector"] in page:
        show_memory()
    elif T["knowledge_graph"] in page:
        show_graph()
    elif T["classify_dataset"] in page:
        show_classify()
    elif T["tools_registry"] in page:
        show_tools()
    elif T["gaps_tracker"] in page:
        show_gaps()


def show_chat():
    """Chat with Alpha Wolf via backend."""
    st.markdown(f"## 💬 {T['chat_with_agent']}")
    st.markdown("""
    **URL للدردشة:** http://127.0.0.1:8501/

    **كيف تتحدث مع الوكيل | How to chat:**
    1. اكتب رسالتك في الأسفل | Type your message below
    2. اضغط Send | Click Send
    3. الـ body يستدعي llama.cpp (عبر FastAPI على port 8001)
    """)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        with st.chat_message(role):
            st.markdown(content)

    # Chat input
    if prompt := st.chat_input(T["chat_placeholder"]):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call backend
        try:
            import httpx
            with httpx.Client(timeout=300) as client:
                response = client.post(
                    "http://127.0.0.1:8001/v1/chat/completions",
                    json={
                        "model": "alpha-wolf-agent",
                        "messages": [{"role": "user", "content": prompt}],
                        "use_body_recall": True,
                        "top_k": 5,
                    },
                )
                response.raise_for_status()
                data = response.json()
                assistant_msg = data["choices"][0]["message"]["content"]
                st.session_state.messages.append({"role": "assistant", "content": assistant_msg})
                with st.chat_message("assistant"):
                    st.markdown(assistant_msg)
        except Exception as e:
            st.error(f"{T['chat_disabled']}")
            st.error(f"Error: {e}")


def show_health():
    """Show body health."""
    st.markdown(f"## 📊 {T['body_health']}")

    if not HAS_BODY:
        st.error("Body module not available")
        return

    body = AlphaWolfBody()
    health = body.health_check()
    summary = body.get_self_summary()
    body.close()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(T["chromadb_collections"], health["chromadb"]["collections"])
    with col2:
        st.metric(T["networkx_nodes"], health["networkx"]["nodes"])
    with col3:
        st.metric(T["networkx_edges"], health["networkx"]["edges"])
    with col4:
        st.metric(T["sqlite_size"], health["sqlite"]["size_mb"])

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric(T["sqlite_tables"], len(health["sqlite"]["tables"]))
    with col6:
        st.metric(T["zvec_ok"], "✅" if health["zvec"]["ok"] else "❌")
    with col7:
        st.metric(T["integrity"], health["sqlite"]["integrity"])
    with col8:
        st.metric(T["disk_usage"], round(health["disk_usage"]["size_mb"], 1))

    st.markdown(f"### {T['self_summary']}")
    st.json(summary)


def show_memory():
    """Memory inspector."""
    st.markdown(f"## 🧠 {T['memory_inspector']}")
    if not HAS_BODY:
        return

    body = AlphaWolfBody()
    tab1, tab2, tab3, tab4 = st.tabs([
        f"🎯 {T['active_goals']}",
        f"⚠️ {T['recent_mistakes']}",
        f"💡 {T['recent_reflections']}",
        f"📝 {T['recent_episodes']}",
    ])

    with tab1:
        st.markdown(f"### {T['active_goals']} / {T['open_goals']}")
        for status in ["active", "open"]:
            goals = body.recall_goals(status=status, limit=10)
            st.markdown(f"#### {T['active_goals'] if status == 'active' else T['open_goals']}")
            for g in goals:
                st.markdown(f"**{g['title']}** (priority: {g['priority']}, progress: {g.get('progress_pct', 0)}%)")
                if g.get('description'):
                    st.caption(g['description'])

    with tab2:
        st.markdown(f"### {T['recent_mistakes']}")
        mistakes = body.recall_mistakes(severity_min=5, limit=10)
        for m in mistakes:
            with st.expander(f"[{T['severity']} {m['severity']}] {m['context'][:80]}..."):
                st.markdown(f"**{T['what_went_wrong']}:** {m['what_went_wrong']}")
                st.markdown(f"**{T['lesson']}:** {m['lesson']}")

    with tab3:
        st.markdown(f"### {T['recent_reflections']}")
        reflections = body.recall_reflections(min_confidence=0.5, limit=10)
        for r in reflections:
            with st.expander(f"{T['confidence']}: {r['confidence']:.2f} | {T['trigger']}: {r['trigger']}"):
                st.markdown(f"**{r['insight']}**")

    with tab4:
        st.markdown(f"### {T['recent_episodes']}")
        episodes = body.recall_episodes(min_importance=3, limit=10)
        for e in episodes:
            st.markdown(f"**[{e['trigger_type']}]** ({T['importance']}: {e['importance']})")
            st.caption(e['content'][:200])

    body.close()


def show_graph():
    """Knowledge graph browser."""
    st.markdown(f"## 📁 {T['knowledge_graph']}")
    if not HAS_BODY:
        return

    body = AlphaWolfBody()
    st.metric(T["networkx_nodes"], body.graph.number_of_nodes())
    st.metric(T["networkx_edges"], body.graph.number_of_edges())

    st.markdown("### Node Types | أنواع العقد")
    node_types = ["Concept", "Tool", "Person", "Place", "Dataset", "Mistake", "Goal", "Reflection", "Episode", "KB"]
    cols = st.columns(5)
    for i, nt in enumerate(node_types):
        with cols[i % 5]:
            st.markdown(f"• `{nt}`")

    st.markdown("### Edge Types | أنواع الروابط")
    edge_types = ["trains_on", "depends_on", "knows_about", "similar_to", "learned_from", "applies_to", "blocks", "achieves"]
    for et in edge_types:
        st.code(f"{et} (source) -> (target)")

    body.close()


def show_classify():
    """Wolf classifier interface."""
    st.markdown(f"## 🔍 {T['classify_dataset']}")
    st.markdown("""
    **Wolf Classification Protocol — 4-class | بروتوكول تصنيف الذئب**

    - 🚨 **HARMFUL (ضار)** → REJECT
    - 📁 **PROJECT-SPECIFIC (خاص بمشروع)** → workspace
    - ✅ **USEFUL (مفيد)** → distill → body
    - ❓ **RAW (خام)** → review queue
    """)

    uploaded = st.file_uploader(T["upload_dataset"], type=["jsonl", "json", "csv", "txt"])

    if uploaded:
        temp_path = PROJECT_ROOT / "body" / uploaded.name
        with open(temp_path, "wb") as f:
            f.write(uploaded.getbuffer())

        st.success(f"Uploaded: {uploaded.name}")

        from body.intake.wolf_classifier import WolfClassifier
        classifier = WolfClassifier()
        result = classifier.classify(temp_path)

        col1, col2, col3 = st.columns(3)
        with col1:
            emoji = {"harmful": "🚨", "project_specific": "📁", "useful": "✅", "raw": "❓"}
            st.metric(T["classified_class"], f"{emoji.get(result['class'], '?')} {result['class'].upper()}")
        with col2:
            st.metric(T["classified_confidence"], f"{result['confidence']:.2f}")
        with col3:
            st.metric("Size (MB)", result["file_size_mb"])

        st.markdown(f"**{T['classified_reason']}:** {result['reason']}")

        if result.get("detected_patterns"):
            with st.expander(T["classified_patterns"]):
                st.json(result["detected_patterns"])

        temp_path.unlink()


def show_tools():
    """Tools registry."""
    st.markdown(f"## 🛠️ {T['tools_registry']}")
    if not HAS_BODY:
        return

    body = AlphaWolfBody()
    tools = body.list_tools()
    st.markdown(f"**Total: {len(tools)} | المجموع**")

    for t in tools:
        with st.expander(f"🛠️ **{t['name']}** ({t.get('category', 'N/A')})"):
            st.code(t.get('invocation', ''))
            st.caption(f"Invocations | الاستدعاءات: {t.get('invocation_count', 0)}")

    body.close()


def show_gaps():
    """Gaps tracker."""
    st.markdown(f"## 📈 {T['gaps_tracker']}")
    gaps_data = [
        ("G1", "llama.cpp server not deployed | llama.cpp غير منشور", "P0", "Waiting for training"),
        ("G2", "Chainlit deps not installed | Chainlit غير مثبت", "P0", "Installing..."),
        ("G3", "FastAPI deps installed ✅ | FastAPI مثبت", "P0 Done", "✅"),
        ("G4", "Ollama embed model not configured | Ollama لم يتم", "P0", "Pending"),
        ("G5", "Backend ↔ llama.cpp integration | ربط Backend بـ llama.cpp", "P0", "Pending"),
        ("G6", "Body Ingestion Pipeline | خط أنابيب الاستيعاب", "✅ Done", "Phase v3.1"),
        ("G17", "Wolf Classification Protocol | بروتوكول تصنيف الذئب", "✅ Done", "Phase v3.2"),
        ("G7", "Authentication | المصادقة", "P1", "Pending"),
        ("G8", "Encryption at rest | التشفير", "P1", "Pending"),
    ]

    for gid, title, priority, status in gaps_data:
        if priority == "✅ Done":
            st.success(f"**{gid}** {title} — {status}")
        elif priority.startswith("P0"):
            st.error(f"**{gid}** {title} — {status}")
        else:
            st.warning(f"**{gid}** {title} — {status}")


if __name__ == "__main__":
    main()