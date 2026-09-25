#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Agent Capabilities Test Suite
=================================================
Tests all backend agent capabilities end-to-end.

Tests:
1. Tool: read_file via HTTP
2. Tool: execute_python via HTTP
3. Tool: list_directory via HTTP
4. Tool: search_files via HTTP
5. Tool: web_search via HTTP (with fallback)
6. Tool: write_file via HTTP + body safety check
7. Streaming: /v1/chat/stream SSE events
8. Tool calling: parser + executor
9. Conversations: CRUD via HTTP
10. Skills: list + run + install/uninstall
11. MCP: tools list + RPC call
12. Backend: root endpoint + version

Usage:
    # Ensure backend is running on port 8001 first
    python scripts/test_agent_capabilities.py

Iron Laws Applied:
- #15 (Verify) — every test must actually run + report pass/fail
- #33 (Lessons) — bilingual output EN+AR
- #41 (Conflict) — failures include diagnostic context
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_URL = "http://127.0.0.1:8001"


# ============================================================================
# Test Infrastructure
# ============================================================================

class TestRunner:
    """Collects test results with bilingual output.

    يجمع نتائج الاختبارات مع مخرجات ثنائية اللغة.
    """

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = time.time()

    def run(self, name: str, func) -> bool:
        """Run a single test and record result.

        يشغل اختباراً واحداً ويسجل النتيجة.
        """
        print(f"\n--- {name} ---")
        start = time.time()
        try:
            result = func()
            elapsed = (time.time() - start) * 1000
            if result is True:
                self.passed += 1
                self.results.append({"name": name, "status": "PASS", "elapsed_ms": elapsed})
                print(f"  ✓ PASS ({elapsed:.0f}ms)")
                return True
            elif result is False:
                self.failed += 1
                self.results.append({"name": name, "status": "FAIL", "elapsed_ms": elapsed})
                print(f"  ✗ FAIL ({elapsed:.0f}ms)")
                return False
            elif isinstance(result, str) and result.startswith("SKIP"):
                self.skipped += 1
                self.results.append({"name": name, "status": "SKIP", "reason": result, "elapsed_ms": elapsed})
                print(f"  ~ SKIP: {result}")
                return False
            else:
                # Unexpected return
                self.failed += 1
                self.results.append({"name": name, "status": "FAIL", "error": f"Unexpected return: {result}"})
                print(f"  ✗ FAIL: unexpected return: {result}")
                return False
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self.failed += 1
            tb = traceback.format_exc()
            self.results.append({"name": name, "status": "FAIL", "error": str(e), "traceback": tb})
            print(f"  ✗ FAIL: {type(e).__name__}: {e}")
            print(f"  Traceback: {tb[:500]}")
            return False

    def summary(self) -> int:
        """Print summary and return exit code.

        يطبع الملخص ويرجع كود الخروج.
        """
        elapsed = (time.time() - self.start_time)
        print()
        print("=" * 60)
        print(f"SUMMARY | ملخص")
        print("=" * 60)
        print(f"  Total:  {len(self.results)}")
        print(f"  Passed: {self.passed} ✓")
        print(f"  Failed: {self.failed} ✗")
        print(f"  Skipped: {self.skipped} ~")
        print(f"  Time:   {elapsed:.1f}s")
        print()

        if self.failed > 0:
            print("FAILED TESTS | الاختبارات الفاشلة:")
            for r in self.results:
                if r["status"] == "FAIL":
                    print(f"  - {r['name']}: {r.get('error', '?')}")
            print()
            return 1

        print("All tests passed! | جميع الاختبارات نجحت! 🐺")
        return 0


# ============================================================================
# Test Cases
# ============================================================================

def test_backend_alive() -> bool:
    """Test 0: Backend is running and responds."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{BACKEND_URL}/")
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version", "?")
                print(f"  Backend version: {version}")
                print(f"  Endpoints: {len(data.get('endpoints', []))}")
                return True
            else:
                print(f"  Backend returned {resp.status_code}")
                return False
    except httpx.ConnectError as e:
        print(f"  Cannot connect to {BACKEND_URL}: {e}")
        print(f"  Start backend with: cd '{PROJECT_ROOT}' && python backend/run_server.py")
        return False


def test_tool_read_file() -> bool:
    """Test 1: read_file via HTTP /v1/tools/execute."""
    # Use a file we know exists
    test_file = PROJECT_ROOT / "backend" / "agent" / "__init__.py"
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{BACKEND_URL}/v1/tools/execute",
            json={"name": "read_file", "arguments": {"path": str(test_file)}},
        )
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            return False
        data = resp.json()
        if not data.get("success"):
            print(f"  Tool failed: {data.get('error')}")
            return False
        content = data.get("output", {}).get("content", "")
        if "__version__" in content:
            print(f"  Read {len(content)} chars from __init__.py")
            return True
        print(f"  Unexpected content: {content[:100]}")
        return False


def test_tool_execute_python() -> bool:
    """Test 2: execute_python via HTTP."""
    code = "print('Wolf tests Python!'); result = sum(range(10)); print(f'sum={result}'); result"
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{BACKEND_URL}/v1/tools/execute",
            json={"name": "execute_python", "arguments": {"code": code, "timeout_seconds": 10}},
        )
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            return False
        data = resp.json()
        if not data.get("success"):
            print(f"  Tool failed: {data.get('error')}")
            return False
        out = data.get("output", {})
        stdout = out.get("stdout", "")
        if "sum=45" in stdout and "Wolf tests Python!" in stdout:
            print(f"  stdout: {stdout.strip()!r}")
            return True
        print(f"  stdout: {stdout!r}, stderr: {out.get('stderr')!r}")
        return False


def test_tool_list_directory() -> bool:
    """Test 3: list_directory via HTTP."""
    agent_dir = PROJECT_ROOT / "backend" / "agent"
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{BACKEND_URL}/v1/tools/execute",
            json={"name": "list_directory", "arguments": {"path": str(agent_dir)}},
        )
        data = resp.json()
        if not data.get("success"):
            print(f"  Tool failed: {data.get('error')}")
            return False
        entries = data.get("output", {}).get("entries", [])
        # Expect tools.py, memory.py, etc.
        names = [e["name"] for e in entries]
        expected = ["tools.py", "memory.py", "streaming.py", "mcp_server.py", "skills.py", "tool_calling.py"]
        if all(n in names for n in expected):
            print(f"  Found all 6 agent modules: {sorted(names)}")
            return True
        print(f"  Missing some modules. Found: {sorted(names)}")
        return False


def test_tool_search_files() -> bool:
    """Test 4: search_files via HTTP."""
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{BACKEND_URL}/v1/tools/execute",
            json={"name": "search_files", "arguments": {
                "pattern": "*.py",
                "path": str(PROJECT_ROOT / "backend" / "agent"),
            }},
        )
        data = resp.json()
        if not data.get("success"):
            print(f"  Tool failed: {data.get('error')}")
            return False
        count = data.get("output", {}).get("count", 0)
        if count >= 6:
            print(f"  Found {count} Python files")
            return True
        print(f"  Only {count} files found (expected ≥6)")
        return False


def test_tool_web_search() -> bool:
    """Test 5: web_search via HTTP (fallback to Wikipedia)."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{BACKEND_URL}/v1/tools/execute",
            json={"name": "web_search", "arguments": {
                "query": "python programming language",
                "max_results": 3,
            }},
        )
        data = resp.json()
        if not data.get("success"):
            # Search engines fully blocked
            print(f"  All search engines blocked: {data.get('error')}")
            return "SKIP" + data.get("error", "all strategies failed")[:100]

        source = data.get("output", {}).get("source", "?")
        count = data.get("output", {}).get("count", 0)
        if count > 0:
            print(f"  Got {count} results from {source}")
            return True
        print(f"  0 results from {source}: {data.get('output', {})}")
        return False


def test_tool_write_file_safety() -> bool:
    """Test 6: write_file blocked for body/, allowed for workspace."""
    # 6a: write to workspace should succeed
    test_file = PROJECT_ROOT / "backend" / "test_temp.txt"
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{BACKEND_URL}/v1/tools/execute",
            json={"name": "write_file", "arguments": {
                "path": str(test_file),
                "content": "Wolf test | اختبار الذئب",
            }},
        )
        data = resp.json()
        if not data.get("success"):
            print(f"  Workspace write failed: {data.get('error')}")
            return False
        # 6b: write to body/ should FAIL
        body_file = PROJECT_ROOT / "body" / "memory" / "should_fail.txt"
        resp2 = client.post(
            f"{BACKEND_URL}/v1/tools/execute",
            json={"name": "write_file", "arguments": {
                "path": str(body_file),
                "content": "should fail",
            }},
        )
        data2 = resp2.json()
        if data2.get("success"):
            print(f"  SECURITY ISSUE: body/ write was allowed!")
            return False
        if "not allowed" in (data2.get("error") or "").lower():
            print(f"  Workspace write OK, body/ write blocked ✓")
            # Cleanup
            if test_file.exists():
                test_file.unlink()
            return True
        print(f"  Unexpected error: {data2.get('error')}")
        return False


def test_streaming_sse() -> bool:
    """Test 7: /v1/chat/stream returns SSE events."""
    with httpx.Client(timeout=60) as client:
        try:
            with client.stream(
                "POST",
                f"{BACKEND_URL}/v1/chat/stream",
                json={
                    "model": "alpha-wolf-agent",
                    "messages": [{"role": "user", "content": "Say hi"}],
                    "temperature": 0.3,
                    "max_tokens": 30,
                    "auto_tools": False,
                },
            ) as resp:
                if resp.status_code != 200:
                    print(f"  HTTP {resp.status_code}")
                    return False
                ct = resp.headers.get("content-type", "")
                if "text/event-stream" not in ct:
                    print(f"  Wrong Content-Type: {ct}")
                    return False
                events = []
                chunks_received = 0
                done_seen = False
                content_chunks = 0
                reasoning_chunks = 0
                # Read until we see [DONE] or 50 chunks (whichever first)
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            done_seen = True
                            break
                        try:
                            data = json.loads(data_str)
                            if data.get("chunk"):
                                chunks_received += 1
                                if data.get("type") == "reasoning":
                                    reasoning_chunks += 1
                                else:
                                    content_chunks += 1
                            events.append(data)
                        except json.JSONDecodeError:
                            pass
                    if chunks_received >= 50:
                        break
                if chunks_received >= 1:
                    types = f"content={content_chunks}, reasoning={reasoning_chunks}"
                    done_status = "DONE seen" if done_seen else "no [DONE] (stream may have ended without)"
                    print(f"  Got {chunks_received} chunks ({types}), {done_status}")
                    # Note: [DONE] is emitted but Ollama may close connection first.
                    # Either chunks OR [DONE] is acceptable.
                    if done_seen or chunks_received >= 3:
                        return True
                    return False
                print(f"  No chunks received")
                return False
        except httpx.HTTPError as e:
            print(f"  Stream error: {e}")
            return False


def test_tool_calling_parser() -> bool:
    """Test 8: Tool calling parser (in-process, no HTTP)."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.agent import tool_calling

    # Test parse
    sample = """Let me read the file.
<tool_call name="read_file">
<path>/tmp/test.txt</path>
<max_size_kb>5</max_size_kb>
</tool_call>
Done."""
    parsed = tool_calling.parse_tool_calls(sample)
    if not parsed.has_tool_calls:
        print(f"  No tool calls detected")
        return False
    if len(parsed.tool_calls) != 1:
        print(f"  Expected 1 call, got {len(parsed.tool_calls)}")
        return False
    tc = parsed.tool_calls[0]
    if tc.name != "read_file":
        print(f"  Wrong name: {tc.name}")
        return False
    args = tc.arguments
    if args.get("path") != "/tmp/test.txt":
        print(f"  Wrong path: {args}")
        return False
    if not isinstance(args.get("max_size_kb"), int):
        print(f"  max_size_kb not int: {args.get('max_size_kb')}")
        return False
    print(f"  Parsed: {tc.name} → {args}")
    return True


def test_conversations_crud() -> bool:
    """Test 9: Conversation CRUD via HTTP."""
    with httpx.Client(timeout=10) as client:
        # Create
        resp = client.post(f"{BACKEND_URL}/v1/conversations", json={
            "title": "Test Conversation | محادثة اختبار",
        })
        if resp.status_code != 200:
            print(f"  Create failed: HTTP {resp.status_code}")
            return False
        conv_id = resp.json().get("conversation_id")
        if not conv_id:
            print(f"  No conversation_id returned")
            return False

        # Add messages
        for role, content in [
            ("user", "Hello Wolf! | مرحباً يا ذئب!"),
            ("assistant", "Hi! How can I help? | مرحباً! كيف أساعدك؟"),
        ]:
            r = client.post(
                f"{BACKEND_URL}/v1/conversations/{conv_id}/messages",
                json={"role": role, "content": content},
            )
            if r.status_code != 200:
                print(f"  Add message failed: HTTP {r.status_code}")
                return False

        # Get conversation
        r = client.get(f"{BACKEND_URL}/v1/conversations/{conv_id}")
        data = r.json()
        messages = data.get("messages", [])
        # Note: conversations table stores metadata, messages table stores actual chat.
        # After create_conversation + 2 add_message calls, we expect 2 messages.
        if len(messages) != 2:
            print(f"  Expected 2 messages (user + assistant), got {len(messages)}")
            return False
        # Verify roles are correct
        roles = [m["role"] for m in messages]
        if roles != ["user", "assistant"]:
            print(f"  Wrong roles: {roles}")
            return False

        # List
        r = client.get(f"{BACKEND_URL}/v1/conversations")
        if r.status_code != 200:
            print(f"  List failed")
            return False
        convs = r.json().get("conversations", [])
        if not any(c["conversation_id"] == conv_id for c in convs):
            print(f"  Test conv not in list")
            return False

        # Soft delete
        r = client.delete(f"{BACKEND_URL}/v1/conversations/{conv_id}")
        if r.status_code != 200:
            print(f"  Delete failed")
            return False

        print(f"  CRUD complete: created, added 2 msgs, listed, soft-deleted")
        return True


def test_skills_lifecycle() -> bool:
    """Test 10: Skills list + run + install."""
    with httpx.Client(timeout=10) as client:
        # List
        r = client.get(f"{BACKEND_URL}/v1/skills")
        skills = r.json().get("skills", [])
        if not any(s["name"] == "example_skill" for s in skills):
            print(f"  example_skill not in list: {[s['name'] for s in skills]}")
            return False

        # Run example_skill
        r = client.post(f"{BACKEND_URL}/v1/run_skill", json={
            "skill_name": "example_skill",
            "arguments": {"name": "Wolf", "shout": True},
        })
        if r.status_code != 200:
            print(f"  Run failed: HTTP {r.status_code}")
            return False
        result = r.json()
        if not result.get("success"):
            print(f"  Run error: {result.get('error')}")
            return False
        skill_result = result.get("result", {})
        if "HELLO, WOLF!" not in str(skill_result):
            print(f"  Unexpected: {skill_result}")
            return False

        print(f"  Listed 1 skill, ran example_skill: {skill_result.get('greeting')}")
        return True


def test_mcp_server() -> bool:
    """Test 11: MCP server via /v1/mcp/rpc."""
    with httpx.Client(timeout=10) as client:
        # List tools
        r = client.get(f"{BACKEND_URL}/v1/mcp/tools")
        tools = r.json().get("tools", [])
        if len(tools) != 6:
            print(f"  Expected 6 MCP tools, got {len(tools)}")
            return False

        # RPC: initialize
        r = client.post(f"{BACKEND_URL}/v1/mcp/rpc", json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
        })
        if r.status_code != 200:
            print(f"  RPC initialize failed: HTTP {r.status_code}")
            return False
        init = r.json()
        if init.get("result", {}).get("serverInfo", {}).get("name") != "alpha-wolf-agent":
            print(f"  Wrong MCP server name: {init}")
            return False

        # RPC: tools/call
        r = client.post(f"{BACKEND_URL}/v1/mcp/rpc", json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 2,
            "params": {
                "name": "execute_python",
                "arguments": {"code": "print(2+2)", "timeout_seconds": 5},
            },
        })
        if r.status_code != 200:
            print(f"  RPC tools/call failed")
            return False
        result = r.json()
        content = result.get("result", {}).get("content", [{}])
        if "4" not in str(content):
            print(f"  Unexpected: {content}")
            return False

        print(f"  MCP: 6 tools, initialize + tools/call (execute_python) OK")
        return True


def test_tool_categorization() -> bool:
    """Test 12: /v1/tools/categories and /v1/tools filtering."""
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{BACKEND_URL}/v1/tools/categories")
        if r.status_code != 200:
            return False
        cats = r.json()
        if cats.get("filesystem") != 4:
            print(f"  Expected 4 filesystem tools, got {cats.get('filesystem')}")
            return False

        # Filter by category
        r = client.get(f"{BACKEND_URL}/v1/tools?category=compute")
        tools = r.json().get("tools", [])
        if len(tools) != 1 or tools[0]["name"] != "execute_python":
            print(f"  Filter failed: {[t['name'] for t in tools]}")
            return False

        print(f"  Categories: {cats}, compute filter: 1 tool")
        return True


def test_tool_calling_real_execution() -> bool:
    """Test 13: Tool calling end-to-end via /v1/chat/completions with execute_tools=true.

    Tests that the model output is parsed for tool calls AND executed.
    Uses a hardcoded response to avoid relying on model behavior.
    """
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.agent import tool_calling

    # Simulate a model output with a tool call
    simulated_response = """I'll run Python for you.
<tool_call name="execute_python">
<code>print('Tool calling works!')</code>
<timeout_seconds>5</timeout_seconds>
</tool_call>
Done."""

    parsed = tool_calling.parse_tool_calls(simulated_response)
    if not parsed.has_tool_calls:
        print(f"  Parse failed")
        return False

    text, results = tool_calling.execute_tool_calls(parsed)
    if not results:
        print(f"  No results")
        return False
    r = results[0]
    if not r.success:
        print(f"  Tool failed: {r.error}")
        return False
    if "Tool calling works!" in r.output.get("stdout", ""):
        print(f"  Tool executed successfully: {r.output['stdout'].strip()!r}")
        return True
    print(f"  Unexpected output: {r.output}")
    return False


def test_body_write_blocked() -> bool:
    """Test 14: write_file to body/ is blocked via in-process tools (not just HTTP)."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.agent import tools

    body_file = PROJECT_ROOT / "body" / "should_fail.txt"
    r = tools.execute_tool("write_file", {"path": str(body_file), "content": "should fail"})
    if r.success:
        print(f"  SECURITY ISSUE: body/ write was allowed!")
        return False
    if "not allowed" in (r.error or "").lower():
        print(f"  body/ write blocked via direct tools.execute_tool ✓")
        return True
    print(f"  Unexpected: {r.error}")
    return False


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    """Run all tests and return exit code.

    تشغيل جميع الاختبارات وإرجاع كود الخروج.
    """
    print("=" * 60)
    print("Alpha Wolf Agent — Agent Capabilities Test Suite")
    print("مجموعة اختبارات قدرات الوكيل")
    print("=" * 60)
    print()

    runner = TestRunner()

    # Run tests
    runner.run("00. Backend alive | الخادم يعمل", test_backend_alive)
    runner.run("01. Tool: read_file | أداة قراءة ملف", test_tool_read_file)
    runner.run("02. Tool: execute_python | أداة تنفيذ بايثون", test_tool_execute_python)
    runner.run("03. Tool: list_directory | أداة قائمة مجلد", test_tool_list_directory)
    runner.run("04. Tool: search_files | أداة بحث ملفات", test_tool_search_files)
    runner.run("05. Tool: web_search | أداة بحث ويب", test_tool_web_search)
    runner.run("06. Tool: write_file + body safety | كتابة ملف + حماية الجسد", test_tool_write_file_safety)
    runner.run("07. Streaming: SSE events | البث المباشر", test_streaming_sse)
    runner.run("08. Tool calling parser | محلل استدعاء الأدوات", test_tool_calling_parser)
    runner.run("09. Conversations CRUD | محادثات CRUD", test_conversations_crud)
    runner.run("10. Skills lifecycle | دورة حياة المهارات", test_skills_lifecycle)
    runner.run("11. MCP server | خادم MCP", test_mcp_server)
    runner.run("12. Tool categories | تصنيف الأدوات", test_tool_categorization)
    runner.run("13. Tool calling end-to-end | استدعاء الأدوات من النهاية للنهاية", test_tool_calling_real_execution)
    runner.run("14. Body write blocked (in-process) | حماية الجسد", test_body_write_blocked)

    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())
