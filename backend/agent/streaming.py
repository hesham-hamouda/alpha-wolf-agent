#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Streaming Module | وحدة البث المباشر
=======================================================
Server-Sent Events (SSE) helpers for streaming chat responses.

SSE format (text/event-stream):
  data: {"chunk": "hello"}\n\n
  data: {"chunk": " world"}\n\n
  data: [DONE]\n\n

Provides:
- format_sse_data() — format a chunk as SSE event
- stream_from_ollama() — async generator that proxies Ollama stream
- Tool result SSE events (type="tool_call", "tool_result", "done")

Iron Laws Applied:
- #15 (Verify)        : Self-test included
- #22 (Autonomous)    : No prompts — stream immediately
- #33 (Lessons)       : Bilingual AR+EN docstrings (Iron Law #47)
- #41 (Conflict)      : Errors include diagnostic context
- #47 (Bilingual)     : Every public function has Arabic translation
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger("alpha_wolf.streaming")


# ============================================================================
# SSE Formatting
# ============================================================================

def format_sse_data(data: Any, event: Optional[str] = None) -> str:
    """Format data as SSE event string.

    تنسيق البيانات كحدث SSE.

    Format:
        event: <event_type>\\n
        data: <json>\\n\\n
    """
    if isinstance(data, (dict, list)):
        json_str = json.dumps(data, ensure_ascii=False)
    else:
        json_str = str(data)

    lines = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json_str}")
    lines.append("")  # Empty line ends the event
    lines.append("")
    return "\n".join(lines)


def format_sse_done() -> str:
    """Format the [DONE] event for end of stream.

    تنسيق حدث [DONE] لنهاية البث.
    """
    return "data: [DONE]\n\n"


# ============================================================================
# Streaming Proxies
# ============================================================================

async def stream_from_ollama(
    base_url: str,
    payload: Dict[str, Any],
    tool_results: Optional[List[Dict[str, Any]]] = None,
) -> AsyncIterator[str]:
    """Stream chat completions from Ollama with optional tool results.

    بث ردود المحادثة من Ollama مع نتائج الأدوات الاختيارية.

    This is the core streaming function used by /v1/chat/stream endpoint.
    """
    import httpx

    # If we have tool results, append them to the last user message
    if tool_results:
        messages = list(payload.get("messages", []))
        if messages:
            last_msg = messages[-1]
            if last_msg.get("role") == "user":
                tool_text = _format_tool_results_text(tool_results)
                last_msg["content"] = last_msg["content"] + "\n\n" + tool_text
                payload["messages"] = messages

    # Inject tool availability into system prompt
    system_msg = {
        "role": "system",
        "content": _build_streaming_system_prompt(),
    }
    payload.setdefault("messages", [])
    if not any(m.get("role") == "system" for m in payload["messages"]):
        payload["messages"].insert(0, system_msg)

    # Force streaming mode
    payload["stream"] = True

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{base_url}/v1/chat/completions",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    # Handle both OpenAI-compatible format (data: {...}) and Ollama native
                    if line.startswith("data: "):
                        line = line[6:]  # Strip "data: " prefix
                    # Stop on [DONE] sentinel
                    if line.strip() == "[DONE]":
                        yield format_sse_done()
                        break
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    chunk_text = ""
                    reasoning_text = ""
                    finish_reason = None

                    # OpenAI-compatible format (Ollama OpenAI mode)
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        chunk_text = delta.get("content", "") or ""
                        reasoning_text = delta.get("reasoning", "") or ""
                        finish_reason = choices[0].get("finish_reason")

                    # Ollama native format
                    if not chunk_text and "message" in data:
                        msg = data.get("message", {})
                        chunk_text = msg.get("content", "") or ""
                        reasoning_text = msg.get("reasoning", "") or ""

                    # Emit content chunks (visible answer)
                    if chunk_text:
                        yield format_sse_data(
                            {"chunk": chunk_text, "type": "content", "done": data.get("done", False)},
                            event="token",
                        )

                    # Emit reasoning chunks (Iron Law #40: M3 reasoning visible to user)
                    if reasoning_text:
                        yield format_sse_data(
                            {"chunk": reasoning_text, "type": "reasoning", "done": data.get("done", False)},
                            event="reasoning",
                        )

                    # Done signal
                    if data.get("done") or finish_reason == "stop":
                        yield format_sse_data(
                            {"done": True},
                            event="done",
                        )
                        yield format_sse_done()
                        break
    except httpx.HTTPError as e:
        logger.error(f"Ollama stream error: {e}")
        yield format_sse_data(
            {"error": str(e), "type": "stream_error"},
            event="error",
        )
    except Exception as e:
        logger.error(f"Unexpected stream error: {e}")
        yield format_sse_data(
            {"error": str(e), "type": "stream_error"},
            event="error",
        )


def _format_tool_results_text(tool_results: List[Dict[str, Any]]) -> str:
    """Format tool results as plain text to feed back to model.

    تنسيق نتائج الأدوات كنص لإعادته للنموذج.
    """
    lines = ["[Tool Results | نتائج الأدوات]"]
    for r in tool_results:
        status = "✓" if r.get("success") else "✗"
        tool = r.get("tool_name", "?")
        if r.get("success"):
            output = r.get("output")
            if isinstance(output, dict):
                output_str = json.dumps(output, ensure_ascii=False, default=str)[:2000]
            else:
                output_str = str(output)[:2000]
            lines.append(f"{status} {tool}: {output_str}")
        else:
            lines.append(f"{status} {tool} ERROR: {r.get('error')}")
    return "\n".join(lines)


def _build_streaming_system_prompt() -> str:
    """Build a streaming-friendly system prompt (shorter than full).

    بناء prompt نظامي قصير للبث المباشر.
    """
    from .tools import format_tools_for_prompt

    base = """You are Alpha Wolf Agent. Be concise and wolf-like.
أنت Alpha Wolf Agent. كن موجزاً وتصرف كذئب.

When you need a tool, output: <tool_call name="X"><arg>value</arg></tool_call>
"""
    return base + "\n" + format_tools_for_prompt()


# ============================================================================
# Tool-Aware Streaming (with auto tool execution)
# ============================================================================

async def stream_with_tool_execution(
    base_url: str,
    payload: Dict[str, Any],
    max_tool_iterations: int = 3,
) -> AsyncIterator[str]:
    """Stream chat completion with automatic tool execution.

    بث رد المحادثة مع تنفيذ الأدوات التلقائي.

    Flow:
    1. Stream initial response from Ollama
    2. If response contains <tool_call> blocks, execute tools
    3. Send tool results back to Ollama as a follow-up stream
    4. Repeat until no more tool calls (max 3 iterations)
    """
    from .tool_calling import parse_tool_calls, execute_tool_calls, format_tool_results_for_followup

    accumulated_text = ""
    current_payload = dict(payload)
    tool_results_history: List[Dict[str, Any]] = []

    for iteration in range(max_tool_iterations):
        accumulated_text = ""
        full_response = ""

        # Stream the response chunk by chunk
        async for sse_chunk in stream_from_ollama(base_url, current_payload):
            yield sse_chunk

            # Parse the chunk to check for tool calls
            # (This is a simplified approach — production should buffer)
            try:
                if sse_chunk.startswith("data: ") and not sse_chunk.startswith("data: [DONE]"):
                    chunk_json = sse_chunk[6:].strip()
                    chunk_data = json.loads(chunk_json)
                    if "chunk" in chunk_data:
                        full_response += chunk_data["chunk"]
            except (json.JSONDecodeError, ValueError):
                pass

        # After stream ends, check if response had tool calls
        parsed = parse_tool_calls(full_response)
        if not parsed.has_tool_calls:
            break  # No tools to execute, done

        # Execute tools
        text, results = execute_tool_calls(parsed)

        # Emit tool execution events
        for i, tc in enumerate(parsed.tool_calls):
            yield format_sse_data(
                {"name": tc.name, "arguments": tc.arguments},
                event="tool_call",
            )
        for i, r in enumerate(results):
            yield format_sse_data(
                r.to_dict(),
                event="tool_result",
            )

        # Save for follow-up
        tool_results_history.extend([r.to_dict() for r in results])

        # Build follow-up payload with tool results appended
        current_payload = dict(payload)
        current_payload["messages"] = list(payload.get("messages", []))
        # Append the assistant's tool-calling response
        current_payload["messages"].append({
            "role": "assistant",
            "content": full_response,
        })
        # Append tool results as user message
        current_payload["messages"].append({
            "role": "user",
            "content": format_tool_results_for_followup(results),
        })


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify SSE formatting works.

    التحقق من تنسيق SSE يعمل.
    """
    print("Running streaming self-tests...")
    print("تشغيل اختبارات البث المباشر...")

    passed = 0
    failed = 0

    # Test 1: format_sse_data with dict
    sse = format_sse_data({"chunk": "hello"}, event="token")
    if sse.startswith("event: token\n") and '"chunk": "hello"' in sse and sse.endswith("\n\n"):
        passed += 1
        print("  ✓ format_sse_data with event")
    else:
        failed += 1
        print(f"  ✗ format_sse_data: {repr(sse)}")

    # Test 2: format_sse_data without event
    sse2 = format_sse_data("hello")
    if sse2.startswith("data: ") and "hello" in sse2:
        passed += 1
        print("  ✓ format_sse_data without event")
    else:
        failed += 1
        print(f"  ✗ format_sse_data simple: {repr(sse2)}")

    # Test 3: format_sse_done
    done = format_sse_done()
    if done == "data: [DONE]\n\n":
        passed += 1
        print("  ✓ format_sse_done")
    else:
        failed += 1
        print(f"  ✗ format_sse_done: {repr(done)}")

    # Test 4: Tool results text formatting
    sample_results = [
        {"tool_name": "read_file", "success": True, "output": {"content": "hi"}, "duration_ms": 5.0, "error": None},
        {"tool_name": "write_file", "success": False, "output": None, "duration_ms": 1.0, "error": "Permission denied"},
    ]
    text = _format_tool_results_text(sample_results)
    if "✓ read_file" in text and "✗ write_file" in text and "Permission denied" in text:
        passed += 1
        print("  ✓ format tool results text")
    else:
        failed += 1
        print(f"  ✗ format_tool_results_text: {text}")

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()
