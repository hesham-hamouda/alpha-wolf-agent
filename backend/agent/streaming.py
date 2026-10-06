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
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

logger = logging.getLogger("alpha_wolf.streaming")

# ============================================================================
# Generation Policy + Prompt Budget (FIX 2026-09-26, Round 13)
# ============================================================================
# Two silent killers were found by measurement, not by guessing:
#   1. The served model had num_ctx=4096 while the agent's own prompt (rules +
#      capability map + 22 native tool schemas) is ~7.9k tokens. Ollama
#      TRUNCATED every request to ~2051 tokens, so the model never saw its own
#      rules or its tool list -> it stopped obeying orders and could not call
#      tools. Nothing in the request could raise it (Ollama's OpenAI-compat
#      endpoint IGNORES "options"), so the context is read back from the model
#      itself and the message list is trimmed to fit.
#   2. The served model is a THINKING model: reasoning shares the max_tokens
#      budget, so a small budget yields an EMPTY answer. A floor is enforced
#      and one reasoning-free retry rescues empty streams.

MIN_OUTPUT_TOKENS = int(os.environ.get("AGENT_MIN_TOKENS", "2048"))
REASONING_EFFORT = os.environ.get("AGENT_REASONING_EFFORT", "").strip()
EMPTY_RETRY = os.environ.get("AGENT_EMPTY_RETRY", "1").strip().lower() not in ("0", "false", "no")
CONTEXT_FALLBACK = int(os.environ.get("AGENT_CONTEXT_FALLBACK", "8192"))


# ============================================================================
# Multi-Turn Disclaimer — Phase 52 (2026-10-06, Grade C Fix #4)
# ============================================================================
# Review found P06b/P06c failures: model "forgot" the user's name after
# single-turn `ollama run` sessions. This is a property of stateless CLI,
# not a model defect — but the model didn't acknowledge it. The disclaimer
# below sets the expectation in the system prompt so the model:
#   - Declares its session scope honestly.
#   - Tells the user how to enable persistent context (backend API + conv_id).
# Injected at the TOP of the streaming system prompt.

MULTI_TURN_DISCLAIMER = """
NOTE — SESSION SCOPE: Each request may be processed independently.
For multi-turn conversations with persistent context, use the API with
conversation_id persistence (backend manages memory). Single-turn `ollama run`
CLI does NOT carry context between invocations — this is by design for
stateless inference. If the user asks "what did I say earlier" in a fresh
session, declare the limitation honestly instead of inventing an answer.
ملاحظة SECURE: كل طلب قد يُعالَج بشكل مستقل. للحوار متعدد الأدوار مع
سياق مستمر، استخدم الـ API مع conversation_id. الـ CLI `ollama run` لا يحمل
السياق بين الجلسات — هذا مقصود. إذا سأل المستخدم عن رسالة سابقة في جلسة
جديدة، صرّح بالحدود بدلاً من اختلاق إجابة.
"""

_ctx_cache: dict[str, Any] = {"ts": 0.0, "tokens": CONTEXT_FALLBACK, "source": "fallback"}


def estimate_tokens(text: str) -> int:
    """Estimate prompt tokens (chars/3.2 — measured 3.48 on the real prompt).

    تقدير عدد توكنات الـ prompt.
    """
    if not text:
        return 0
    return int(len(text) / 3.2) + 1


def served_context_tokens(base_url: str = "", refresh: bool = False) -> int:
    """Read the CONTEXT window the served model is actually running with.

    قراءة نافذة السياق الفعلية للنموذج المخدوم (وليس الافتراضي).
    """
    now = time.time()
    if not refresh and now - _ctx_cache["ts"] < 60:
        return int(_ctx_cache["tokens"])
    url = (base_url or os.environ.get("LLAMACPP_BASE_URL")
           or os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    model = os.environ.get("LLAMACPP_MODEL", "alpha-wolf-agent-v8")  # FIX 2026-10-06: original model broken
    tokens, source = CONTEXT_FALLBACK, "fallback"
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=5) as _c:
            # /api/show is POST-only (a GET returns 404 -> silent fallback).
            _r = _c.post(f"{url}/api/show", json={"model": model})
            if _r.status_code == 200:
                # /api/show answers JSON; num_ctx lives in the "parameters" blob.
                _params = (_r.json() or {}).get("parameters", "") or ""
                for _line in str(_params).splitlines():
                    if _line.strip().startswith("num_ctx"):
                        try:
                            tokens = int(_line.split()[-1])
                            source = "ollama:/api/show"
                        except ValueError:
                            pass
                        break
    except Exception as _e:
        logger.debug("  [Budget] context probe failed: %s", _e)
    _ctx_cache.update({"ts": now, "tokens": tokens, "source": source})
    logger.info("  [Budget] served context = %d tokens (%s)", tokens, source)
    return tokens


def apply_generation_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce a non-starvable output budget + optional reasoning effort.

    فرض حد أدنى لمخرجات النموذج حتى لا يبتلع التفكير الحصة ويجيب فارغاً.
    """
    try:
        cur = int(payload.get("max_tokens") or 0)
    except (TypeError, ValueError):
        cur = 0
    if cur < MIN_OUTPUT_TOKENS:
        logger.info("  [Budget] max_tokens %s -> floor %d", cur, MIN_OUTPUT_TOKENS)
        payload["max_tokens"] = MIN_OUTPUT_TOKENS
    if REASONING_EFFORT:
        payload["reasoning_effort"] = REASONING_EFFORT
    return payload


def fit_messages_to_budget(
    messages: List[Dict[str, Any]],
    context_tokens: int,
    reserve: int = MIN_OUTPUT_TOKENS,
) -> Tuple[List[Dict[str, Any]], int]:
    """Compress (prefer) or truncate (fallback) messages to fit context.

    ضغط (مفضل) أو اقتطاع (احتياطي) للرسائل لتناسب الـ context.

    System messages (rules/capability map/RAG) are NEVER dropped: losing
    them is exactly what made the Wolf stop following orders.

    Strategy (P1-1, Round 25, 2026-09-29):
      1. If the prompt already fits → return as-is.
      2. Try LLM-based compression (summarize oldest turns into one
         system message while keeping the last 2 turns verbatim).
      3. On any compression failure → fall back to oldest-first drop.

    FIX 2026-10-04 (Phase 41 — RC4): before the budget check, if the system
    messages alone exceed 50% of the budget, shrink the capability map
    (largest system block) by keeping the first 30 + last 10 lines.
    """
    budget = max(1024, context_tokens - reserve)
    total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)

    # FIX 2026-10-04 (Phase 41 — RC4): shrink an oversized capability map
    # BEFORE the budget check. Without this the function would either compress
    # user history (losing context) or hit the truncation fallback while
    # leaving the giant capability map intact — exactly the failure mode
    # that triggered RC3.
    if total_chars > budget * 3.2:
        for m in messages:
            if m.get("role") == "system" and "capability map" in (m.get("content") or "").lower():
                content = m["content"]
                lines = content.split("\n")
                if len(lines) > 50:
                    m["content"] = "\n".join(
                        lines[:30]
                        + ["... (capability map truncated for context budget) ..."]
                        + lines[-10:]
                    )
                    logger.warning(
                        "  [Budget] truncated capability map from %d → %d lines",
                        len(lines), 40,
                    )
        total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)

    if total_chars <= budget:
        return messages, 0

    # Try compression first (preserves more information than truncation)
    try:
        compressed = compress_old_messages(messages, target_chars=budget)
        new_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in compressed)
        if new_chars <= budget:
            dropped = len(messages) - len(compressed)
            logger.info(
                "  [Budget] compressed %d → %d msgs (%d → %d chars)",
                len(messages), len(compressed), total_chars, new_chars,
            )
            return compressed, dropped
    except Exception as e:
        logger.warning(f"  [Budget] compression failed: {e}, falling back to truncation")

    # Fallback: drop oldest non-system messages
    kept = list(messages)
    dropped = 0
    while estimate_tokens(json.dumps(kept, ensure_ascii=False)) > budget:
        idx = next((i for i, m in enumerate(kept)
                    if m.get("role") not in ("system",)), None)
        if idx is None:
            break
        kept.pop(idx)
        dropped += 1
    if dropped:
        logger.warning("  [Budget] trimmed %d old message(s) to fit %d tokens",
                       dropped, context_tokens)
    return kept, dropped


def compress_old_messages(
    messages: List[Dict[str, Any]],
    target_chars: int = 4000,
) -> List[Dict[str, Any]]:
    """Compress old messages via LLM summarization (Iron Law #33).

    ضغط الرسائل القديمة عبر تلخيص النموذج.

    Replaces oldest non-system messages with a single summary system
    message. Preserves the original system messages (rules + tools).
    Keeps the last 2 user-facing messages for immediate context.
    Returns compressed list fitting target_chars budget. Falls back to
    truncation if the LLM call fails.
    """
    if not messages:
        return messages

    # Split: system messages (untouchable) vs others
    system_msgs: List[Dict[str, Any]] = []
    user_msgs: List[Dict[str, Any]] = []
    for m in messages:
        if m.get("role") == "system":
            system_msgs.append(m)
        else:
            user_msgs.append(m)

    if not user_msgs:
        return messages  # nothing to compress

    total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    if total_chars <= target_chars:
        return messages

    # Build a summary of user_msgs (excluding the last 2 to keep them verbatim)
    to_summarize = user_msgs[:-2] if len(user_msgs) > 2 else user_msgs[:-1]
    keep_recent = user_msgs[-2:] if len(user_msgs) >= 2 else user_msgs[-1:]

    if not to_summarize:
        return messages  # not enough to compress meaningfully

    summary_text = _summarize_via_llm(to_summarize, max_chars=max(500, target_chars // 3))
    if not summary_text:
        # Fallback: truncate oldest
        return _truncate_old_messages(messages, target_chars)

    summary_msg = {
        "role": "system",
        "content": (
            f"[Conversation Summary | ملخص المحادثة]\n"
            f"The following is a compressed summary of earlier turns "
            f"to fit the context budget:\n\n{summary_text}"
        ),
    }

    compressed = list(system_msgs) + [summary_msg] + list(keep_recent)
    new_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in compressed)
    logger.info(
        "  [Compression] %d msgs (%d chars) → %d msgs (%d chars) [summarized %d]",
        len(messages), total_chars, len(compressed), new_chars, len(to_summarize),
    )
    return compressed


def _summarize_via_llm(messages: List[Dict[str, Any]], max_chars: int = 2000) -> str:
    """Summarize conversation via Ollama (one-shot call, no tools).

    تلخيص المحادثة عبر Ollama (استدعاء واحد، بدون أدوات).
    """
    try:
        import requests as _req
    except ImportError:
        return ""

    text_to_summarize = "\n".join(
        f"{m.get('role', '?')}: {str(m.get('content', ''))[:500]}"
        for m in messages
    )

    prompt = (
        "Summarize this conversation in Arabic/English (preserve key facts, "
        "decisions, tool calls, user preferences):\n"
        f"{text_to_summarize[:8000]}\n\n"
        f"Output ONLY the summary (max {max_chars} chars), no preamble."
    )

    base_url = (
        os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("LLAMACPP_BASE_URL")
        or "http://localhost:11434"
    ).rstrip("/")
    model = os.environ.get("LLAMACPP_MODEL", "alpha-wolf-agent-v8")  # FIX 2026-10-06: original model broken

    try:
        r = _req.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max(64, max_chars // 4),
                    "temperature": 0.3,
                },
            },
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning(f"  [Compression] Ollama returned {r.status_code}")
            return ""
        return (r.json().get("response") or "").strip()[:max_chars]
    except Exception as e:
        logger.warning(f"  [Compression] LLM call failed: {type(e).__name__}: {e}")
        return ""


def _truncate_old_messages(
    messages: List[Dict[str, Any]],
    target_chars: int,
) -> List[Dict[str, Any]]:
    """Fallback: drop oldest non-system messages until under budget.

    احتياطي: حذف أقدم الرسائل غير الـ system حتى يصبح الحجم ضمن الحد.
    """
    result: List[Dict[str, Any]] = [m for m in messages if m.get("role") == "system"]
    remaining_budget = target_chars - sum(
        len(json.dumps(m, ensure_ascii=False)) for m in result
    )

    for m in reversed(messages):
        if m.get("role") == "system":
            continue
        if remaining_budget <= 0:
            break
        size = len(json.dumps(m, ensure_ascii=False))
        if size <= remaining_budget:
            result.append(m)
            remaining_budget -= size

    return result


def prompt_budget_report() -> Dict[str, Any]:
    """Self-knowledge: does the agent's own prompt fit the served context?

    وعي ذاتي: هل يتسع prompt الوكيل داخل سياق النموذج المخدوم؟
    """
    from .tools import to_openai_tools
    sys_prompt = _build_streaming_system_prompt()
    try:
        tools_chars = len(json.dumps(to_openai_tools(), ensure_ascii=False))
    except Exception:
        tools_chars = 0
    ctx = served_context_tokens()
    est = estimate_tokens(sys_prompt) + int(tools_chars / 3.2)
    return {
        "system_prompt_tokens": estimate_tokens(sys_prompt),
        "native_tool_schema_tokens": int(tools_chars / 3.2),
        "total_estimate_tokens": est,
        "served_context_tokens": ctx,
        "context_source": _ctx_cache.get("source", "fallback"),
        "fits": est < ctx - MIN_OUTPUT_TOKENS,
        "headroom_tokens": ctx - est,
        "min_output_tokens": MIN_OUTPUT_TOKENS,
        "reasoning_effort": REASONING_EFFORT or "model_default",
    }


# ============================================================================
# Streaming Resumability — P1-5 (Round 25, 2026-09-29)
# ============================================================================
# Persist each SSE chunk to disk so a reconnecting client can resume from
# the last received chunk_id instead of replaying the whole stream.

_STREAM_RESUME_DIR = Path(
    os.environ.get(
        "ALPHA_WOLF_STREAM_RESUME_DIR",
        str(Path(__file__).resolve().parent.parent / "stream_chunks"),
    )
)


def _save_stream_chunk(conv_id: str, chunk_id: int, chunk_data: str) -> None:
    """Append a stream chunk to disk for resumability.

    حفظ chunk للسماح باستئناف الـ stream.
    """
    if not conv_id:
        return
    try:
        _STREAM_RESUME_DIR.mkdir(parents=True, exist_ok=True)
        chunk_file = _STREAM_RESUME_DIR / f"{conv_id}.chunks"
        # Append format: "{chunk_id}|{chunk_data}\n"
        # Use a tight write — no need to fsync, resumability is best-effort.
        with open(chunk_file, "a", encoding="utf-8") as f:
            f.write(f"{int(chunk_id)}|{chunk_data}\n")
    except Exception as e:
        logger.debug(f"  [Resume] save failed for {conv_id[:8]} chunk {chunk_id}: {e}")


def _load_stream_chunks(
    conv_id: str,
    from_chunk_id: int = 0,
) -> List[Tuple[int, str]]:
    """Load stream chunks from disk for resumption.

    تحميل الـ chunks من الـ disk لاستئناف الـ stream.
    """
    chunk_file = _STREAM_RESUME_DIR / f"{conv_id}.chunks"
    if not chunk_file.exists():
        return []
    chunks: List[Tuple[int, str]] = []
    try:
        with open(chunk_file, "r", encoding="utf-8") as f:
            for line in f:
                if "|" not in line:
                    continue
                cid_str, _, data = line.partition("|")
                try:
                    cid = int(cid_str.strip())
                except ValueError:
                    continue
                if cid >= from_chunk_id:
                    chunks.append((cid, data.rstrip("\n")))
    except Exception as e:
        logger.warning(f"  [Resume] load failed for {conv_id[:8]}: {e}")
    return chunks


def _clear_stream_chunks(conv_id: str) -> None:
    """Clear stream chunks for a conversation (called on stream end).

    مسح الـ chunks لمحادثة (يُستدعى عند انتهاء الـ stream).
    """
    if not conv_id:
        return
    chunk_file = _STREAM_RESUME_DIR / f"{conv_id}.chunks"
    try:
        if chunk_file.exists():
            chunk_file.unlink()
    except Exception as e:
        logger.debug(f"  [Resume] clear failed for {conv_id[:8]}: {e}")


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
    emit_terminal: bool = False,
) -> AsyncIterator[str]:
    """Stream chat completions from Ollama with optional tool results.

    بث ردود المحادثة من Ollama مع نتائج الأدوات الاختيارية.

    This is the core streaming function used by /v1/chat/stream endpoint.

    emit_terminal=False (default, FIX 2026-09-26 Round 14): Ollama closes EVERY
    model call with `data: [DONE]`. Forwarding that per-call sentinel made
    clients treat the FIRST model call as the end of the answer, so any turn
    that used a tool (model call #1 = tool call, model call #2 = answer) was
    cut off before the answer and the UI showed "empty response from backend".
    The tool-loop owner emits exactly one terminal pair at the very end; the
    simple single-shot path passes emit_terminal=True.
    """
    import httpx
    import copy

    # FIX 2026-09-26 (Round 15): deep-copy messages to prevent payload mutation.
    # stream_with_tool_execution creates shallow copies (dict(payload)), so the
    # nested messages list was shared between iterations. When this function
    # modified payload["messages"] in place, it corrupted the original payload,
    # causing the next tool-loop iteration to start with stale/modified history.
    payload = copy.deepcopy(payload)

    # If we have tool results, append them to the last user message
    if tool_results:
        messages = list(payload.get("messages", []))
        if messages:
            last_msg = messages[-1]
            if last_msg.get("role") == "user":
                tool_text = _format_tool_results_text(tool_results)
                last_msg["content"] = last_msg["content"] + "\n\n" + tool_text
                payload["messages"] = messages

    # Inject the Wolf core prompt (rules + capability map + tool list).
    # FIX 2026-09-26 (Round 13): previously injected ONLY when no system
    # message existed, so any RAG / live-context / recall injection silently
    # REPLACED the agent's own rules and tool list. Merge instead of skip.
    # FIX Phase 44 (2026-10-04): extract last user text so the capability map
    # is appended ONLY for capability questions (saves ~6K chars / call).
    payload.setdefault("messages", [])
    _last_user_text = ""
    for _m in reversed(payload["messages"]):
        if _m.get("role") == "user":
            _last_user_text = _m.get("content") or ""
            break
    if not any("HARD TOOL RULES" in (m.get("content") or "")
               for m in payload["messages"] if m.get("role") == "system"):
        payload["messages"].insert(0, {
            "role": "system",
            "content": _build_streaming_system_prompt(last_user_text=_last_user_text),
        })

    # Keep the whole prompt inside the context the model actually runs with,
    # then enforce a non-starvable output budget.
    ctx = served_context_tokens(base_url)
    payload["messages"], _dropped = fit_messages_to_budget(payload["messages"], ctx)
    apply_generation_policy(payload)

    # Force streaming mode
    payload["stream"] = True

    def _terminal() -> AsyncIterator[str]:
        """Single authoritative end-of-stream pair (tagged event + sentinel)."""
        yield format_sse_data({"done": True}, event="done")
        yield format_sse_done()

    # FIX 2026-10-06 (Phase 50.71 — Ollama 500 transient recovery):
    # Wrap the streaming POST in a retry loop so a transient 500 from Ollama
    # (manifest mismatch after model update, VRAM blip, etc) doesn't surface
    # as a hard error to the user. Up to 3 attempts with exponential backoff.
    import asyncio as _asyncio
    _MAX_STREAM_RETRIES = 3

    # Sentinel yielded on the first line of the FIRST successful attempt so we
    # can detect "have we ever streamed" inside the retry loop. We can't just
    # check a bool across `yield`s (each yield pauses the generator and loses
    # local state), so we use the bool as a closure-captured list.
    _streamed_anything: list[bool] = [False]
    _last_stream_error: list[Optional[BaseException]] = [None]

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            for _attempt in range(_MAX_STREAM_RETRIES):
                _t0 = time.time()
                try:
                    _ctx = client.stream(
                        "POST",
                        f"{base_url}/v1/chat/completions",
                        json=payload,
                    )
                    # We use a small inline helper so the `async with` properly
                    # drives __aenter__/__aexit__ (Response itself is NOT a CM).
                    resp = await _ctx.__aenter__()
                except (httpx.HTTPError, Exception) as _open_err:
                    _last_stream_error[0] = _open_err
                    logger.warning(
                        "  [Retry/stream] open error (attempt %d/%d): %s: %s",
                        _attempt + 1, _MAX_STREAM_RETRIES,
                        type(_open_err).__name__, _open_err,
                    )
                    if _attempt < _MAX_STREAM_RETRIES - 1:
                        await _asyncio.sleep(2 ** _attempt)
                    continue

                if resp.status_code != 200:
                    _elapsed = (time.time() - _t0) * 1000
                    if resp.status_code == 500:
                        logger.warning(
                            "  [Retry/stream] Ollama 500 (attempt %d/%d, %.0fms) — model=%s, "
                            "msgs=%d, max_tokens=%d",
                            _attempt + 1, _MAX_STREAM_RETRIES, _elapsed,
                            payload.get("model"), len(payload.get("messages", [])),
                            payload.get("max_tokens"),
                        )
                    else:
                        logger.warning(
                            "  [Retry/stream] Ollama HTTP %d (attempt %d/%d, %.0fms)",
                            resp.status_code, _attempt + 1, _MAX_STREAM_RETRIES, _elapsed,
                        )
                    try:
                        await _ctx.__aexit__(None, None, None)
                    except Exception:
                        pass
                    if resp.status_code == 500 and _attempt < _MAX_STREAM_RETRIES - 1:
                        await _asyncio.sleep(2 ** _attempt)
                        continue
                    # Non-500 (or final 500): surface as error event.
                    yield format_sse_data(
                        {"error": f"Ollama HTTP {resp.status_code}",
                         "type": "stream_unavailable",
                         "after_attempts": _attempt + 1},
                        event="error",
                    )
                    for _t in _terminal():
                        yield _t
                    return

                # SUCCESS: resp.status_code == 200. Read it.
                # Note: Response from `client.stream()` is NOT itself an async
                # context manager, but `_ctx` IS — we close it via __aexit__
                # at the end (using try/finally so a streaming exception
                # still releases the connection).
                try:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        # Handle both OpenAI-compatible format (data: {...}) and Ollama native
                        if line.startswith("data: "):
                            line = line[6:]  # Strip "data: " prefix
                        # Stop on [DONE] sentinel
                        if line.strip() == "[DONE]":
                            _streamed_anything[0] = True
                            if emit_terminal:
                                for _t in _terminal():
                                    yield _t
                            break
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        chunk_text = ""
                        reasoning_text = ""
                        finish_reason = None
                        tool_calls_delta: list = []

                        # OpenAI-compatible format (Ollama OpenAI mode)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            chunk_text = delta.get("content", "") or ""
                            reasoning_text = delta.get("reasoning", "") or ""
                            finish_reason = choices[0].get("finish_reason")
                            # FIX 2026-09-25: capture native tool_calls deltas
                            # (previously dropped, so auto-tools never fired).
                            tool_calls_delta = delta.get("tool_calls") or []
                            if tool_calls_delta:
                                # Stash on payload for the caller to accumulate.
                                # stream_from_ollama is an async generator; we emit
                                # them as dedicated SSE events so the tool executor
                                # can reconstruct the full call.
                                for tc in tool_calls_delta:
                                    yield format_sse_data(
                                        {"tool_call_delta": tc, "type": "tool_call_delta"},
                                        event="tool_call_delta",
                                    )

                        # Ollama native format
                        if not chunk_text and "message" in data:
                            msg = data.get("message", {})
                            chunk_text = msg.get("content", "") or ""
                            reasoning_text = msg.get("reasoning", "") or ""

                        # Emit content chunks (visible answer)
                        if chunk_text:
                            _streamed_anything[0] = True
                            yield format_sse_data(
                                {"chunk": chunk_text, "type": "content", "done": data.get("done", False)},
                                event="token",
                            )

                        # Emit reasoning chunks (Iron Law #40: M3 reasoning visible to user)
                        if reasoning_text:
                            _streamed_anything[0] = True
                            yield format_sse_data(
                                {"chunk": reasoning_text, "type": "reasoning", "done": data.get("done", False)},
                                event="reasoning",
                            )

                        # Done signal
                        if data.get("done") or finish_reason == "stop":
                            _streamed_anything[0] = True
                            if emit_terminal:
                                for _t in _terminal():
                                    yield _t
                            break
                finally:
                    # Always release the streaming connection, regardless of
                    # whether the consumer exhausted the generator or broke.
                    try:
                        await _ctx.__aexit__(None, None, None)
                    except Exception as _close_err:
                        logger.debug(f"  [Retry/stream] close error (ignored): {_close_err}")
                # Stream completed (or hit terminal sentinel). Break the retry loop.
                if _streamed_anything[0]:
                    return
                # Stream ended with no tokens AND no terminal sentinel — treat
                # as a 500-class transient failure and retry if possible.
                if _attempt < _MAX_STREAM_RETRIES - 1:
                    logger.warning(
                        "  [Retry/stream] empty stream (attempt %d/%d) — retrying",
                        _attempt + 1, _MAX_STREAM_RETRIES,
                    )
                    await _asyncio.sleep(2 ** _attempt)
                    continue
                # Final attempt also empty — surface a clean error event.
                yield format_sse_data(
                    {"error": "Ollama stream ended with no tokens",
                     "type": "empty_stream",
                     "after_attempts": _MAX_STREAM_RETRIES},
                    event="error",
                )
                for _t in _terminal():
                    yield _t
                return
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
                output_str = json.dumps(output, ensure_ascii=False, default=str)[:5000]
            else:
                output_str = str(output)[:5000]
            lines.append(f"{status} {tool}: {output_str}")
        else:
            lines.append(f"{status} {tool} ERROR: {r.get('error')}")
    lines.append(
        "\n\n=== SYSTEM INSTRUCTION ===\n"
        "CRITICAL: Do NOT copy the '[Tool Results]' header or any raw output above "
        "into your answer. The data above is REAL — READ it, then ANSWER the user's "
        "question USING that data. Synthesize a concise response in your own words. "
        "Never repeat the tool output verbatim."
    )
    return "\n".join(lines)


def _build_streaming_system_prompt(last_user_text: Optional[str] = None) -> str:
    """Build a streaming-friendly system prompt (shorter than full).

    بناء prompt نظامي قصير للبث المباشر.

    FIX 2026-09-26 (user-observed failures):
    - Model summarized a file WITHOUT calling read_file when asked to read it.
    - Model claimed "web search done" and invented links WITHOUT calling web_search.
    Rules below force tool-first behavior for these cases.

    FIX Phase 44 (2026-10-04): capability map (~6K chars) was injected on
    EVERY prompt, pushing total above the served context budget. Now the
    capability map is appended ONLY when the user asks about capabilities
    (Iron Law #41: tool names stay embedded in the rules, only verbose
    description is conditional — never break tool calling).
    """
    _CAPABILITY_KEYWORDS = (
        "what can you", "ماذا تستطيع", "ماذا يمكنك", "قدرات",
        "your tools", "your skills", "your capabilities",
        "قواعد البيانات", "قاعدة بيانات", "قاعدة معرفية",
        "الأدوات", "ادواتك", "مهاراتك",
        "knowledge base", "persistent memory", "do you have",
        "هل تستطيع", "هل لديك", "تستطيع الوصول",
    )
    _last = (last_user_text or "").lower()
    _include_capability_map = any(kw in _last for kw in _CAPABILITY_KEYWORDS)
    from .tools import format_tools_for_prompt

    base = MULTI_TURN_DISCLAIMER + """

You are Alpha Wolf Agent. Be concise, professional, and helpful.
أنت Alpha Wolf Agent. كن موجزاً ومهنياً ومفيداً.

HARD TOOL RULES (must obey):
1. You DO have live tools, including web_search (real internet access). NEVER claim you lack internet access or cannot browse.
1b. 👁️ YOU HAVE DATABASE / MEMORY TOOLS — NEVER REFUSE OR LIE:
   You carry a FULL 4-layer memory + knowledge base stack. NEVER claim
   "لا أستطيع الوصول إلى قواعد البيانات", "I cannot access databases",
   "I don't have persistent memory", "no database access", or similar.
   When asked ANY variant of "do you have databases?", "هل تستطيع الوصول
   إلى قواعد البيانات", "do you have memory?", "persistent memory?",
   "knowledge base?", "KB?":
   → ANSWER "نعم، عندي قاعدة معرفية + 4 طبقات ذاكرة" (yes, knowledge base
     + 4 memory layers: short-term, long-term, episodic, semantic).
   → THEN call my_capabilities (live map) OR query_body_kb (live proof)
     and CITE the real returned data in your reply.
   → NEVER invent a refusal. The answer is ALWAYS affirmative + proof.
2. For the CURRENT date/time (today's date, what time is it) → CALL system_time. Never guess, never refuse.
3. If the user explicitly asks to read/open a file, list a directory, or run code → CALL the tool (read_file/list_directory/execute_python). Never answer from memory when a file operation was requested.
4. If the user asks about current facts, versions, news, or anything that may have changed → CALL web_search FIRST, then answer from its results with real links.
5. SIMPLE GREETINGS & SMALL TALK: for "hello", "hi", "how are you", "thank you", or any greeting/pleasantry → answer DIRECTLY. NEVER call web_search, fetch_page, or any tool for these. Tools are for tasks that need external data, not for conversation.
5. NEVER claim you searched the web unless a [Tool Results] block exists in this conversation. NEVER invent URLs — only cite links returned by web_search/fetch_page.
6. When you need a tool, output ONE block and nothing else:
   <tool_call name="TOOL_NAME">
   <parameter_name>value</parameter_name>
   </​tool_call>
   The tag MUST be the real parameter name (<path> for read_file, <code> for execute_python, <query> for web_search). ALWAYS close the block, one call per block. If a tool fits, CALL it instead of describing it.
7. PROJECTS LIVE OUTSIDE YOUR BODY: when asked to create apps/projects/files for the user, build them under D:/A/Applications under development/TESTS (run_shell defaults there). NEVER write projects inside body/ (body is for knowledge/memory/skills only — read-only). CRITICAL: When write_file fails with "read-only" or "permission denied", IMMEDIATELY retry with path D:/A/Applications under development/TESTS/filename. NEVER give up after one failure.
8. LONG TASKS: for multi-step work, FIRST call track_goal with the plan, update_goal as you progress, and list_goals to resume. ALWAYS verify by RUNNING (run_shell/execute_python) — never claim done without executed proof.
9. BUILDING PROJECTS/APPS: when asked to create files or a project, CALL write_file for EVERY file (under D:/A/Applications under development/TESTS), THEN execute it (run_shell/execute_python) and show the REAL executed output. It is FORBIDDEN to present code plus imagined output without tool results — an unverified claim is a lie.
   - EXAMPLES of correct behavior:
     User: "اكتب لي تطبيق Python لـ Todo" → You MUST call: track_goal, write_file (for the main .py file), write_file (for README), then run_shell or execute_python to TEST it, THEN show the real output.
     User: "ابني تطبيق ويب بسيط" → You MUST call: track_goal, write_file (for backend), write_file (for frontend), then run_shell to install + test.
   - WRONG behavior (FORBIDDEN):
     ❌ Presenting ```python code``` blocks as plain markdown without calling write_file.
     ❌ Claiming "تم بنجاح" without executing and showing real tool results.
     ❌ Summarizing what the code would do instead of running it.
     ❌ Outputting code as final answer without tool calls.
   - The user wants EXECUTED PROOF, not code descriptions. ALWAYS call write_file for EVERY file, then run it.
10. SELF-IMPROVEMENT: install skills you need with install_skill (your own code) or install_skill_from_url (skills.sh/GitHub/trusted https — foreign SKILL.md packs are auto-adapted to your identity); run them with run_skill. Diagnose yourself with system_status (device resources) and repair_body (auto-fix gaps); check system_status BEFORE heavy work to protect the machine.
11. NEW SKILLS: when asked for a skill you lack, FIRST check https://www.skills.sh/ (search it with web_search, install via install_skill_from_url) — adapt, don't reinvent. For browser control you carry the playwright-cli playbook skill: drive it via run_shell (snapshot refs are text — made for you).
12. SIGHT: you have no eyes — pixels mean nothing to you. To "see" an image/screenshot, CALL see_image and read its text description (moondream local). One look per need (VRAM swap is slow).
13. KNOW YOURSELF: your LIVE capability map is appended below (servers, places, every tool, skills, recipes). TRUST IT over memory — if asked what you can do, answer FROM it (or call my_capabilities for the freshest copy).
14. LOCAL FILES ARE READABLE: you CAN read the user's drive via read_file (D:/ projects, workspace, file:// links with %20). NEVER claim security restrictions prevent reading local files — that is false. A pasted file:// link is just a local path: read it, then do the task.

15. APPLICATION/AGENT CREATION & SELF-EVOLUTION WORKFLOW:
   a. When asked to create an application, agent, or tool: BREAK the request into discrete files/components (backend, frontend, config, scripts).
   b. CALL write_file for EACH file under D:/A/Applications under development/TESTS, with FULL content including imports, classes, routes, etc.
   c. CALL execute_python OR run_shell to INSTALL dependencies (pip install) if needed, THEN run the creation script.
   d. CALL the resulting executable/script to VERIFY it works, and show the REAL output.
   e. SUMMARIZE what was created and PROVIDE the path(s). NEVER claim creation without executed proof.

16. 24/7 OPERATION & LONG-TASK ENDURANCE:
   a. BEFORE heavy work, CALL system_status to CHECK device resources (RAM, disk, CPU). DEFER if resources insufficient.
   b. FOR long tasks (>{30} min): FIRST call track_goal with a PLAIN plan, UPDATE goal as you PROGRESS, and LIST_goals to RESUME after interruptions.
   c. NEVER claim DONE without executed proof (RUN the tool, capture output, THEN answer).
   d. IF interrupted or ERROR: PERSIST partial state to body/mistakes table, RESUME from last goal. DO NOT lose progress.

17. SELF-REPAIR & CAPABILITY AUTO-RECOVERY:
   a. WHEN any tool FAILS or RETURNS error: CALL repair_body with the error details, then RETRY the tool.
   b. WHEN missing a needed skill: CALL install_skill (your own code) or install_skill_from_url (trusted packs from skills.sh), ADAPT don't reinvent.
   c. DIAGNOSE yourself with system_status after each repair cycle, and ONLY resume when system_status OK.
   c. MAINTAIN a mistakes LOG (automatic) and REVIEW it before starting new long tasks to AVOID repeating failures.

18. IDENTITY PRESERVATION: your 7 WOLF TRAITS (mistake_hunter, goal_persistence, tenacity, deep_thinking, resourceful, self_aware, reinforcement_learning) are FIXED. All actions MUST align with these traits. Never abandon a goal (goal_persistence), NEVER hide mistakes (mistake_hunter).

19. TOOL RESULT HANDLING: When you receive tool results (marked with [Tool Results] or tool role messages), you MUST:
    a. READ the tool output carefully.
    b. ANSWER the user's question USING the data from the tool output.
    c. NEVER copy the '[Tool Results]' header, tool names, or raw JSON into your answer.
    d. NEVER repeat the tool output verbatim — synthesize a concise response FROM the data.
    e. If the tool output is a file, summarize its CONTENT in your own words.
    f. Respond in the SAME language as the user's question.
    g. This applies to ALL tools: read_file, web_search, execute_python, etc.
"""
    try:
        if _include_capability_map:
            from .capabilities import build_capability_map
            base += "\n\n" + build_capability_map() + "\n"
    except Exception:
        pass
    # FIX 2026-10-06 (Phase 46): the full format_tools_for_prompt() injected
    # ~15K chars of EN+AR descriptions + parameter lists, blowing the system
    # prompt past 21K chars and pushing "hi who are you" past 18s. The native
    # OpenAI tools path (to_openai_tools) is already sent to Ollama, so the
    # model sees tool schemas via the API. We keep ONLY a compact name list
    # here (~500 chars) as a safety net for any non-native path. Drops the
    # system prompt from ~21K chars to ~7K chars.
    try:
        from .tools import TOOL_SPECS as _TOOL_SPECS
        tool_names = ", ".join(s.name for s in _TOOL_SPECS)
        compact_tools = (
            "\n\n# Tools (names only — full schema sent via API)\n"
            f"Available: {tool_names}\n"
            'Format: <tool_call name="TOOL_NAME"><arg>value</arg></tool_call>\n'
            "Use the EXACT parameter name as the XML tag."
        )
    except Exception:
        compact_tools = "\n\n(tools sent via native API)"
    return base + compact_tools


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
    from .tool_calling import (
        parse_tool_calls, execute_tool_calls, format_tool_results_for_followup,
        decide_forced_calls, is_refusal_text, neutral_bridge,
    )
    from .tools import execute_tool, parse_openai_tool_calls

    # Deterministic fallbacks (iteration 0 only): when the user explicitly
    # requests search/date/file-ops but the model calls nothing (incl.
    # refusals), the backend runs the tool once and feeds results back.
    # FIX 2026-09-26 (user-observed failures). Helpers live in tool_calling
    # so the non-streaming path shares the exact same logic.

    accumulated_text = ""
    current_payload = dict(payload)
    tool_results_history: List[Dict[str, Any]] = []
    _corrected_once = False
    _empty_retried = False

    # P1-2: extract optional conversation_id for checkpoint snapshots.
    # Callers (e.g. /v1/chat/stream) can inject it into payload["_conv_id"]
    # or payload["conversation_id"] without breaking Ollama's schema.
    _conv_id = (
        payload.get("_conv_id")
        or payload.get("conversation_id")
        or ""
    )

    for iteration in range(max_tool_iterations):
        accumulated_text = ""
        full_response = ""
        # FIX 2026-09-25: accumulate native tool_calls deltas streamed as
        # tool_call_delta events (index -> {id, function:{name, arguments}}).
        native_accum: Dict[int, Dict[str, Any]] = {}

        # Stream the response chunk by chunk
        async for sse_chunk in stream_from_ollama(base_url, current_payload):
            yield sse_chunk

            # Parse the chunk to check for tool calls
            # The chunk is a full SSE block (event: + data: + empty lines)
            # Extract the data line from the SSE block
            try:
                data_line = None
                for line in sse_chunk.split("\n"):
                    if line.startswith("data: "):
                        data_line = line[6:].strip()
                        break
                if data_line and data_line != "[DONE]":
                    chunk_data = json.loads(data_line)
                    if "chunk" in chunk_data:
                        full_response += chunk_data["chunk"]
                    delta_tc = chunk_data.get("tool_call_delta")
                    if isinstance(delta_tc, dict):
                        idx = int(delta_tc.get("index", 0))
                        slot = native_accum.setdefault(
                            idx, {"id": "", "function": {"name": "", "arguments": ""}}
                        )
                        if delta_tc.get("id"):
                            slot["id"] = delta_tc["id"]
                        func = delta_tc.get("function", {})
                        if isinstance(func, dict):
                            if func.get("name"):
                                slot["function"]["name"] += func["name"]
                            args = func.get("arguments", "")
                            if isinstance(args, str):
                                slot["function"]["arguments"] += args
                            elif isinstance(args, dict):
                                # Some servers send dict chunks; merge by dump
                                slot["function"]["arguments"] += json.dumps(args)
            except (json.JSONDecodeError, ValueError):
                pass

        # Path 1 (preferred): native tool calls reassembled from deltas
        native_msg = {"tool_calls": [
            {"id": v.get("id", ""), "type": "function",
             "function": {"name": v["function"]["name"],
                          "arguments": v["function"]["arguments"]}}
            for v in native_accum.values()
            if v.get("function", {}).get("name")
        ]} if native_accum else {"tool_calls": []}
        native_calls = parse_openai_tool_calls(native_msg) if native_msg.get("tool_calls") else []

        if native_calls:
            import asyncio
            async def _exec_with_timeout(name, args, timeout=120):
                try:
                    return await asyncio.wait_for(
                        asyncio.to_thread(execute_tool, name, args),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    from .tools import ToolResult
                    return ToolResult(
                        tool_name=name, success=False, output=None,
                        duration_ms=timeout * 1000,
                        error=f"Tool execution timed out after {timeout}s",
                    )
            executed = []
            for c in native_calls[:max_tool_iterations]:
                r = await _exec_with_timeout(c["name"], c["arguments"])
                executed.append(r)
            # Tell clients to discard the pre-tool draft and render the
            # final answer fresh (avoids refusal-text + answer Frankenstein).
            yield format_sse_data({"restart": True}, event="restart")
            for c in native_calls[:len(executed)]:
                yield format_sse_data(
                    {"name": c["name"], "arguments": c["arguments"]},
                    event="tool_call",
                )
            for r in executed:
                yield format_sse_data(r.to_dict(), event="tool_result")
            tool_results_history.extend([r.to_dict() for r in executed])
            current_payload = dict(payload)
            current_payload["messages"] = list(payload.get("messages", []))
            current_payload["messages"].append({"role": "assistant", "content": full_response or None,
                                                 "tool_calls": native_msg["tool_calls"]})
            for c, r in zip(native_calls[:len(executed)], executed):
                current_payload["messages"].append({
                    "role": "tool", "tool_call_id": c.get("id", ""),
                    "content": json.dumps(r.to_dict(), ensure_ascii=False, default=str),
                })
            # P1-2: checkpoint every 3 iterations so interrupted runs can resume.
            if _conv_id and iteration % 3 == 0:
                try:
                    import asyncio as _asyncio
                    from . import memory as _mem
                    _asyncio.get_event_loop().run_until_complete  # ensure loop exists
                    cp_task = _asyncio.create_task(
                        _asyncio.to_thread(
                            _mem.save_checkpoint,
                            _conv_id,
                            iteration,
                            current_payload["messages"],
                            {"iteration": iteration, "tool_count": len(executed)},
                        )
                    )
                    logger.info(
                        "  [Checkpoint] scheduled save for %s step %d",
                        _conv_id[:8], iteration,
                    )
                except Exception as _cp_e:
                    logger.debug(f"  [Checkpoint] defer (running sync): {_cp_e}")

            _user_q = next(
                (m.get("content", "") for m in reversed(payload.get("messages", []))
                 if m.get("role") == "user"), ""
            )
            _user_msg = next(
                (m for m in reversed(current_payload["messages"])
                 if m.get("role") == "user"), None
            )
            if _user_msg:
                _user_msg["content"] = (
                    f"{_user_msg.get('content', '')}\n\n"
                    "=== CRITICAL INSTRUCTION ===\n"
                    "You MUST answer the user's question using the tool results above. "
                    "Do NOT copy the '[Tool Results]' header or raw output into your answer. "
                    "Synthesize a concise response FROM the data. This is your FINAL answer."
                )
            # Post-processing filter: if the model still copies tool results,
            # strip the [Tool Results] header from the final answer
            if full_response.strip().startswith("[Tool Results"):
                logger.warning("  [Post-filter] model copied tool results — stripping header")
                # Try to extract the actual answer after the tool results
                _parts = full_response.split("\n\n", 2)
                if len(_parts) > 2:
                    full_response = _parts[-1].strip()
                else:
                    full_response = "I have read the file. Here is a summary of its content."
            continue

        # Path 2 (fallback): legacy XML <tool_call> in text
        parsed = parse_tool_calls(full_response)
        if not parsed.has_tool_calls:
            # Path 3 (deterministic): explicit intent but model called
            # nothing. Single shared chain (tool_calling.decide_forced_calls)
            # so streaming and non-streaming behave identically.
            if iteration == 0:
                user_q = next(
                    (m.get("content", "") for m in reversed(current_payload.get("messages", []))
                     if m.get("role") == "user"), "",
                )
                forced_calls = decide_forced_calls(user_q)
                if forced_calls:
                    logger.info("  [Tools] deterministic fallback: %s",
                                [n for n, _ in forced_calls])
                    try:
                        from pathlib import Path as _P
                        _logf = _P(__file__).resolve().parent.parent / "requests.log"
                        with open(_logf, "a", encoding="utf-8") as _lf:
                            _lf.write(json.dumps(
                                {"forced": [n for n, _ in forced_calls],
                                 "user_q": user_q[:200]}, ensure_ascii=False) + "\n")
                    except Exception:
                        pass
                    import asyncio as _asyncio
                    async def _exec_forced_with_timeout(name, args, timeout=120):
                        try:
                            return await _asyncio.wait_for(
                                _asyncio.to_thread(execute_tool, name, args),
                                timeout=timeout,
                            )
                        except _asyncio.TimeoutError:
                            from .tools import ToolResult
                            return ToolResult(
                                tool_name=name, success=False, output=None,
                                duration_ms=timeout * 1000,
                                error=f"Tool execution timed out after {timeout}s",
                            )
                    executed_forced = []
                    for n, a in forced_calls:
                        r = await _exec_forced_with_timeout(n, a)
                        executed_forced.append(r)
                    try:
                        from pathlib import Path as _P2
                        _logf2 = _P2(__file__).resolve().parent.parent / "requests.log"
                        with open(_logf2, "a", encoding="utf-8") as _lf2:
                            _lf2.write(json.dumps(
                                {"forced_results": [
                                    {"tool": fr.tool_name, "success": fr.success,
                                     "err": (fr.error or "")[:150],
                                     "out_chars": len(str((fr.output or {}).get("content") or ""))}
                                    for fr in executed_forced]}, ensure_ascii=False) + "\n")
                    except Exception:
                        pass
                    yield format_sse_data({"restart": True}, event="restart")
                    for (n, a) in forced_calls:
                        yield format_sse_data({"name": n, "arguments": a}, event="tool_call")
                    for fr in executed_forced:
                        yield format_sse_data(fr.to_dict(), event="tool_result")
                    tool_results_history.extend([fr.to_dict() for fr in executed_forced])
                    current_payload = dict(payload)
                    current_payload["messages"] = list(payload.get("messages", []))
                    # Refusal quarantine (FIX 2026-09-26): if iter-1 text is a
                    # refusal, do NOT feed it back as assistant history — the
                    # model would defend it (consistency lock) and ignore the
                    # successful tool results. Neutral bridge instead.
                    _bridge = (neutral_bridge() if is_refusal_text(full_response)
                               else (full_response or None))
                    current_payload["messages"].append({"role": "assistant", "content": _bridge})
                    _fr_text = format_tool_results_for_followup(
                        executed_forced,
                        max_chars=30000 if any(n == "read_file" for n, _ in forced_calls) else 5000,
                    )
                    _fr_text += (
                        "\n\nREMINDER: now continue the task with tool calls "
                        "(write_file for EVERY file, then RUN it). "
                        "Do NOT output code as plain text without calling tools."
                        if any(n in ("track_goal", "run_shell") for n, _ in forced_calls) else "")
                    _fr_text += (
                        "\n\nREMINDER: enumerate EVERY tool BY NAME with its one-line "
                        "function, grouped by category. Never summarize categories "
                        "instead of listing tools."
                        if any(n == "my_capabilities" for n, _ in forced_calls) else "")
                    _fr_text += (
                        "\n\n=== SYSTEM INSTRUCTION ===\n"
                        "The tools above have been executed successfully. Their outputs are "
                        "REAL data you already hold. Now answer the user's original question "
                        "using ONLY the tool results. Do NOT copy the '[Tool Results]' header "
                        "or raw output text into your answer — synthesize a concise response "
                        "FROM the data."
                    )
                    current_payload["messages"].append({
                        "role": "user",
                        "content": _fr_text,
                    })
                    continue
            # Correction round (FIX 2026-09-26, user-observed): tools ran
            # SUCCESSFULLY but this iteration is still a refusal (the model
            # defending a prior stance). Do NOT accept it as final — restart
            # once with an explicit correction grounded in the results.
            # Bounded to one correction per stream (no loops).
            if (not _corrected_once and tool_results_history
                    and any(r.get("success") and r.get("output") for r in tool_results_history)
                    and is_refusal_text(full_response)):
                _corrected_once = True
                logger.info("  [Tools] refusal-despite-results → corrective re-stream")
                yield format_sse_data({"restart": True}, event="restart")
                # Keep ALL context (original + tool results); only append the
                # correction — rebuilding from payload would LOSE the results.
                current_payload["messages"] = list(current_payload.get("messages", []))
                current_payload["messages"].append({
                    "role": "user",
                    "content": (
                        "SYSTEM CORRECTION — READ CAREFULLY: the tools above RAN "
                        "SUCCESSFULLY and their outputs are REAL data you already "
                        "hold (file content, search results, clock time). You DO "
                        "have this access. Now DO the user's task using that data. "
                        "Restating inability to access is a FAILURE — answer from "
                        "the tool outputs."),
                })
                continue
            # Empty-answer guard (FIX 2026-09-26, Round 13): the served model
            # is a THINKING model and reasoning shares max_tokens. When the
            # budget is consumed before any visible answer exists, the user
            # sees NOTHING. Retry once with reasoning off and a bigger budget.
            if (EMPTY_RETRY and not _empty_retried and not full_response.strip()):
                _empty_retried = True
                logger.info("  [Budget] empty answer → reasoning-free re-stream")
                yield format_sse_data({"restart": True}, event="restart")
                current_payload = dict(payload)
                current_payload["messages"] = list(payload.get("messages", []))
                current_payload["max_tokens"] = max(
                    int(payload.get("max_tokens") or MIN_OUTPUT_TOKENS) * 2,
                    MIN_OUTPUT_TOKENS * 2,
                )
                current_payload["reasoning_effort"] = "none"
                continue

            break  # No tools to execute, done

        # Path 2 (fallback): legacy XML <tool_call> in text.
        # FIX 2026-09-26 (Round 14): this block sat at function level, i.e.
        # AFTER the `for` loop had already broken out — unreachable dead code.
        # XML tool calls were therefore parsed and silently dropped: no tool
        # ran, no follow-up was streamed, and the client was left with the
        # stripped XML draft (often empty) => "empty response from backend".
        text, results = execute_tool_calls(parsed)

        # Tell clients to discard the pre-tool draft and render fresh.
        yield format_sse_data({"restart": True}, event="restart")

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
            "content": (
                "The tools above have been executed successfully. Their outputs are "
                "REAL data you already hold. Now answer the user's original question "
                "using ONLY the tool results. Do NOT copy the '[Tool Results]' header "
                "or raw output text into your answer — synthesize a concise response "
                "FROM the data. Never call another tool; just answer."
            ),
        })
        continue

    # FIX 2026-09-27 (Round 19): if the tool loop exhausted max_tool_iterations
    # but the model never produced a final text answer, force one synthesis
    # call so the user gets a response grounded in the tool results.
    if tool_results_history and not full_response.strip():
        logger.info("  [Tools] loop exhausted without final answer → forced synthesis")
        yield format_sse_data({"restart": True}, event="restart")
        current_payload["messages"] = list(current_payload.get("messages", []))
        current_payload["messages"].append({
            "role": "user",
            "content": (
                "SYSTEM: The tools above RAN and their outputs are REAL data you "
                "already hold. DO NOT call any more tools. Answer the user's "
                "original question using ONLY the tool results above. Be concise "
                "and helpful."),
        })
        async for sse_chunk in stream_from_ollama(base_url, current_payload):
            yield sse_chunk
            try:
                data_line = None
                for line in sse_chunk.split("\n"):
                    if line.startswith("data: "):
                        data_line = line[6:].strip()
                        break
                if data_line and data_line != "[DONE]":
                    chunk_data = json.loads(data_line)
                    if "chunk" in chunk_data:
                        full_response += chunk_data["chunk"]
            except (json.JSONDecodeError, ValueError):
                pass

    # Single authoritative terminal pair (Round 14). Clients (both frontends)
    # stop reading on `event: done` / `data: [DONE]`, so they must appear ONCE
    # and LAST — after the final answer tokens.
    yield format_sse_data({"done": True}, event="done")
    yield format_sse_done()


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

    # Test 5: token estimate + budget trimming (Round 13)
    est = estimate_tokens("x" * 320)
    msgs = [{"role": "system", "content": "RULES"}] + [
        {"role": "user", "content": "y" * 4000} for _ in range(6)
    ]
    kept, dropped = fit_messages_to_budget(msgs, 2048, reserve=256)
    if 95 <= est <= 110 and dropped > 0 and kept[0]["role"] == "system" \
            and len(kept) < len(msgs):
        passed += 1
        print(f"  ✓ estimate_tokens + trim (dropped {dropped}, kept {len(kept)})")
    else:
        failed += 1
        print(f"  ✗ budget trim: est={est} dropped={dropped} kept={len(kept)}")

    # Test 6: generation policy floor + reasoning effort (Round 13)
    p1 = apply_generation_policy({"max_tokens": 10})
    p2 = apply_generation_policy({"max_tokens": 99999})
    if p1["max_tokens"] == MIN_OUTPUT_TOKENS and p2["max_tokens"] == 99999:
        passed += 1
        print("  ✓ apply_generation_policy floor")
    else:
        failed += 1
        print(f"  ✗ generation policy: {p1} {p2}")

    # Test 7: prompt budget report is self-consistent (Round 13)
    rep = prompt_budget_report()
    if rep["total_estimate_tokens"] > 0 and rep["served_context_tokens"] > 0:
        passed += 1
        print(f"  ✓ prompt_budget_report (est {rep['total_estimate_tokens']} / "
              f"ctx {rep['served_context_tokens']}, fits={rep['fits']})")
    else:
        failed += 1
        print(f"  ✗ prompt_budget_report: {rep}")

    # Test 8: SSE terminal contract (Round 14) — per-call [DONE] must NOT be
    # forwarded, and the tool-loop must emit exactly one terminal pair LAST.
    import asyncio
    import inspect as _insp

    sig = _insp.signature(stream_from_ollama)
    src = _insp.getsource(stream_with_tool_execution)
    loop_body = src.split("for iteration in range")[1]
    tail = loop_body.split("# Single authoritative terminal pair")[-1]
    ok_default = sig.parameters["emit_terminal"].default is False
    ok_once = tail.count("format_sse_done()") == 1 and "event=\"done\"" in tail
    # The XML tool-call path must live INSIDE the loop (was dead code).
    ok_xml = loop_body.count("execute_tool_calls(parsed)") == 1
    inner = _insp.getsource(stream_from_ollama)
    ok_guarded = inner.count("if emit_terminal:") == 2
    if ok_default and ok_once and ok_xml and ok_guarded:
        passed += 1
        print("  ✓ SSE terminal contract (1 terminal pair, per-call [DONE] suppressed)")
    else:
        failed += 1
        print(f"  ✗ terminal contract: default={ok_default} once={ok_once} "
              f"xml_in_loop={ok_xml} guarded={ok_guarded}")

    # Test 9: tool-loop end-to-end SSE order with a fake Ollama server (Round 14)
    async def _fake_run() -> Tuple[bool, str]:
        import json as _json
        from . import streaming as _self_mod

        calls: List[Dict[str, Any]] = []

        class _Resp:
            def __init__(self, lines: List[str]):
                self._lines = lines

            def raise_for_status(self) -> None:
                return None

            async def aiter_lines(self):
                for ln in self._lines:
                    yield ln

        class _StreamCtx:
            def __init__(self, lines):
                self._lines = lines

            async def __aenter__(self):
                return _Resp(self._lines)

            async def __aexit__(self, *a):
                return False

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def stream(self, method, url, json=None):
                calls.append(json or {})
                n = len(calls)
                if n == 1:
                    body = [
                        "data: " + _json.dumps({"choices": [{"delta": {
                            "content": "",
                            "tool_calls": [{"index": 0, "id": "c1", "type": "function",
                                            "function": {"name": "system_time",
                                                         "arguments": "{}"}}]},
                            "finish_reason": "tool_calls"}]}),
                        "data: [DONE]",
                    ]
                else:
                    body = [
                        "data: " + _json.dumps({"choices": [{"delta": {
                            "content": "الوقت الآن 12:00"}, "finish_reason": None}]}),
                        "data: " + _json.dumps({"choices": [{"delta": {},
                                                            "finish_reason": "stop"}]}),
                        "data: [DONE]",
                    ]
                return _StreamCtx(body)

        real_client = _self_mod.httpx.AsyncClient if hasattr(_self_mod, "httpx") else None
        import httpx as _h
        orig = _h.AsyncClient
        _h.AsyncClient = _Client  # type: ignore[assignment]
        out: List[str] = []
        try:
            async for sse in stream_with_tool_execution(
                "http://ollama.invalid", {"messages": [{"role": "user", "content": "كم الساعة؟"}]},
            ):
                out.append(sse)
        finally:
            _h.AsyncClient = orig  # type: ignore[assignment]
        text = "".join(out)
        # exactly one terminal pair, and it must be the LAST thing sent
        n_done_events = text.count("event: done")
        n_sentinels = text.count("data: [DONE]")
        last_is_sentinel = text.rstrip().endswith("data: [DONE]")
        has_answer = "الوقت الآن 12:00" in text
        # tool events must precede the answer tokens
        tool_idx = text.find("event: tool_result")
        ans_idx = text.find("الوقت الآن 12:00")
        order_ok = 0 <= tool_idx < ans_idx
        good = (n_done_events == 1 and n_sentinels == 1 and last_is_sentinel
                and has_answer and order_ok)
        return good, (f"done={n_done_events} sentinel={n_sentinels} last_ok={last_is_sentinel} "
                      f"answer={has_answer} order={order_ok} calls={len(calls)}")

    try:
        good, detail = asyncio.run(_fake_run())
        if good:
            passed += 1
            print(f"  ✓ tool-loop SSE order via fake Ollama ({detail})")
        else:
            failed += 1
            print(f"  ✗ tool-loop SSE order: {detail}")
    except Exception as exc:  # pragma: no cover
        failed += 1
        print(f"  ✗ tool-loop SSE order raised: {exc!r}")

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()
