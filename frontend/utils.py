#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Frontend Utilities
=====================================
Shared helpers for the Streamlit UI.

Provides:
- APIClient: synchronous HTTP client wrapping the FastAPI backend
- i18n: bilingual (Arabic + English) labels per Iron Law #47
- formatters: markdown rendering, code highlighting, time helpers
- stream_helpers: SSE streaming via requests (Streamlit cannot use httpx async directly)
- session: Streamlit session state initialization and helpers

Iron Laws Applied:
- #15 Verify: backend reachability checks before rendering UI
- #33 Lessons: bilingual labels with tooltip annotations
- #41 Conflict: explicit fallbacks documented
- #42 Storage Discipline: backend URL configurable via env var (no hardcoded secrets)
- #47 Bilingual: every user-visible string is AR + EN
- #48 Separated Concerns: no UI rendering here (utilities only)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import requests

logger = logging.getLogger("alpha_wolf_frontend")

# ============================================================================
# Configuration
# ============================================================================

BACKEND_URL = os.environ.get("ALPHA_WOLF_BACKEND_URL", "http://127.0.0.1:8001")
DEFAULT_TIMEOUT = 30
STREAM_TIMEOUT = 600  # 10 min for long streams

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = PROJECT_ROOT / "frontend" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Bilingual Labels (Iron Law #47)
# ============================================================================

T = {
    # Branding
    "app_name": "Alpha Wolf Agent",
    "app_subtitle": "وكيل الذئب ألفا",
    "wolf_emoji": "🐺",
    "app_tagline": "Your wolf-themed AI assistant with 7 traits",
    "app_tagline_ar": "مساعدك الذكي بصفات الذئب السبع",
    "footer_disclaimer": "",

    # Sidebar
    "new_chat": "New chat | محادثة جديدة",
    "conversations": "Conversations | المحادثات",
    "search_chats": "Search chats... | ابحث في المحادثات...",
    "today": "Today | اليوم",
    "yesterday": "Yesterday | أمس",
    "previous_7_days": "Previous 7 days | الأيام السبعة السابقة",
    "delete_chat": "Delete | حذف",
    "delete_confirm": "Delete this chat? | حذف هذه المحادثة؟",
    "no_conversations": "No conversations yet | لا محادثات بعد",
    "wolf_traits": "Wolf Traits | صفات الذئب",
    "trait_active": "Active | نشط",
    "backend_status": "Backend Status | حالة الخادم",
    "backend_connected": "Connected | متصل",
    "backend_offline": "Offline | غير متصل",
    "model_label": "Model | النموذج",
    "user_name": "Quханд هشام | القائد",
    "settings_link": "Settings | الإعدادات",

    # Top bar
    "clear_chat": "Clear chat | مسح المحادثة",
    "clear_confirm": "Clear this conversation? | مسح هذه المحادثة؟",
    "theme_toggle": "Theme | المظهر",
    "theme_dark": "Dark | داكن",
    "theme_light": "Light | فاتح",
    "temperature_label": "Temperature | الحرارة",

    # Chat
    "chat_placeholder": "Message Alpha Wolf... (Enter to send, Shift+Enter for new line) | اكتب للذئب... (Enter للإرسال، Shift+Enter لسطر جديد)",
    "send": "Send | إرسال",
    "stop_generating": "Stop | إيقاف",
    "thinking": "Alpha Wolf is thinking | الذئب يفكر",
    "thinking_with_dots": "Alpha Wolf is thinking...",
    "tool_calling": "Tool Call | استدعاء أداة",
    "tool_result": "Result | النتيجة",
    "tool_duration": "Duration | المدة",
    "tool_arguments": "Arguments | المعاملات",
    "tool_output": "Output | المخرجات",
    "upload_file": "Upload File | رفع ملف",
    "upload_tooltip": "Attach a file to your message | إرفق ملف مع رسالتك",
    "copy_response": "Copy | نسخ",
    "regenerate": "Regenerate | إعادة التوليد",
    "export_chat": "Export | تصدير",
    "export_json": "Export as JSON | تصدير JSON",
    "export_markdown": "Export as Markdown | تصدير Markdown",

    # Quick start cards (welcome screen)
    "qs_mistake_hunter_title": "Mistake Hunter | اقتناص الأخطاء",
    "qs_mistake_hunter_desc": "Help me debug code | ساعدني في تصحيح كود",
    "qs_deep_thinking_title": "Deep Thinking | التفكير العميق",
    "qs_deep_thinking_desc": "Analyze a complex problem | حلل مشكلة معقدة",
    "qs_resourceful_title": "Resourceful | استخدام الموارد",
    "qs_resourceful_desc": "Find tools to solve this | جد أدوات لحل هذا",
    "qs_tenacity_title": "Tenacity | الشراسة",
    "qs_tenacity_desc": "Don't give up on me | لا تستسلم",

    # Errors
    "error": "Error | خطأ",
    "error_backend_offline": "Backend is offline. Start it with: | الخادم متوقف. شغّله بـ:",
    "retry": "Retry | إعادة المحاولة",
    "cancel": "Cancel | إلغاء",
    "save": "Save | حفظ",
    "delete": "Delete | حذف",
    "edit": "Edit | تعديل",
    "close": "Close | إغلاق",
    "yes": "Yes | نعم",
    "no": "No | لا",
    "open": "Open | فتح",

    # Wolf traits (7 traits)
    "trait_mistake_hunter": "Mistake Hunter | اقتناص الأخطاء",
    "trait_goal_persistence": "Goal Persistence | تتبع الأهداف",
    "trait_tenacity": "Tenacity | الشراسة",
    "trait_deep_thinking": "Deep Thinking | التفكير العميق",
    "trait_resourceful": "Resourceful | استخدام الموارد",
    "trait_self_aware": "Self-Aware | الوعي الذاتي",
    "trait_reinforcement_learning": "Reinforcement Learning | التعلم التعزيزي",

    # Settings
    "settings_general": "General | عام",
    "settings_appearance": "Appearance | المظهر",
    "settings_model": "Model | النموذج",
    "settings_advanced": "Advanced | متقدم",

    # Welcome metrics
    "chromadb_collections": "ChromaDB Collections | مجموعات ChromaDB",
    "networkx_nodes": "NetworkX Nodes | عقد NetworkX",
    "networkx_edges": "NetworkX Edges | روابط NetworkX",
    "sqlite_tables": "SQLite Tables | جداول SQLite",

    # Memory views
    "memory_episodes": "Episodes | الحلقات",
    "memory_goals": "Goals | الأهداف",
    "memory_mistakes": "Mistakes | الأخطاء",
    "memory_reflections": "Reflections | التأملات",
    "active_goals": "Active Goals | الأهداف النشطة",
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

    # Tools
    "tools_total": "Tools Total | إجمالي الأدوات",
    "tools_categories": "Categories | الفئات",
    "try_tool": "Try Tool | تجربة الأداة",
    "tool_name": "Name | الاسم",
    "tool_description": "Description | الوصف",
    "tool_parameters": "Parameters | المعاملات",
    "tool_invocation": "Invocation | الاستدعاء",
    "tool_result": "Result | النتيجة",
    "tool_invocations_count": "Invocations | مرات الاستدعاء",
    "add_custom_tool": "Add Custom Tool | إضافة أداة مخصصة",

    # Project Awareness
    "project_folder": "Project Folder | مجلد المشروع",
    "files_indexed": "Files Indexed | ملفات مفهرسة",
    "last_scan": "Last Scan | آخر فحص",
    "refresh_index": "Refresh Index | إعادة الفهرسة",
    "rag_stats": "RAG Stats | إحصائيات RAG",
    "live_context_summary": "Live Context Summary | ملخص السياق المباشر",
    "index_now": "Index Now | فهرسة الآن",

    # Common
    "loading": "Loading... | جاري التحميل...",
    "metadata": "Metadata | البيانات الوصفية",
    "timestamp": "Timestamp | الوقت",

    # Navigation
    "nav_chat": "Chat | محادثة",
    "nav_health": "Body Health | صحة الجسد",
    "nav_memory": "Memory | الذاكرة",
    "nav_tools": "Tools | الأدوات",
    "nav_project": "Project Awareness | وعي المشروع",
    "nav_settings": "Settings | الإعدادات",

    # Agent lifecycle (restart / stop)
    "restart_agent": "Restart agent | إعادة تشغيل الوكيل",
    "restart_agent_help": "Reset agent state and start fresh (keeps model settings) | تصفير حالة الوكيل والبدء من جديد (مع الاحتفاظ بإعدادات النموذج)",
    "agent_restarted": "Agent restarted — fresh state | تمت إعادة تشغيل الوكيل — حالة جديدة",
    "stop_agent": "Stop agent | إيقاف الوكيل",
    "stop_agent_help": "Stop the ongoing generation immediately | إيقاف التوليد الجاري فوراً",
    "agent_stopped": "Agent stopped | تم إيقاف الوكيل",
    "agent_stopped_partial": "Generation stopped by user — partial reply kept | تم إيقاف التوليد — تم الاحتفاظ بالرد الجزئي",
    "no_active_generation": "No active generation to stop | لا يوجد توليد جارٍ لإيقافه",

    # Memory Inspector
    "memory_inspector": "Memory Inspector | فحص الذاكرة",

    # Body Health + Memory Inspector missing keys (Phase 35)
    "refresh": "Refresh | تحديث",
    "body_status": "Body Status | حالة الجسد",
    "create_backup": "Create Backup | إنشاء نسخة احتياطية",
    "backup_created": "Backup created | تم إنشاء النسخة",
    "wolf_self_summary": "Wolf Self-Summary | ملخص الذئب الذاتي",
    "training_mix": "Training Mix | مزيج بيانات التدريب",
    "integrity": "Integrity | السلامة",
    "add_to_memory": "Add to Memory | إضافة للذاكرة",
    "episode_importance": "Episode Importance | أهمية الحلقة",
    "episode_content": "Episode Content | محتوى الحلقة",
    "zvec_status": "zvec Status | حالة zvec",
    "sqlite_size": "SQLite Size | حجم قاعدة البيانات",

    # Admin shutdown (Phase 35 — Stop Everything button)
    "stop_everything": "Stop Everything | إيقاف كل شيء",
    "stop_everything_help": "Stop backend + frontend completely (closes this app) | إيقاف الخادم والواجهة بالكامل (يُغلق هذا التطبيق)",
    "stop_confirm": "Stop Alpha Wolf Agent? The app will close. | إيقاف وكيل الذئب ألفا؟ سيُغلق التطبيق.",
    "stopping_now": "Stopping... You can close this tab. | جاري الإيقاف... يمكنك إغلاق هذا التبويب.",
    "stop_disabled_no_backend": "Backend offline — cannot stop remotely | الخادم متوقف — لا يمكن الإيقاف عن بُعد",

    # Welcome screen
    "chat_placeholder": "Message Alpha Wolf... (Enter to send, Shift+Enter for new line) | اكتب للذئب... (Enter للإرسال، Shift+Enter لسطر جديد)",
}

# Default wolf trait active state (visual indicators)
WOLF_TRAITS = [
    ("trait_mistake_hunter", "🔍"),
    ("trait_goal_persistence", "🎯"),
    ("trait_tenacity", "💪"),
    ("trait_deep_thinking", "🧠"),
    ("trait_resourceful", "🛠️"),
    ("trait_self_aware", "👁️"),
    ("trait_reinforcement_learning", "🔄"),
]


# ============================================================================
# API Client
# ============================================================================


@dataclass
class APIError(Exception):
    """Wrapper for backend errors with bilingual message."""

    status_code: int
    detail: str
    url: str

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.detail} ({self.url})"

    def bilingual(self) -> str:
        return f"{T['error']}: {self.detail}"


class APIClient:
    """Synchronous HTTP client for the FastAPI backend."""

    def __init__(self, base_url: str = BACKEND_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    # ----- Health -----
    def health_check(self) -> bool:
        try:
            resp = self._session.get(f"{self.base_url}/", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def body_health(self) -> dict[str, Any] | None:
        try:
            resp = self._session.get(f"{self.base_url}/v1/body/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("body_health failed: %s", exc)
            return None

    def self_summary(self) -> dict[str, Any] | None:
        try:
            resp = self._session.get(f"{self.base_url}/v1/self/summary", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("self_summary failed: %s", exc)
            return None

    def create_backup(self) -> dict[str, Any] | None:
        try:
            resp = self._session.post(f"{self.base_url}/v1/body/backup", timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("create_backup failed: %s", exc)
            return None

    # ----- Conversations -----
    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            resp = self._session.get(
                f"{self.base_url}/v1/conversations", params={"limit": limit}, timeout=5
            )
            resp.raise_for_status()
            return resp.json().get("conversations", [])
        except requests.RequestException as exc:
            logger.warning("list_conversations failed: %s", exc)
            return []

    def create_conversation(self, title: str | None = None) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/conversations",
                json={"title": title} if title else {},
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("create_conversation failed: %s", exc)
            return None

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        try:
            resp = self._session.get(
                f"{self.base_url}/v1/conversations/{conversation_id}", timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("get_conversation failed: %s", exc)
            return None

    def delete_conversation(self, conversation_id: str) -> bool:
        try:
            resp = self._session.delete(
                f"{self.base_url}/v1/conversations/{conversation_id}", timeout=5
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.warning("delete_conversation failed: %s", exc)
            return False

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        importance: int = 5,
    ) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/conversations/{conversation_id}/messages",
                json={"role": role, "content": content, "importance": importance},
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("add_message failed: %s", exc)
            return None

    def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get all messages in a conversation.

        Note: Backend does NOT expose GET for messages (only POST/Add).
        We retrieve the full conversation object which includes messages.
        """
        conv = self.get_conversation(conversation_id)
        if not conv:
            return []
        return conv.get("messages", [])[:limit]

    # ----- Chat (non-streaming) -----
    def chat(self, messages: list[dict[str, str]], **kwargs) -> dict[str, Any] | None:
        """Non-streaming chat completion."""
        try:
            # FIX 2026-10-06: use v8 by default — original `alpha-wolf-agent` is BROKEN
            payload = {"model": "alpha-wolf-agent-v8", "messages": messages}
            payload.update(kwargs)
            resp = self._session.post(
                f"{self.base_url}/v1/chat/completions", json=payload, timeout=300
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("chat failed: %s", exc)
            return None

    # ----- Chat (streaming) -----
    def stream_chat(
        self,
        messages: list[dict[str, str]],
        conversation_id: str | None = None,
        auto_tools: bool = True,
    ) -> Iterator[dict[str, Any]]:
        """Stream chat completion via SSE.

        Yields dicts like:
            {"type": "token", "chunk": "..."}
            {"type": "tool_call", "name": "...", "arguments": {...}}
            {"type": "tool_result", "name": "...", "output": {...}}
            {"type": "done"}
            {"type": "error", "message": "..."}
        """
        payload = {
            "model": "alpha-wolf-agent-v8",  # FIX 2026-10-06: original model broken
            "messages": messages,
            "stream": True,
            "auto_tools": auto_tools,
            "max_tokens": 4000,  # PHASE 14: Increased to give Ollama's reasoning phase enough budget before content phase (was 2000, reasoning consumed all tokens leaving 0 for content)
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        try:
            with self._session.post(
                f"{self.base_url}/v1/chat/stream",
                json=payload,
                stream=True,
                timeout=STREAM_TIMEOUT,
                headers={"Accept": "text/event-stream"},
            ) as resp:
                resp.raise_for_status()
                # Parse SSE manually
                event_buf: list[str] = []
                data_buf: list[str] = []

                for raw_line in resp.iter_lines(decode_unicode=True):
                    if raw_line is None:
                        continue
                    line = raw_line.rstrip("\n")
                    if line.startswith("event:"):
                        event_buf.append(line[6:].strip())
                    elif line.startswith("data:"):
                        data_buf.append(line[5:].strip())
                    elif line == "" or line.startswith(":"):
                        # Dispatch buffered event
                        if data_buf:
                            data_str = "\n".join(data_buf)
                            event_name = event_buf[0] if event_buf else "message"
                            try:
                                if data_str == "[DONE]" and not event_buf:
                                    # Bare untagged sentinel.
                                    # FIX 2026-09-26 (Round 14): never treat this
                                    # as end-of-answer. Ollama closes EVERY model
                                    # call with one, so a tool turn (call #1 =
                                    # tool call, call #2 = answer) ended here and
                                    # the UI rendered "empty response from
                                    # backend". The authoritative terminal is the
                                    # tagged `event: done` sent once at the end.
                                    logger.debug("SSE: untagged [DONE] sentinel ignored")
                                elif data_str == "[DONE]":
                                    yield {"type": "done", "done": True}
                                else:
                                    payload_json = json.loads(data_str)
                                    payload_json["type"] = event_name
                                    yield payload_json
                            except json.JSONDecodeError:
                                logger.warning("SSE JSON decode error: %s", data_str[:200])
                            event_buf = []
                            data_buf = []
        except requests.RequestException as exc:
            yield {"type": "error", "message": str(exc)}

    # ----- Tools -----
    def list_tools(self, category: str | None = None) -> dict[str, Any] | None:
        try:
            params = {"category": category} if category else {}
            resp = self._session.get(
                f"{self.base_url}/v1/tools", params=params, timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("list_tools failed: %s", exc)
            return None

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/tools/execute",
                json={"name": name, "arguments": arguments},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("execute_tool failed: %s", exc)
            return None

    def tool_categories(self) -> dict[str, int] | None:
        try:
            resp = self._session.get(
                f"{self.base_url}/v1/tools/categories", timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("tool_categories failed: %s", exc)
            return None

    # ----- Skills (self-extension management) -----
    def list_skills(self) -> list[dict[str, Any]]:
        try:
            resp = self._session.get(f"{self.base_url}/v1/skills/registry", timeout=10)
            resp.raise_for_status()
            return resp.json().get("skills", [])
        except requests.RequestException as exc:
            logger.warning("list_skills failed: %s", exc)
            return []

    def run_skill(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/skills/{name}/run",
                json={"arguments": arguments},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("run_skill failed: %s", exc)
            return None

    def install_skill_from_url(self, url: str, name: str = "") -> dict[str, Any] | None:
        """Install a skill via the forge (skills.sh/GitHub/.py)."""
        res = self.execute_tool(
            "install_skill_from_url", {"url": url, "name": name or ""}
        )
        return res

    # ----- Self-awareness (model/gaps/system) -----
    def self_model(self) -> dict[str, Any] | None:
        try:
            resp = self._session.get(f"{self.base_url}/v1/self/model", timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("self_model failed: %s", exc)
            return None

    def self_gaps(self) -> dict[str, Any] | None:
        try:
            resp = self._session.get(f"{self.base_url}/v1/self/gaps", timeout=90)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("self_gaps failed: %s", exc)
            return None

    def system_status(self) -> dict[str, Any] | None:
        res = self.execute_tool("system_status", {})
        return (res or {}).get("output") if res else None

    # ----- Admin shutdown (Phase 35 — Stop Everything button) -----
    def admin_stop_all(self, timeout: float = 4.0) -> dict[str, Any] | None:
        """Tell the backend to kill the frontend + shut itself down.

        إبلاغ الخادم بإيقاف الواجهة وإنهاء نفسه.

        The backend POST /v1/admin/stop-all kills the Streamlit listener on
        port 8501 then SIGTERMs itself. Returns the JSON ack or None on error.
        """
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/admin/stop-all",
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("admin_stop_all failed: %s", exc)
            return None

    def admin_shutdown_backend(self, timeout: float = 4.0) -> dict[str, Any] | None:
        """Stop the backend only (frontend stays running but loses connectivity).

        إيقاف الخادم فقط.
        """
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/admin/shutdown",
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("admin_shutdown_backend failed: %s", exc)
            return None

    # ----- Web (search/fetch via engine endpoints) -----
    def web_search(self, query: str, max_results: int = 5) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/web/search",
                json={"query": query, "max_results": max_results},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("web_search failed: %s", exc)
            return None

    def web_fetch(self, url: str, max_chars: int = 8000) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/web/fetch",
                json={"url": url, "max_chars": max_chars},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("web_fetch failed: %s", exc)
            return None

    # ----- Vision -----
    def describe_image(self, image_path: str, prompt: str = "") -> dict[str, Any] | None:
        res = self.execute_tool(
            "see_image", {"image_path": image_path, "prompt": prompt or ""}
        )
        return (res or {}).get("output") if res else None

    # ----- Memory -----
    def list_episodes(self, limit: int = 50, min_importance: int = 1) -> list[dict[str, Any]]:
        try:
            resp = self._session.get(
                f"{self.base_url}/v1/memory/episode",
                params={"limit": limit, "min_importance": min_importance},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("episodes", [])
        except requests.RequestException as exc:
            logger.warning("list_episodes failed: %s", exc)
            return []

    def list_goals(self, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        try:
            params: dict[str, Any] = {"limit": limit}
            if status:
                params["status"] = status
            resp = self._session.get(
                f"{self.base_url}/v1/memory/goal", params=params, timeout=5
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("goals", [])
        except requests.RequestException as exc:
            logger.warning("list_goals failed: %s", exc)
            return []

    def list_mistakes(self, limit: int = 50, severity_min: int = 1) -> list[dict[str, Any]]:
        try:
            resp = self._session.get(
                f"{self.base_url}/v1/memory/mistake",
                params={"limit": limit, "severity_min": severity_min},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("mistakes", [])
        except requests.RequestException as exc:
            logger.warning("list_mistakes failed: %s", exc)
            return []

    def list_reflections(self) -> list[dict[str, Any]]:
        """Reflections endpoint only supports POST (create), not GET (list).

        Backend limitation: only POST /v1/memory/reflection exists.
        Returns empty list — UI should display a notice.
        """
        # Iron Law #41: documenting limitation rather than fabricating
        return []

    def add_episode(self, content: str, trigger_type: str = "user_task", importance: int = 5) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/memory/episode",
                json={"content": content, "trigger_type": trigger_type, "importance": importance},
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("add_episode failed: %s", exc)
            return None

    def update_goal(self, goal_id: str, status: str, progress_pct: float = 100.0) -> bool:
        try:
            resp = self._session.patch(
                f"{self.base_url}/v1/memory/goal/{goal_id}",
                params={"status": status, "progress_pct": progress_pct},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.warning("update_goal failed: %s", exc)
            return False

    # ----- Live Context & RAG -----
    def live_context_summary(self) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/live-context/summary",
                json={"max_depth": 2, "recent_days": 7},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("live_context_summary failed: %s", exc)
            return None

    def rag_stats(self) -> dict[str, Any] | None:
        try:
            resp = self._session.get(f"{self.base_url}/v1/rag/stats", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("rag_stats failed: %s", exc)
            return None

    def rag_index(self, force: bool = False) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/rag/index",
                json={"force": force, "patterns": ["**/*.py", "**/*.md", "**/*.json", "**/*.yaml", "**/*.yml"]},
                timeout=600,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("rag_index failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # FIX 2026-10-06 (Phase 46): additional backend integrations to push
    # the UI↔API surface past the 60% line. Iron Law #15: live only.
    # ------------------------------------------------------------------

    def list_tools_discover(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/tools/discover", timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("list_tools_discover failed: %s", exc)
            return None

    def list_mcp_tools(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/mcp/tools", timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("list_mcp_tools failed: %s", exc)
            return None

    def call_mcp_rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        try:
            r = self._session.post(
                f"{self.base_url}/v1/mcp/rpc",
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                timeout=20,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("call_mcp_rpc failed: %s", exc)
            return None

    def vision_status(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/vision/status", timeout=5)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("vision_status failed: %s", exc)
            return None

    def vision_test(self) -> dict[str, Any] | None:
        try:
            r = self._session.post(f"{self.base_url}/v1/vision/test", timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("vision_test failed: %s", exc)
            return None

    def rope_config(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/rope-config", timeout=5)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("rope_config failed: %s", exc)
            return None

    def cache_stats(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/cache/stats", timeout=5)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("cache_stats failed: %s", exc)
            return None

    def cache_clear(self) -> dict[str, Any] | None:
        try:
            r = self._session.post(f"{self.base_url}/v1/cache/clear", timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("cache_clear failed: %s", exc)
            return None

    def live_context_search(self, query: str, top_k: int = 5) -> dict[str, Any] | None:
        try:
            r = self._session.post(
                f"{self.base_url}/v1/live-context/search",
                json={"query": query, "top_k": top_k},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("live_context_search failed: %s", exc)
            return None

    def rag_query(self, query: str, top_k: int = 5) -> dict[str, Any] | None:
        try:
            r = self._session.post(
                f"{self.base_url}/v1/rag/query",
                json={"query": query, "top_k": top_k},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("rag_query failed: %s", exc)
            return None

    def body_browse(self, path: str = "", limit: int = 30) -> Any:
        try:
            params: dict[str, Any] = {"limit": limit}
            if path:
                params["path"] = path
            r = self._session.get(f"{self.base_url}/v1/body/browse", params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("body_browse failed: %s", exc)
            return None

    def body_read(self, path: str, max_bytes: int = 16384) -> dict[str, Any] | None:
        try:
            r = self._session.get(
                f"{self.base_url}/v1/body/read",
                params={"path": path, "max_bytes": max_bytes},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("body_read failed: %s", exc)
            return None

    def list_sessions(self) -> list[dict[str, Any]] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/sessions", timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("list_sessions failed: %s", exc)
            return None

    def unified_recall(self, query: str, top_k: int = 5) -> dict[str, Any] | None:
        try:
            r = self._session.post(
                f"{self.base_url}/v1/memory/unified-recall",
                json={"query": query, "top_k": top_k},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("unified_recall failed: %s", exc)
            return None

    def short_term_memory(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/memory/short-term", timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("short_term_memory failed: %s", exc)
            return None

    def clear_short_term(self) -> dict[str, Any] | None:
        try:
            r = self._session.post(f"{self.base_url}/v1/memory/short-term/clear", timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("clear_short_term failed: %s", exc)
            return None

    def eval_history(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/eval/history", timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("eval_history failed: %s", exc)
            return None

    def eval_suggestions(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/eval/suggestions", timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("eval_suggestions failed: %s", exc)
            return None

    def list_checkpoints(self, conv_id: str) -> list[dict[str, Any]] | None:
        try:
            r = self._session.get(
                f"{self.base_url}/v1/conversations/{conv_id}/checkpoints",
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("list_checkpoints failed: %s", exc)
            return None

    def get_checkpoint(self, conv_id: str) -> dict[str, Any] | None:
        try:
            r = self._session.get(
                f"{self.base_url}/v1/conversations/{conv_id}/checkpoint",
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("get_checkpoint failed: %s", exc)
            return None

    def training_files(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/training/files", timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("training_files failed: %s", exc)
            return None

    def admin_status(self) -> dict[str, Any] | None:
        try:
            r = self._session.get(f"{self.base_url}/v1/admin/status", timeout=5)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("admin_status failed: %s", exc)
            return None

    def get(self, path: str, **kwargs: Any) -> Any:
        try:
            r = self._session.get(f"{self.base_url}{path}", timeout=kwargs.pop("timeout", 10), **kwargs)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("GET %s failed: %s", path, exc)
            return None

    def post(self, path: str, json_body: dict[str, Any] | None = None,
             **kwargs: Any) -> Any:
        try:
            r = self._session.post(
                f"{self.base_url}{path}",
                json=json_body,
                timeout=kwargs.pop("timeout", 10),
                **kwargs,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            logger.debug("POST %s failed: %s", path, exc)
            return None

    def _delete(self, path: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
        """Internal: DELETE request — Phase 48 (P1 integration)."""
        try:
            r = self._session.delete(f"{self.base_url}{path}", timeout=10)
            r.raise_for_status()
            return r.json() if r.text else {}
        except requests.RequestException as exc:
            logger.warning("DELETE %s failed: %s", path, exc)
            return fallback if fallback is not None else {"error": str(exc)}

    # ----- Phase 48 (P1) — 6 new endpoint wrappers -----
    def list_auto_skills(self) -> dict[str, Any] | None:
        """GET /v1/skills/auto — list auto-generated skills (Iron Law #42)."""
        try:
            resp = self._session.get(f"{self.base_url}/v1/skills/auto", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("list_auto_skills failed: %s", exc)
            return None

    def delete_skill(self, name: str) -> dict[str, Any] | None:
        """DELETE /v1/skills/{name} — remove a skill by name."""
        try:
            resp = self._session.delete(f"{self.base_url}/v1/skills/{name}", timeout=10)
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("delete_skill failed: %s", exc)
            return None

    def evaluate_conversation(self, conv_id: str) -> dict[str, Any] | None:
        """POST /v1/eval/{conv_id} — auto-evaluate a conversation."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/eval/{conv_id}", timeout=60
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("evaluate_conversation failed: %s", exc)
            return None

    def inject_live_context(
        self, query: str, max_depth: int = 2, top_k: int = 3
    ) -> dict[str, Any] | None:
        """POST /v1/live-context/inject — inject live project context."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/live-context/inject",
                json={"query": query, "max_depth": max_depth, "top_k": top_k},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("inject_live_context failed: %s", exc)
            return None

    def get_rag_job(self, job_id: str) -> dict[str, Any] | None:
        """GET /v1/rag/job/{job_id} — fetch RAG indexing job status."""
        try:
            resp = self._session.get(
                f"{self.base_url}/v1/rag/job/{job_id}", timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("get_rag_job failed: %s", exc)
            return None

    def analyze_training_data(self) -> dict[str, Any] | None:
        """GET /v1/training/analyze — analyze training data weaknesses."""
        try:
            resp = self._session.get(
                f"{self.base_url}/v1/training/analyze", timeout=30
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("analyze_training_data failed: %s", exc)
            return None

    # ----- Phase 49 (P2) — Skills Manager + Code Playground + Memory Episodes -----
    def list_skills_root(self) -> dict[str, Any] | None:
        """GET /v1/skills — list all skills (RESTful root endpoint).

        Alias for /v1/skills/registry with broader scope (returns full metadata).
        """
        try:
            resp = self._session.get(f"{self.base_url}/v1/skills", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("list_skills_root failed: %s", exc)
            return None

    def forge_skill(
        self,
        name: str,
        description: str,
        code_template: str,
        tags: list[str] | None = None,
        auto_save: bool = False,
    ) -> dict[str, Any] | None:
        """POST /v1/skills/forge — auto-create a skill.

        auto_save=true requires ALPHA_WOLF_FORGE_TOKEN (Iron Law #21).
        Returns dict with success flag + skill_path + metadata.
        """
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/skills/forge",
                json={
                    "name": name,
                    "description": description,
                    "code_template": code_template,
                    "tags": tags or [],
                    "auto_save": auto_save,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("forge_skill failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def install_skill_text(self, name: str, source: str) -> dict[str, Any] | None:
        """POST /v1/skills/text — install a skill from inline Python source.

        Args:
            name: snake_case skill name (no extension)
            source: full Python source code (the file body)
        """
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/skills/text",
                json={"name": name, "source": source},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("install_skill_text failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def safety_check_code(self, code: str) -> dict[str, Any] | None:
        """POST /v1/code-exec/safety-check — AST safety check (no execution).

        Returns dict with: passed (bool), violations, warnings, error.
        """
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/code-exec/safety-check",
                json={"code": code},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("safety_check_code failed: %s", exc)
            return {"passed": False, "error": str(exc)}

    def execute_code(self, code: str, timeout_sec: int = 10) -> dict[str, Any] | None:
        """POST /v1/code-exec/execute — execute Python code in sandbox.

        Backend enforces: AST pre-check + restricted env + 30s max timeout.
        Returns dict with: stdout, stderr, returncode, success.
        """
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/code-exec/execute",
                json={"code": code, "timeout_sec": timeout_sec},
                timeout=max(30, timeout_sec + 5),
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("execute_code failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def list_episodes_plural(
        self, min_importance: int = 1, limit: int = 50
    ) -> list[dict[str, Any]] | None:
        """GET /v1/memory/episodes — list episodes (RESTful plural endpoint).

        Alias for /v1/memory/episode with more RESTful name. Returns a list.
        """
        try:
            resp = self._session.get(
                f"{self.base_url}/v1/memory/episodes",
                params={"min_importance": min_importance, "limit": limit},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("episodes", [])
        except requests.RequestException as exc:
            logger.warning("list_episodes_plural failed: %s", exc)
            return []

    def health_check_root(self) -> dict[str, Any] | None:
        """GET / — root health check (service banner)."""
        try:
            resp = self._session.get(f"{self.base_url}/", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("health_check_root failed: %s", exc)
            return None

    # ----- Phase 50 (P3) — 12 new endpoint wrappers (100% coverage) -----
    def install_skill_legacy(self, name: str, content: str) -> dict[str, Any] | None:
        """POST /v1/install_skill — legacy alias (deprecated)."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/install_skill",
                json={"name": name, "source": content},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("install_skill_legacy failed: %s", exc)
            return {"error": str(exc)}

    def run_skill_legacy(self, skill_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """POST /v1/run_skill — legacy alias (deprecated)."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/run_skill",
                json={"skill_name": skill_name, "arguments": arguments or {}},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("run_skill_legacy failed: %s", exc)
            return {"error": str(exc)}

    def recall_legacy(self, query: str, top_k: int = 5) -> dict[str, Any] | None:
        """POST /v1/recall — legacy alias (deprecated alias for /v1/memory/recall)."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/recall",
                json={"query": query, "top_k": top_k},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("recall_legacy failed: %s", exc)
            return {"error": str(exc)}

    def install_skill_v2(self, name: str, content: str) -> dict[str, Any] | None:
        """POST /v1/skills/install — install skill via v2 endpoint."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/skills/install",
                json={"name": name, "source": content},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("install_skill_v2 failed: %s", exc)
            return {"error": str(exc)}

    def body_tools(self, action: str = "list") -> dict[str, Any] | None:
        """GET/POST /v1/body/tools — internal body tools (debugging)."""
        try:
            if action == "list":
                resp = self._session.get(f"{self.base_url}/v1/body/tools", timeout=10)
            else:
                resp = self._session.post(
                    f"{self.base_url}/v1/body/tools",
                    json={"action": action},
                    timeout=10,
                )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("body_tools failed: %s", exc)
            return {"error": str(exc)}

    def reflect(self, topic: str, insight: str, actionable: str = "") -> dict[str, Any] | None:
        """POST /v1/memory/reflection — store a structured reflection."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/memory/reflection",
                json={
                    "topic": topic,
                    "insight": insight,
                    "actionable": actionable,
                    "trigger": "manual",
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("reflect failed: %s", exc)
            return {"error": str(exc)}

    def resume_stream(self, conv_id: str, from_chunk: int = 0) -> dict[str, Any] | None:
        """GET /v1/chat/stream/resume/{conv_id} — resume interrupted SSE stream.

        Note: returns SSE stream; we only probe existence + return minimal metadata.
        """
        try:
            # SSE endpoint — read first chunk then close to verify reachability
            resp = self._session.get(
                f"{self.base_url}/v1/chat/stream/resume/{conv_id}",
                params={"from_chunk": from_chunk},
                timeout=5,
                stream=True,
            )
            resp.raise_for_status()
            # Close the stream immediately — we only verify the endpoint exists
            resp.close()
            return {
                "status": "streaming_endpoint",
                "conv_id": conv_id,
                "from_chunk": from_chunk,
                "http_status": resp.status_code,
            }
        except requests.RequestException as exc:
            logger.warning("resume_stream failed: %s", exc)
            return {"error": str(exc), "conv_id": conv_id}

    def add_graph_entity(self, name: str, type_: str, description: str = "") -> dict[str, Any] | None:
        """POST /v1/graph/entity — add entity to knowledge graph."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/graph/entity",
                json={
                    "name": name,
                    "node_type": type_,
                    "description": description,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("add_graph_entity failed: %s", exc)
            return {"error": str(exc)}

    def add_graph_relation(
        self, source: str, target: str, relation: str = "related"
    ) -> dict[str, Any] | None:
        """POST /v1/graph/relation — add relation to knowledge graph."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/graph/relation",
                json={
                    "source_id": source,
                    "target_id": target,
                    "edge_type": relation,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("add_graph_relation failed: %s", exc)
            return {"error": str(exc)}

    def export_training_data(self, min_score: float = 7.0, limit: int = 100) -> dict[str, Any] | None:
        """POST /v1/training/export — export successful conversations as training data."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/training/export",
                json={"min_score": min_score, "limit": limit},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("export_training_data failed: %s", exc)
            return {"error": str(exc)}

    def trigger_training(
        self,
        base_model: str = "llama3.1:8b",
        adapter_name: str = "v_self_improve",
        epochs: int = 1,
        confirm_token: str | None = None,
    ) -> dict[str, Any] | None:
        """POST /v1/training/train — trigger a training round (requires ALPHA_WOLF_TRAIN_TOKEN)."""
        try:
            payload = {
                "base_model": base_model,
                "adapter_name": adapter_name,
                "epochs": epochs,
            }
            if confirm_token:
                payload["confirm_token"] = confirm_token
            resp = self._session.post(
                f"{self.base_url}/v1/training/train",
                json=payload,
                timeout=30,
            )
            # Don't raise_for_status — 401/403 is expected without token
            try:
                data = resp.json() if resp.text else {}
            except ValueError:
                data = {"raw": resp.text}
            data["http_status"] = resp.status_code
            return data
        except requests.RequestException as exc:
            logger.warning("trigger_training failed: %s", exc)
            return {"error": str(exc)}

    def run_skill_by_name(
        self, skill_name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """POST /v1/skills/{skill_name}/run — run skill by name."""
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/skills/{skill_name}/run",
                json={"arguments": arguments or {}},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.RequestException as exc:
            logger.warning("run_skill_by_name failed: %s", exc)
            return {"error": str(exc)}


# ============================================================================
# Formatters
# ============================================================================


def format_timestamp(ts: str | int | float | None) -> str:
    """Format a timestamp into a human-readable string.

    Accepts ISO strings, unix timestamps, or None. Returns bilingual.
    """
    if not ts:
        return "—"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts)
        else:
            # Try ISO format
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(ts)[:19]


def truncate(text: str, max_len: int = 100) -> str:
    """Truncate text with ellipsis if too long."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def get_date_bucket(iso_date: str | None) -> str:
    """Bucket an ISO date string into 'today', 'yesterday', 'previous_7_days'.

    Per Iron Law #33 — clear section labels.
    """
    if not iso_date:
        return "previous_7_days"

    try:
        dt = datetime.fromisoformat(str(iso_date).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc) if dt.tzinfo else datetime.now()

        # Convert now to dt's timezone if dt has tzinfo
        if dt.tzinfo:
            now = now.astimezone(dt.tzinfo)

        diff_days = (now.date() - dt.date()).days

        if diff_days <= 0:
            return "today"
        elif diff_days == 1:
            return "yesterday"
        else:
            return "previous_7_days"
    except (ValueError, TypeError):
        return "previous_7_days"


def group_conversations_by_date(conversations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group conversations into today/yesterday/previous_7_days buckets.

    Per Iron Law #48 (Separated): pure data function, no UI logic.
    """
    groups: dict[str, list[dict[str, Any]]] = {
        "today": [],
        "yesterday": [],
        "previous_7_days": [],
    }
    for conv in conversations:
        # Use last_activity or created_at
        date_field = conv.get("last_activity") or conv.get("created_at")
        bucket = get_date_bucket(date_field)
        groups[bucket].append(conv)
    return groups


def detect_code_blocks(text: str) -> list[dict[str, str]]:
    """Detect fenced code blocks in markdown text.

    Returns list of dicts with 'lang', 'code', 'start', 'end' keys.
    """
    pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    blocks = []
    for match in pattern.finditer(text):
        blocks.append(
            {
                "lang": match.group(1) or "text",
                "code": match.group(2).strip(),
                "start": match.start(),
                "end": match.end(),
            }
        )
    return blocks


def split_text_by_code(text: str) -> list[dict[str, str]]:
    """Split text into alternating text and code segments for rendering."""
    pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    segments = []
    last_end = 0
    for match in pattern.finditer(text):
        if match.start() > last_end:
            segments.append({"type": "text", "content": text[last_end : match.start()]})
        segments.append(
            {
                "type": "code",
                "lang": match.group(1) or "text",
                "content": match.group(2).strip(),
            }
        )
        last_end = match.end()
    if last_end < len(text):
        segments.append({"type": "text", "content": text[last_end:]})
    return segments


def auto_generate_title(first_message: str, max_len: int = 50) -> str:
    """Generate a short title from the first user message.

    Per Iron Law #33 — auto-title from first message for clean sidebar.
    """
    if not first_message:
        return T["new_chat"]

    # Strip extra whitespace
    msg = re.sub(r"\s+", " ", first_message).strip()
    if not msg:
        return T["new_chat"]

    # If short enough, use as-is
    if len(msg) <= max_len:
        return msg

    # Truncate at word boundary
    truncated = msg[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len * 0.6:  # at least 60% used
        truncated = truncated[:last_space]
    return truncated + "..."


def export_chat_as_markdown(messages: list[dict[str, Any]], title: str = "Chat") -> str:
    """Export conversation as Markdown text."""
    lines = [f"# {title}", ""]
    for msg in messages:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        ts = msg.get("ts") or msg.get("created_at", "")
        if ts:
            lines.append(f"_{ts}_")
        lines.append(f"## {role}")
        lines.append("")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


def export_chat_as_json(messages: list[dict[str, Any]], metadata: dict | None = None) -> str:
    """Export conversation as JSON string."""
    data = {
        "metadata": metadata or {},
        "messages": messages,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ============================================================================
# Session helpers
# ============================================================================


def init_session_state(key: str, default: Any) -> Any:
    """Initialize a session state key if not already present."""
    import streamlit as st

    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def get_session(key: str, default: Any = None) -> Any:
    """Get a session state value or return default."""
    import streamlit as st

    return getattr(st.session_state, key, default)


def set_session(key: str, value: Any) -> None:
    """Set a session state value."""
    import streamlit as st

    setattr(st.session_state, key, value)


# ============================================================================
# Cached API client (Streamlit-friendly)
# ============================================================================


def get_api_client() -> APIClient:
    """Return a cached API client instance (per-session)."""
    import streamlit as st

    if "api_client" not in st.session_state:
        st.session_state.api_client = APIClient()
    return st.session_state.api_client


def get_backend_status() -> tuple[bool, str]:
    """Quick backend reachability check.

    Returns (is_online, detail_message).
    """
    client = get_api_client()
    if client.health_check():
        return True, T["backend_connected"]
    return False, T["backend_offline"]
