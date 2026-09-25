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
    "footer_disclaimer": "Alpha Wolf Agent can make mistakes. Verify important info. | قد يخطئ الذئب. تحقق من المعلومات المهمة.",

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
            payload = {"model": "alpha-wolf-agent", "messages": messages}
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
            "model": "alpha-wolf-agent",
            "messages": messages,
            "stream": True,
            "auto_tools": auto_tools,
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
                                if data_str == "[DONE]":
                                    yield {"type": "done"}
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

    # ----- Live Context & RAG -----
    def live_context_summary(self) -> dict[str, Any] | None:
        try:
            resp = self._session.post(
                f"{self.base_url}/v1/live-context/summary",
                json={"max_depth": 2, "search_top_k": 5},
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
