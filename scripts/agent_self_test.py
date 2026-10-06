#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Self-Test Suite
====================================

اختبار شامل للوكيل من جهة المستخدم. يحاكي مستخدم بشري يرسل رسائل
ويتحقق من الردود، الأدوات، المهارات، والذاكرة.

Per Quхائد directive 2026-09-25: "تتبعوا ارساله الرساله للوكيل وتلقى ردوده
لتتبع قدرته على استخدام ادواته... الاختبار الحقيقى هو الفيصل"

Run:
    python scripts/agent_self_test.py
    python scripts/agent_self_test.py --quick
    python scripts/agent_self_test.py --interactive  # user persona simulation
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from typing import Any

BACKEND_URL = os.environ.get("ALPHA_WOLF_BACKEND_URL", "http://127.0.0.1:8001")


class Colors:
    """ANSI color codes for terminal output (bilingual UX)."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def log_pass(msg: str) -> None:
    print(f"  {Colors.GREEN}✓{Colors.END} {msg}")


def log_fail(msg: str) -> None:
    print(f"  {Colors.RED}✗{Colors.END} {msg}")


def log_warn(msg: str) -> None:
    print(f"  {Colors.YELLOW}⚠{Colors.END} {msg}")


def log_info(msg: str) -> None:
    print(f"  {Colors.CYAN}ℹ{Colors.END} {msg}")


def log_section(title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}{Colors.END}\n")


def test_backend_health() -> bool:
    """Test 1: Backend health check (Iron Law #15)."""
    log_section("Test 1: Backend Health Check | فحص صحة الـ Backend")
    try:
        r = httpx.get(f"{BACKEND_URL}/v1/body/health", timeout=5)
        if r.status_code == 200:
            data = r.json()
            log_pass(f"Backend reachable at {BACKEND_URL}")
            log_info(f"  ChromaDB: {data.get('chromadb', {}).get('ok')}")
            log_info(f"  NetworkX: {data.get('networkx', {}).get('nodes', 0)} nodes")
            log_info(f"  SQLite: {data.get('sqlite', {}).get('tables', [])}")
            return True
        log_fail(f"Backend returned status {r.status_code}")
        return False
    except Exception as exc:
        log_fail(f"Cannot reach backend: {exc}")
        return False


def test_simple_chat() -> bool:
    """Test 2: Simple chat (no tools) — does the agent respond in Arabic?"""
    log_section("Test 2: Simple Chat (No Tools) | محادثة بسيطة")
    try:
        r = httpx.post(
            f"{BACKEND_URL}/v1/chat/stream",
            json={
                "model": "alpha-wolf-agent-v8",  # FIX 2026-10-06: original broken
                "messages": [{"role": "user", "content": "ما اسمك باختصار؟"}],
                "max_tokens": 2000,
                "auto_tools": False,
            },
            timeout=60,
        )
        if r.status_code != 200:
            log_fail(f"Stream returned status {r.status_code}")
            return False
        # Count event types
        events = {"reasoning": 0, "token": 0, "done": 0}
        tokens: list[str] = []
        for chunk in r.text.split("\n\n"):
            if chunk.startswith("event: reasoning"):
                events["reasoning"] += 1
            elif chunk.startswith("event: token"):
                # Extract chunk
                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        try:
                            obj = json.loads(line[6:])
                            if "chunk" in obj:
                                tokens.append(obj["chunk"])
                        except Exception:
                            pass
                events["token"] += 1
            elif chunk.startswith("event: done"):
                events["done"] += 1

        log_info(f"  Reasoning events: {events['reasoning']}")
        log_info(f"  Token events: {events['token']}")
        log_info(f"  Done events: {events['done']}")

        if events["token"] == 0:
            log_fail("No token events received (agent did not respond!)")
            return False
        full_response = "".join(tokens)
        log_info(f"  Response: {full_response[:200]}")
        if full_response.strip():
            log_pass(f"Agent responded: {len(full_response)} chars")
            return True
        log_fail("Agent response was empty")
        return False
    except Exception as exc:
        log_fail(f"Stream test failed: {exc}")
        return False


def test_tool_calling_read_file() -> bool:
    """Test 3: Tool calling — can agent read a file?"""
    log_section("Test 3: Tool Calling (read_file) | استدعاء أداة قراءة ملف")
    try:
        # Use the actual README in the project
        readme_path = str(PROJECT_ROOT / "README.md").replace("\\", "\\\\")
        r = httpx.post(
            f"{BACKEND_URL}/v1/chat/stream",
            json={
                "model": "alpha-wolf-agent-v8",  # FIX 2026-10-06: original broken
                "messages": [
                    {"role": "user", "content": f"اقرأ الملف {readme_path} وأعطني ملخصاً قصيراً من سطرين."}
                ],
                "max_tokens": 4000,
                "auto_tools": True,
            },
            timeout=90,
        )
        if r.status_code != 200:
            log_fail(f"Stream returned status {r.status_code}")
            return False

        events = {"reasoning": 0, "token": 0, "tool_call": 0, "tool_result": 0, "done": 0}
        tokens: list[str] = []
        tool_name = None
        tool_result_ok = False
        for chunk in r.text.split("\n\n"):
            if chunk.startswith("event: "):
                ev_type = chunk.split("\n")[0].replace("event: ", "").strip()
                events[ev_type] = events.get(ev_type, 0) + 1
                # Extract data
                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        try:
                            obj = json.loads(line[6:])
                            if ev_type == "token" and "chunk" in obj:
                                tokens.append(obj["chunk"])
                            elif ev_type == "tool_call" and "name" in obj:
                                tool_name = obj["name"]
                            elif ev_type == "tool_result":
                                tool_result_ok = obj.get("success", False)
                        except Exception:
                            pass

        log_info(f"  Reasoning: {events['reasoning']}, Tokens: {events['token']}, "
                 f"tool_call: {events['tool_call']}, tool_result: {events['tool_result']}")

        if tool_name != "read_file":
            log_warn(f"Expected tool_call to 'read_file' but got: {tool_name}")
            return False
        log_pass(f"Agent invoked tool: {tool_name}")
        if not tool_result_ok:
            log_warn(f"Tool result success=False (file might not exist)")
        else:
            log_pass("Tool executed successfully")

        full_response = "".join(tokens)
        if "README" in full_response or "Wolf" in full_response or "ملخص" in full_response:
            log_pass("Agent response mentions file content")
        else:
            log_warn(f"Response doesn't seem to mention file: {full_response[:200]}")
        return True
    except Exception as exc:
        log_fail(f"Tool calling test failed: {exc}")
        return False


def test_tool_calling_list_directory() -> bool:
    """Test 4: Tool calling — can agent list a directory?"""
    log_section("Test 4: Tool Calling (list_directory) | استدعاء أداة عرض محتويات مجلد")
    try:
        # Use a more explicit prompt to avoid XML tool_call leakage in answer
        r = httpx.post(
            f"{BACKEND_URL}/v1/chat/stream",
            json={
                "model": "alpha-wolf-agent-v8",  # FIX 2026-10-06: original broken
                "messages": [
                    {"role": "user", "content": "استخدم أداة list_directory لمعرفة محتويات المجلد الحالي. أعطني اسم ملف واحد فقط من النتيجة."}
                ],
                "max_tokens": 4000,
                "auto_tools": True,
            },
            timeout=90,
        )
        if r.status_code != 200:
            log_fail(f"Stream returned status {r.status_code}")
            return False

        # Parse SSE events properly
        events: dict[str, int] = {}
        tool_name = None
        tool_result_ok = False
        tool_result_output: dict[str, Any] = {}
        for chunk in r.text.split("\n\n"):
            if not chunk.startswith("event: "):
                continue
            first_line = chunk.split("\n")[0]
            ev_type = first_line.replace("event: ", "").strip()
            events[ev_type] = events.get(ev_type, 0) + 1
            # Extract data
            for line in chunk.split("\n"):
                if line.startswith("data: "):
                    try:
                        obj = json.loads(line[6:])
                        if ev_type == "tool_call" and "name" in obj:
                            tool_name = obj["name"]
                        elif ev_type == "tool_result":
                            tool_result_ok = obj.get("success", False)
                            tool_result_output = obj
                    except Exception:
                        pass

        log_info(f"  Events: {events}")
        if tool_name != "list_directory":
            log_warn(f"Expected 'list_directory' but got: {tool_name}")
            return False
        log_pass(f"Agent invoked tool: {tool_name}")
        if not tool_result_ok:
            log_warn(f"Tool result success=False")
        else:
            log_pass(f"Tool executed successfully")
            # Show some result data
            output = tool_result_output.get("output", {})
            if isinstance(output, dict):
                entries = output.get("entries", [])
                log_info(f"  Files in directory: {len(entries)}")
                if entries:
                    log_info(f"  First file: {entries[0].get('name', '?')}")
        return True
    except Exception as exc:
        log_fail(f"list_directory test failed: {exc}")
        return False


def test_skills_registry() -> bool:
    """Test 5: Skills registry — can agent use installed skills?"""
    log_section("Test 5: Skills Registry | سجل المهارات")
    try:
        r = httpx.get(f"{BACKEND_URL}/v1/skills", timeout=5)
        if r.status_code != 200:
            log_fail(f"Skills endpoint returned {r.status_code}")
            return False
        data = r.json()
        count = data.get("count", 0)
        skills = data.get("skills", [])
        log_info(f"  Total skills: {count}")
        for skill in skills:
            log_info(f"    • {skill.get('name')}: {skill.get('description', '')[:60]}")
        if count >= 1:
            log_pass(f"{count} skill(s) available")
            return True
        log_warn("No skills installed (agent has no skills to use)")
        return False
    except Exception as exc:
        log_fail(f"Skills test failed: {exc}")
        return False


def test_tools_catalog() -> bool:
    """Test 6: Tools catalog — what tools does the agent have?"""
    log_section("Test 6: Tools Catalog | كتالوج الأدوات")
    try:
        r = httpx.get(f"{BACKEND_URL}/v1/tools", timeout=5)
        if r.status_code != 200:
            log_fail(f"Tools endpoint returned {r.status_code}")
            return False
        data = r.json()
        count = data.get("count", 0)
        tools = data.get("tools", [])
        categories = data.get("categories", [])
        log_info(f"  Total tools: {count}")
        log_info(f"  Categories: {', '.join(categories)}")
        for tool in tools[:10]:
            log_info(f"    • {tool.get('name')}: {tool.get('description', '')[:60]}")
        if count >= 5:
            log_pass(f"{count} tools available across {len(categories)} categories")
            return True
        log_warn(f"Only {count} tools available")
        return False
    except Exception as exc:
        log_fail(f"Tools catalog test failed: {exc}")
        return False


def test_memory_persistence() -> bool:
    """Test 7: Memory — can agent remember previous messages?"""
    log_section("Test 7: Memory Persistence | الذاكرة (استمرارية)")
    try:
        # Create a conversation
        r = httpx.post(
            f"{BACKEND_URL}/v1/conversations",
            json={"title": "Self-test session"},
            timeout=5,
        )
        if r.status_code != 200:
            log_fail(f"Create conversation failed: {r.status_code}")
            return False
        conv_id = r.json().get("conversation_id")
        log_pass(f"Created conversation: {conv_id}")

        # Add a message
        r = httpx.post(
            f"{BACKEND_URL}/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "اسمي محمد", "importance": 5},
            timeout=5,
        )
        if r.status_code != 200:
            log_fail(f"Add message failed: {r.status_code}")
            return False
        log_pass("Added user message")

        # Add assistant message
        r = httpx.post(
            f"{BACKEND_URL}/v1/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "أهلاً محمد", "importance": 5},
            timeout=5,
        )
        if r.status_code != 200:
            log_fail(f"Add assistant message failed: {r.status_code}")
            return False
        log_pass("Added assistant message")

        # Retrieve conversation
        r = httpx.get(
            f"{BACKEND_URL}/v1/conversations/{conv_id}",
            timeout=5,
        )
        if r.status_code != 200:
            log_fail(f"Get conversation failed: {r.status_code}")
            return False
        msgs = r.json().get("messages", [])
        if len(msgs) >= 2:
            log_pass(f"Retrieved conversation with {len(msgs)} messages")
            return True
        log_fail(f"Expected 2 messages, got {len(msgs)}")
        return False
    except Exception as exc:
        log_fail(f"Memory test failed: {exc}")
        return False


def test_live_context_awareness() -> bool:
    """Test 8: Live Context — does agent know about the project?"""
    log_section("Test 8: Live Context Awareness | الوعي بالـ Live Context")
    try:
        r = httpx.post(
            f"{BACKEND_URL}/v1/live-context/inject",
            json={"query": "frontend directory", "max_depth": 2, "top_k": 3},
            timeout=10,
        )
        if r.status_code != 200:
            log_fail(f"Live context endpoint returned {r.status_code}")
            return False
        data = r.json()
        ctx = data.get("context", "")
        if ctx and "frontend" in ctx.lower():
            log_pass(f"Live context found: {len(ctx)} chars")
            log_info(f"  Sample: {ctx[:200]}")
            return True
        log_warn(f"Live context empty or doesn't mention frontend: {ctx[:100]}")
        return False
    except Exception as exc:
        log_fail(f"Live context test failed: {exc}")
        return False


def test_rag_query() -> bool:
    """Test 9: RAG — does the agent have semantic search?"""
    log_section("Test 9: RAG (Retrieval-Augmented Generation) | البحث الدلالي")
    try:
        r = httpx.get(f"{BACKEND_URL}/v1/rag/stats", timeout=5)
        if r.status_code != 200:
            log_fail(f"RAG stats returned {r.status_code}")
            return False
        data = r.json()
        chunks = data.get("total_chunks", 0)
        embedding_model = data.get("embedding_model", "unknown")
        log_info(f"  Embedding model: {embedding_model}")
        log_info(f"  Total chunks: {chunks}")
        if chunks == 0:
            log_warn("RAG has no chunks indexed — semantic search unavailable")
            return False

        log_pass(f"RAG has {chunks} chunks indexed")

        # Try a query — field name is "chunks" not "results" (BUGFIX)
        queries = ["Wolf personality", "Alpha Wolf Agent", "training pipeline", "7 traits"]
        total_pass = 0
        for q in queries:
            r = httpx.post(
                f"{BACKEND_URL}/v1/rag/query",
                json={"query": q, "top_k": 3},
                timeout=10,
            )
            if r.status_code != 200:
                log_warn(f"  Query '{q}' failed: status {r.status_code}")
                continue
            body = r.json()
            # Field name is "chunks" (not "results")
            results = body.get("chunks", [])
            if results:
                top_sim = results[0].get("similarity", 0)
                log_info(f"  Query '{q}': {len(results)} chunks (top sim: {top_sim:.2f})")
                total_pass += 1
            else:
                log_warn(f"  Query '{q}': 0 results")

        if total_pass == len(queries):
            log_pass(f"All {len(queries)} queries returned results — RAG works!")
            return True
        elif total_pass > 0:
            log_warn(f"{total_pass}/{len(queries)} queries returned results (partial)")
            return True
        log_fail("No queries returned results")
        return False
    except Exception as exc:
        log_fail(f"RAG test failed: {exc}")
        return False


def test_mcp_tools() -> bool:
    """Test 10: MCP server — does the agent have MCP tools?"""
    log_section("Test 10: MCP Tools | أدوات MCP")
    try:
        r = httpx.get(f"{BACKEND_URL}/v1/mcp/tools", timeout=5)
        if r.status_code != 200:
            log_warn(f"MCP tools endpoint returned {r.status_code}")
            return False
        data = r.json()
        count = data.get("count", 0)
        tools = data.get("tools", [])
        log_info(f"  MCP tools: {count}")
        for tool in tools[:5]:
            log_info(f"    • {tool.get('name')}: {tool.get('description', '')[:60]}")
        if count >= 1:
            log_pass(f"{count} MCP tools available")
            return True
        log_info("  No MCP tools (this is OK — MCP is optional)")
        return True  # Not a failure, just informational
    except Exception as exc:
        log_info(f"  MCP tools not available: {exc}")
        return True  # Optional


def main() -> int:
    """Run all tests."""
    print(f"\n{Colors.BOLD}🐺 Alpha Wolf Agent — Self-Test Suite{Colors.END}")
    print(f"Backend: {BACKEND_URL}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    tests = [
        ("Backend Health", test_backend_health),
        ("Simple Chat", test_simple_chat),
        ("Tool: read_file", test_tool_calling_read_file),
        ("Tool: list_directory", test_tool_calling_list_directory),
        ("Skills Registry", test_skills_registry),
        ("Tools Catalog", test_tools_catalog),
        ("Memory Persistence", test_memory_persistence),
        ("Live Context", test_live_context_awareness),
        ("RAG Query", test_rag_query),
        ("MCP Tools", test_mcp_tools),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
        except Exception as exc:
            log_fail(f"Test crashed: {exc}")
            passed = False
        results.append((name, passed))

    # Summary
    log_section("Test Summary | ملخص الاختبارات")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        if ok:
            log_pass(f"{name}")
        else:
            log_fail(f"{name}")

    pct = (passed / total * 100) if total > 0 else 0
    color = Colors.GREEN if pct == 100 else Colors.YELLOW if pct >= 70 else Colors.RED
    print(f"\n{Colors.BOLD}{color}Result: {passed}/{total} ({pct:.0f}%) tests passed{Colors.END}")

    if pct == 100:
        print(f"{Colors.GREEN}✅ Alpha Wolf Agent is fully functional!{Colors.END}")
    elif pct >= 70:
        print(f"{Colors.YELLOW}⚠️  Alpha Wolf Agent has some issues — see above{Colors.END}")
    else:
        print(f"{Colors.RED}❌ Alpha Wolf Agent needs fixes — see above{Colors.END}")

    return 0 if pct >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())
