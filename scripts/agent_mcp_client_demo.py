#!/usr/bin/env python3
r"""
Alpha Wolf Agent MCP Tester — Client Demo
=========================================

Demonstrates how to connect to the MCP server and use its tools to test
the Alpha Wolf Agent programmatically.

Per Quхائд directive 2026-09-25:
> "ممكن تنشئوا MCP SERVER خاص بذلك يمكنكم من التواصل مع اى وكيل
> واختباره بهذا الشكل"

Usage:
    # Start the MCP server first:
    python mcp_agent_tester/server.py

    # Then run this client in another terminal:
    python scripts/agent_mcp_client_demo.py

Or use it programmatically:
    from scripts.agent_mcp_client_demo import AlphaWolfTester
    tester = AlphaWolfTester()
    result = tester.send_message("What is your name?")
    print(result)
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AlphaWolfTester:
    """Client for testing Alpha Wolf Agent via MCP server.

    Can be used directly (calls HTTP backend) or via MCP stdio transport.
    """

    def __init__(self, backend_url: str = "http://127.0.0.1:8001"):
        self.backend_url = backend_url
        self.results: list[dict[str, Any]] = []

    def send_message(
        self,
        message: str,
        auto_tools: bool = True,
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        """Send a message to Alpha Wolf Agent (direct HTTP, not via MCP)."""
        import httpx

        try:
            r = httpx.post(
                f"{self.backend_url}/v1/chat/stream",
                json={
                    "model": "alpha-wolf-agent-v8",  # FIX 2026-10-06: original broken
                    "messages": [{"role": "user", "content": message}],
                    "temperature": 0.7,
                    "max_tokens": max_tokens,
                    "auto_tools": auto_tools,
                },
                timeout=120,
            )
            if r.status_code != 200:
                return {"success": False, "error": f"Backend returned {r.status_code}"}

            # Parse SSE
            events: dict[str, int] = {}
            tool_calls: list[dict[str, Any]] = []
            tokens: list[str] = []
            for chunk in r.text.split("\n\n"):
                if not chunk.startswith("event: "):
                    continue
                ev_type = chunk.split("\n")[0].replace("event: ", "").strip()
                events[ev_type] = events.get(ev_type, 0) + 1
                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        try:
                            obj = json.loads(line[6:])
                            if ev_type == "token" and "chunk" in obj:
                                tokens.append(obj["chunk"])
                            elif ev_type == "tool_call" and "name" in obj:
                                tool_calls.append(obj)
                        except Exception:
                            pass

            import re
            raw = "".join(tokens)
            cleaned = re.sub(r"<tool_call\b[^>]*>.*?</tool_call>", "", raw, flags=re.DOTALL)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

            return {
                "success": bool(cleaned or tool_calls),
                "final_answer": cleaned,
                "tool_calls": tool_calls,
                "events": events,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def verify_tool(
        self,
        message: str,
        expected_tool: str,
        expected_args_substring: str = "",
    ) -> dict[str, Any]:
        """Send a message and verify a specific tool was called."""
        result = self.send_message(message)

        if not result.get("success"):
            return {
                "invoked": False,
                "recommendation": "FAIL",
                "reason": result.get("error", "Send failed"),
            }

        tool_calls = result.get("tool_calls", [])
        invoked = any(tc.get("name") == expected_tool for tc in tool_calls)

        args_match = False
        actual_args = None
        for tc in tool_calls:
            if tc.get("name") == expected_tool:
                actual_args = tc.get("arguments", {})
                if expected_args_substring:
                    args_str = json.dumps(actual_args, ensure_ascii=False)
                    args_match = expected_args_substring in args_str
                else:
                    args_match = True
                break

        if invoked and args_match:
            recommendation = "PASS"
        elif invoked:
            recommendation = "PARTIAL"
        else:
            recommendation = "FAIL"

        return {
            "invoked": invoked,
            "args_match": args_match,
            "actual_args": actual_args,
            "final_answer": result.get("final_answer", ""),
            "recommendation": recommendation,
        }

    def get_state(self) -> dict[str, Any]:
        """Get Alpha Wolf Agent state."""
        import httpx

        state: dict[str, Any] = {"backend_url": self.backend_url}
        try:
            r = httpx.get(f"{self.backend_url}/v1/body/health", timeout=3)
            state["backend_alive"] = r.status_code == 200
        except Exception as exc:
            state["backend_alive"] = False
            state["error"] = str(exc)
            return state

        for endpoint, name in [
            ("/v1/tools", "tools"),
            ("/v1/skills", "skills"),
            ("/v1/conversations?limit=100", "conversations"),
            ("/v1/rag/stats", "rag"),
            ("/v1/mcp/tools", "mcp_tools"),
        ]:
            try:
                r = httpx.get(f"{self.backend_url}{endpoint}", timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    if name == "tools":
                        state["tools_count"] = data.get("count", 0)
                    elif name == "skills":
                        state["skills_count"] = data.get("count", 0)
                    elif name == "conversations":
                        state["conversations_count"] = data.get("count", 0)
                    elif name == "rag":
                        state["rag_chunks"] = data.get("total_chunks", 0)
                    elif name == "mcp_tools":
                        state["mcp_tools_count"] = data.get("count", 0)
            except Exception:
                pass

        return state

    def run_full_suite(self) -> dict[str, Any]:
        """Run all 10 self-tests and return report."""
        tests: list[dict[str, Any]] = []

        # Test 1: Health
        state = self.get_state()
        tests.append({
            "name": "Backend Health",
            "passed": state.get("backend_alive", False),
            "details": f"Tools: {state.get('tools_count', '?')}, Skills: {state.get('skills_count', '?')}",
        })

        # Test 2: Simple Chat
        r2 = self.send_message("ما اسمك باختصار؟", max_tokens=2000)
        tests.append({
            "name": "Simple Chat",
            "passed": r2.get("success", False),
            "details": r2.get("final_answer", "")[:80],
        })

        # Test 3: Tool read_file
        readme_path = str(PROJECT_ROOT / "README.md").replace("\\", "\\\\")
        r3 = self.verify_tool(
            f"اقرأ الملف {readme_path} وأعطني سطراً واحداً.",
            "read_file", "README",
        )
        tests.append({
            "name": "Tool: read_file",
            "passed": r3.get("recommendation") == "PASS",
            "details": f"Recommendation: {r3.get('recommendation')}",
        })

        # Test 4: Tool list_directory
        r4 = self.verify_tool(
            "استخدم list_directory لمعرفة محتويات المجلد الحالي. أعطني اسم ملف واحد.",
            "list_directory",
        )
        tests.append({
            "name": "Tool: list_directory",
            "passed": r4.get("recommendation") in ("PASS", "PARTIAL"),
            "details": f"Recommendation: {r4.get('recommendation')}",
        })

        # Test 5: Skills
        try:
            import httpx
            r5 = httpx.get(f"{self.backend_url}/v1/skills", timeout=5)
            data5 = r5.json()
            count5 = data5.get("count", 0)
            tests.append({
                "name": "Skills Registry",
                "passed": count5 >= 1,
                "details": f"{count5} skills",
            })
        except Exception as exc:
            tests.append({"name": "Skills Registry", "passed": False, "details": str(exc)})

        # Test 6: Tools
        try:
            import httpx
            r6 = httpx.get(f"{self.backend_url}/v1/tools", timeout=5)
            data6 = r6.json()
            count6 = data6.get("count", 0)
            tests.append({
                "name": "Tools Catalog",
                "passed": count6 >= 5,
                "details": f"{count6} tools",
            })
        except Exception as exc:
            tests.append({"name": "Tools Catalog", "passed": False, "details": str(exc)})

        # Test 7: Memory
        try:
            import httpx
            r7 = httpx.post(f"{self.backend_url}/v1/conversations",
                          json={"title": "MCP client test"}, timeout=5)
            conv_id = r7.json().get("conversation_id") if r7.status_code == 200 else None
            tests.append({
                "name": "Memory Persistence",
                "passed": bool(conv_id),
                "details": f"Conv: {conv_id[:8] if conv_id else 'N/A'}...",
            })
        except Exception as exc:
            tests.append({"name": "Memory Persistence", "passed": False, "details": str(exc)})

        # Test 8: Live Context
        try:
            import httpx
            r8 = httpx.post(f"{self.backend_url}/v1/live-context/inject",
                          json={"query": "frontend", "max_depth": 2, "top_k": 3}, timeout=10)
            data8 = r8.json()
            ctx8 = data8.get("context", "")
            tests.append({
                "name": "Live Context",
                "passed": len(ctx8) > 100,
                "details": f"{len(ctx8)} chars",
            })
        except Exception as exc:
            tests.append({"name": "Live Context", "passed": False, "details": str(exc)})

        # Test 9: RAG
        try:
            import httpx
            r9 = httpx.post(f"{self.backend_url}/v1/rag/query",
                          json={"query": "Wolf personality", "top_k": 3}, timeout=10)
            data9 = r9.json()
            chunks9 = data9.get("chunks", [])
            tests.append({
                "name": "RAG Query",
                "passed": len(chunks9) > 0,
                "details": f"{len(chunks9)} chunks" + (f", sim: {chunks9[0].get('similarity', 0):.2f}" if chunks9 else ""),
            })
        except Exception as exc:
            tests.append({"name": "RAG Query", "passed": False, "details": str(exc)})

        # Test 10: MCP Tools
        try:
            import httpx
            r10 = httpx.get(f"{self.backend_url}/v1/mcp/tools", timeout=5)
            data10 = r10.json()
            count10 = data10.get("count", 0)
            tests.append({
                "name": "MCP Tools",
                "passed": count10 >= 1,
                "details": f"{count10} MCP tools",
            })
        except Exception as exc:
            tests.append({"name": "MCP Tools", "passed": False, "details": str(exc)})

        passed = sum(1 for t in tests if t["passed"])
        failed = len(tests) - passed
        return {
            "total": len(tests),
            "passed": passed,
            "failed": failed,
            "tests": tests,
            "summary": "✅ All tests passed" if failed == 0 else f"⚠️ {failed} tests failed",
        }


def main() -> int:
    """Demo: Run all tests via the client class."""
    print("=" * 70)
    print("  🐺 Alpha Wolf Agent — MCP Tester Demo")
    print("=" * 70)
    print()

    tester = AlphaWolfTester()
    result = tester.run_full_suite()

    for t in result["tests"]:
        status = "✅" if t["passed"] else "❌"
        print(f"  {status} {t['name']}: {t['details'][:60]}")

    print()
    pct = (result["passed"] / result["total"] * 100) if result["total"] > 0 else 0
    color = "\033[92m" if pct == 100 else "\033[93m"
    print(f"  {color}Result: {result['passed']}/{result['total']} ({pct:.0f}%) tests passed\033[0m")
    print(f"  {result['summary']}")

    return 0 if pct >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())
