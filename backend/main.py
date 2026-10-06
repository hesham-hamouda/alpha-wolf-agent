#!/usr/bin/env python3
r"""
Alpha Wolf Agent — FastAPI Backend
==================================
Bridges the body infrastructure (ChromaDB + NetworkX + SQLite + zvec)
with the inference engine (llama.cpp) and the frontend (Chainlit).

Endpoints (Phase 11+ v3.5):
- /v1/chat/completions     — OpenAI-compatible (proxy to llama.cpp)
- /v1/chat/stream          — Server-Sent Events streaming (Phase 11+ v3.3)
- /v1/recall               — semantic search across KBs
- /v1/memory/episode       — episodic memory CRUD
- /v1/memory/goal          — goal tracking CRUD
- /v1/memory/mistake       — mistake log CRUD
- /v1/memory/reflection    — reflection CRUD
- /v1/memory/episodes      — alias for memory/episode (Phase 11+ v3.5)
- /v1/tools                — tool registry
- /v1/tools/discover       — unified catalog (Phase 11+ v3.5)
- /v1/conversations        — conversation history CRUD (Phase 11+ v3.3)
- /v1/skills               — list installed skills (Phase 11+ v3.3)
- /v1/skills/install       — install skill (RESTful, Phase 11+ v3.5)
- /v1/skills/{name}/run    — run skill (RESTful, Phase 11+ v3.5)
- /v1/skills/text          — install from inline text (Phase 11+ v3.5)
- /v1/skills/registry      — registry with metadata (Phase 11+ v3.5)
- /v1/sessions             — session tracking (Phase 11+ v3.5)
- /v1/rope-config          — RoPE scaling proposal (FUTURE)
- /v1/vision/status        — Vision availability (PLACEHOLDER)
- /v1/graph/entity         — knowledge graph entity CRUD
- /v1/graph/relation       — knowledge graph relation CRUD
- /v1/body/health          — health check
- /v1/body/backup          — create backup snapshot
- /v1/self/summary         — Alpha Wolf self-summary

Iron Laws Applied:
- #8 (3-Expert Consensus) — design approved by 3-expert panel
- #15 (Verify) — /health endpoint returns structured dict
- #21 (NO Deletion) — soft delete via deleted_at
- #26 (Arabic comments where applicable)
- #33 (Lessons) — bilingual docstrings (Iron Law #47)
- #42 (Storage Discipline) — all paths in workspace, NOT body
- #48 (Separated Concerns) — SkillsManager split from skills.py
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path (works from any CWD)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file (Iron Law #42 — workspace config, not body)
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
        logger_early = logging.getLogger("alpha_wolf_early")
        logger_early.info(f"Loaded .env from {env_path}")
except ImportError:
    pass  # python-dotenv not installed; rely on OS env vars

from fastapi import FastAPI, HTTPException, Body, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from urllib.parse import urlparse


def _validate_url(url: str) -> None:
    """Validate URL to prevent SSRF attacks (FIX 2026-09-26 Round 17).

    التحقق من الرابط لمنع هجمات SSRF.

    Rejects:
    - Non-HTTP/HTTPS schemes
    - Private/internal IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x, 169.254.x)
    - localhost
    - Cloud metadata endpoints (169.254.169.254)
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(status_code=400, detail="URL must use http or https")
        hostname = parsed.hostname or ""
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
            raise HTTPException(status_code=400, detail="Access to localhost is not allowed")
        if hostname == "169.254.169.254":
            raise HTTPException(status_code=400, detail="Access to cloud metadata endpoint is not allowed")
        try:
            import ipaddress
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                raise HTTPException(status_code=400, detail="Access to private/internal networks is not allowed")
        except ValueError:
            pass  # Not an IP address, it's a domain name — allow it
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {e}")


# FIX 2026-10-06 (Phase 50.71 — Ollama 500 root cause):
# The original `alpha-wolf-agent` model manifest is BROKEN — Ollama returns
# `llama-server process has terminated: exit status 1` on every request,
# which surfaces to clients as HTTP 500. Any old frontend, MCP tester, or
# external script that still asks for the broken alias would silently
# crash. Rewrite those requests transparently to the working v8 rebuild.
_BROKEN_MODEL_ALIASES = frozenset({
    "alpha-wolf-agent",
    "alpha-wolf-agent:latest",
    "alpha-wolf-agent:default",
})
_WORKING_MODEL = os.environ.get("LLAMACPP_MODEL", "alpha-wolf-agent-v8")


def _resolve_served_model(req_model: str) -> str:
    """Swap the broken model alias for the working v8 rebuild.

    إعادة توجيه alias المكسور إلى v8 العامل (شفاف للعميل).
    """
    if req_model in _BROKEN_MODEL_ALIASES:
        logger.warning(
            "  [Model] client requested BROKEN %r — rewriting to working %r",
            req_model, _WORKING_MODEL,
        )
        return _WORKING_MODEL
    return req_model


# FIX 2026-10-06 (Phase 50.71 — Ollama 500 transient recovery):
# Ollama occasionally returns HTTP 500 mid-stream when the served model
# process gets into a bad state (manifest mismatch after update, VRAM
# pressure, etc). The error is usually transient and the NEXT call works.
# Retry with exponential backoff so the user sees a response, not a 500.
import asyncio as _asyncio


async def _call_ollama_with_retry(
    client: "httpx.AsyncClient",
    url: str,
    payload: dict[str, Any],
    *,
    max_retries: int = 3,
    is_stream: bool = False,
) -> Optional[dict[str, Any]]:
    """POST to Ollama with retry on 500.

    استدعاء Ollama مع إعادة المحاولة عند 500 (exponential backoff).

    Returns parsed JSON for non-stream calls. For stream calls, returns None
    (the caller streams directly and handles errors inline). Raises the last
    error if all retries are exhausted on non-stream.
    """
    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        t0 = time.time()
        try:
            if is_stream:
                # Streaming: caller handles the response, we just retry the
                # POST itself. Returning a flag signals "retry me".
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return None  # success: caller continues with resp
                if resp.status_code == 500:
                    elapsed = (time.time() - t0) * 1000
                    logger.warning(
                        "  [Retry] Ollama 500 on stream (attempt %d/%d, %.0fms) — model=%s, "
                        "msgs=%d, max_tokens=%d",
                        attempt + 1, max_retries, elapsed,
                        payload.get("model"), len(payload.get("messages", [])),
                        payload.get("max_tokens"),
                    )
                    if attempt < max_retries - 1:
                        await _asyncio.sleep(2 ** attempt)
                        continue
                    raise last_error or Exception("Ollama 500 stream after retries")
                # Other HTTP errors → raise (not retried)
                resp.raise_for_status()
                return None
            else:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 500:
                    elapsed = (time.time() - t0) * 1000
                    logger.warning(
                        "  [Retry] Ollama 500 (attempt %d/%d, %.0fms) — model=%s, "
                        "msgs=%d, max_tokens=%d",
                        attempt + 1, max_retries, elapsed,
                        payload.get("model"), len(payload.get("messages", [])),
                        payload.get("max_tokens"),
                    )
                    if attempt < max_retries - 1:
                        await _asyncio.sleep(2 ** attempt)
                        continue
                    last_error = Exception(f"Ollama 500 after {max_retries} retries")
                    break
                # 4xx: don't retry, surface the error
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            last_error = e
            elapsed = (time.time() - t0) * 1000
            logger.warning(
                "  [Retry] HTTP error (attempt %d/%d, %.0fms): %s",
                attempt + 1, max_retries, elapsed, e,
            )
            if attempt < max_retries - 1:
                await _asyncio.sleep(2 ** attempt)
                continue
            raise
    if last_error:
        raise last_error
    return None


from contextlib import asynccontextmanager

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from body.alpha_wolf_body import AlphaWolfBody

# Agent capabilities (Phase 11+ v3.3)
from backend.agent import tools as agent_tools
from backend.agent import tool_calling
from backend.agent import streaming
from backend.agent import memory as agent_memory
from backend.agent import skills as agent_skills
from backend.agent import skills_manager as agent_skills_manager
from backend.agent import mcp_server as agent_mcp

# Phase 11+ v3.4 capabilities (GraphRAG + Code Sandbox + Live RAG)
from backend.agent import live_context  # LIVE project folder awareness
from backend.agent import code_exec       # Sandboxed Python execution
from backend.agent import rag             # Ollama embeddings + ChromaDB

# Phase 11+ v3.5 — future work placeholders (RoPE scaling, Vision)
from backend.agent import rope_config  # Context window expansion (FUTURE)
from backend.agent import vision        # Vision module (PLACEHOLDER)

# ============================================================================
# Configuration
# ============================================================================

LLAMACPP_BASE_URL = os.environ.get("LLAMACPP_BASE_URL", "http://localhost:8080")
FASTAPI_HOST = os.environ.get("FASTAPI_HOST", "127.0.0.1")
FASTAPI_PORT = int(os.environ.get("FASTAPI_PORT", "8001"))

logger = logging.getLogger("alpha_wolf_backend")

# FIX 2026-09-26 (Phase 36 — mojibake fix):
# Force UTF-8 stdout/stderr to prevent mojibake on Arabic log output.
# Without this, Windows console (cp1252) mangles Arabic chars into garbage.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ============================================================================
# FastAPI App
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler (replaces deprecated @app.on_event).

    معالج دورة الحياة — يهيئ الجسم والمهارات عند البدء ويغلق عند الإيقاف.
    """
    global body
    body = AlphaWolfBody()
    logger.info("✓ Alpha Wolf Body initialized")

    # Auto-load skills (Iron Law #15 — verify on startup)
    mgr = _get_skills_manager()
    load_result = mgr.auto_load()
    logger.info("✓ Skills auto-load: %d registered", load_result["registered"])
    # Reload RAG job ledger (stale running jobs -> interrupted, honestly)
    _load_rag_jobs()
    yield
    if body:
        body.close()
    logger.info("✓ Alpha Wolf Body closed")


app = FastAPI(
    title="Alpha Wolf Agent Backend",
    version="0.1.0",
    description="Bridges body infrastructure (ChromaDB+NetworkX+SQLite+zvec) + llama.cpp inference",
    lifespan=lifespan,
)

# CORS — restricted to localhost (FIX 2026-09-26 Round 15: was allow_origins=["*"]
# with allow_credentials=True, which is a browser security violation and allows
# any website to make authenticated requests to this backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",   # Streamlit frontend
        "http://localhost:8000",   # Chainlit frontend
        "http://127.0.0.1:8501",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy body initialization (deferred to lifespan)
body: Optional[AlphaWolfBody] = None

# Lazy skills manager (separated concerns per Iron Law #48)
_skills_mgr: Optional[agent_skills_manager.SkillsManager] = None


def _get_skills_manager() -> agent_skills_manager.SkillsManager:
    """Lazy-init the SkillsManager (singleton)."""
    global _skills_mgr
    if _skills_mgr is None:
        _skills_mgr = agent_skills_manager.SkillsManager()
        _skills_mgr.auto_load()
    return _skills_mgr


# ============================================================================
# Pydantic Models
# ============================================================================

class ChatMessage(BaseModel):
    role: str = Field(..., description="system|user|assistant")
    content: str


class ChatRequest(BaseModel):
    model: str = "alpha-wolf-agent-v8"
    messages: list[ChatMessage]
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1, le=131072)
    stream: bool = False
    use_body_recall: bool = True
    top_k: int = Field(5, ge=1, le=20)
    inject_tools: bool = True
    use_native_tools: bool = True
    execute_tools: bool = False
    use_live_context: bool = True
    use_rag: bool = True


class RecallRequest(BaseModel):
    query: str
    kb_filter: Optional[str] = None
    top_k: int = 5


class EpisodeRequest(BaseModel):
    content: str
    trigger_type: str = "user_task"
    importance: int = 5
    session_id: Optional[str] = None
    summary: Optional[str] = None


class GoalRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: int = 5
    deadline: Optional[str] = None
    parent_id: Optional[str] = None


class MistakeRequest(BaseModel):
    context: str
    what_went_wrong: str
    lesson: str
    root_cause: Optional[str] = None
    prevention: Optional[str] = None
    severity: int = 5


class ReflectionRequest(BaseModel):
    trigger: str
    insight: str
    confidence: float = 0.5
    episode_id: Optional[str] = None


class ToolRequest(BaseModel):
    name: str
    invocation: str
    description: Optional[str] = None
    category: Optional[str] = None


class EntityRequest(BaseModel):
    node_type: str
    name: str
    attributes: Optional[dict] = None


class RelationRequest(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    attributes: Optional[dict] = None


class CreateConversationRequest(BaseModel):
    title: Optional[str] = None
    metadata: Optional[dict] = None


class AddMessageRequest(BaseModel):
    role: str
    content: str
    metadata: Optional[dict] = None
    importance: int = 5


class InstallSkillRequest(BaseModel):
    source: str  # URL or local file path
    target_name: Optional[str] = None
    skill_type: str = "file"  # 'file' or 'url'


class RunSkillRequest(BaseModel):
    skill_name: str
    arguments: Optional[dict] = None


# ============================================================================
# Chat Endpoint (OpenAI-compatible proxy to llama.cpp)
# ============================================================================

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    """OpenAI-compatible chat endpoint with optional body recall."""
    if not HAS_HTTPX:
        raise HTTPException(status_code=503, detail="httpx not installed")

    # Inject body context if requested
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # FIX 2026-09-26 (Round 15): unify system prompts — non-streaming now uses
    # the SAME _build_streaming_system_prompt() as the streaming path, so the
    # agent behaves identically regardless of which endpoint is called.
    from backend.agent.streaming import _build_streaming_system_prompt
    wolf_system = _build_streaming_system_prompt()
    if not any("HARD TOOL RULES" in (m["content"] or "")
               for m in messages if m["role"] == "system"):
        messages.insert(0, {"role": "system", "content": wolf_system})

    # Inject tool definitions if requested (Phase 11+ v3.3)
    # FIX 2026-10-04 (Phase 41 — RC1): avoid duplicating tools as both system
    # text AND payload["tools"]. When use_native_tools=True, payload["tools"]
    # is the authoritative structured form (smaller + Ollama-native), so we
    # skip the text injection to save ~13K chars / ~4.5K tokens and keep the
    # total request under num_ctx=16384.
    if req.inject_tools and not req.use_native_tools:
        # Only inject tools-as-text when native tools are NOT being sent
        # (avoids duplication; native format is smaller + structured)
        tool_system = {
            "role": "system",
            "content": agent_tools.format_tools_for_prompt(),
        }
        messages.insert(0, tool_system)
        logger.info("  [Tools] injected %d tool definitions (text format)",
                    len(agent_tools.TOOL_SPECS))
    elif req.inject_tools and req.use_native_tools:
        logger.info("  [Tools] using native format only (skipping text format to avoid duplication)")

    if req.use_body_recall and body:
        # Recall relevant context from body
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if last_user:
            import asyncio
            results = await asyncio.to_thread(body.recall, last_user, top_k=req.top_k)
            if results:
                context_str = "\n\n".join(
                    f"[{r['metadata'].get('source_agent', 'unknown')}] {r['content'][:300]}"
                    for r in results
                )
                # Inject as system message
                messages.insert(0, {
                    "role": "system",
                    "content": f"Relevant knowledge from your body:\n\n{context_str}",
                })
                logger.info(f"  [Recall] injected {len(results)} results for: {last_user[:50]}")

    # Phase 11+ v3.4 — GraphRAG Live Context Awareness
    if req.use_live_context:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if last_user:
            try:
                import asyncio
                lc = await asyncio.to_thread(live_context.get_live_context)
                ctx = await asyncio.to_thread(lc.build_system_context, query=last_user, max_depth=2, search_top_k=3)
                messages.insert(0, {"role": "system", "content": ctx})
                logger.info(f"  [LiveContext] injected {len(ctx)} chars for query: {last_user[:50]}")
            except Exception as e:
                logger.warning(f"  [LiveContext] failed: {e}")

    # Phase 11+ v3.4 — Live RAG (Ollama embeddings + ChromaDB)
    if req.use_rag:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if last_user:
            try:
                import asyncio
                rag_ctx = await asyncio.to_thread(rag.build_rag_context, last_user, top_k=min(req.top_k, 3))
                if rag_ctx:
                    messages.insert(0, {"role": "system", "content": rag_ctx})
                    logger.info(f"  [RAG] injected {len(rag_ctx)} chars for query: {last_user[:50]}")
            except Exception as e:
                logger.warning(f"  [RAG] failed: {e}")

    # FIX 2026-09-26 (Phase 36 — Arabic overflow guard):
    # Log total system-injected chars so we can detect when context exceeds budget.
    # Arabic text ≈ 14× heavier than English per char; 12000 chars ≈ 4500 Arabic tokens.
    # FIX 2026-10-04 (Phase 41 — RC5): add a 35K hard-warning threshold so any
    # future regression on num_ctx or prompt growth trips a loud log line
    # instead of a silent 400 from Ollama.
    total_injected = sum(
        len(m.get("content", "") or "")
        for m in messages
        if m.get("role") == "system"
    )
    if total_injected > 35000:
        logger.warning(
            f"  [Budget] system prompt too large: {total_injected} chars (target: <30000) — request at risk"
        )
    elif total_injected > 12000:
        logger.warning(f"  [Budget] total system injection = {total_injected} chars (high)")
    else:
        logger.info(f"  [Budget] total system injection = {total_injected} chars")

    # Proxy to llama.cpp / Ollama (OpenAI-compatible)
    # FIX 2026-10-06: rewrite broken model alias to working v8 (defensive).
    served_model = _resolve_served_model(req.model)
    payload: dict[str, Any] = {
        "model": served_model,
        "messages": messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "stream": req.stream,
    }

    # Prompt budget + output budget (FIX 2026-09-26, Round 13): the served
    # context used to be 4096 while this prompt is ~7.9k tokens, so Ollama
    # silently truncated it away and the model stopped obeying + stopped
    # calling tools. Trim history to the REAL context, never the rules.
    try:
        from backend.agent.streaming import (
            apply_generation_policy, fit_messages_to_budget, served_context_tokens,
        )
        payload["messages"], _ = fit_messages_to_budget(
            messages, served_context_tokens(LLAMACPP_BASE_URL))
        payload = apply_generation_policy(payload)
    except Exception as e:
        logger.warning(f"  [Budget] policy skipped: {e}")

    # Native function-calling (reliable path — FIX 2026-09-25).
    # Previously only XML <tool_call> text was injected, which the model
    # ignored. Now we ALSO send OpenAI tools[] so Ollama returns
    # message.tool_calls natively.
    if req.use_native_tools:
        try:
            payload["tools"] = agent_tools.to_openai_tools()
            payload["tool_choice"] = "auto"
        except Exception as e:
            logger.warning(f"  [Tools] native tools build failed: {e}")

    # If tool execution is requested and response contains tool_calls, execute them
    if req.execute_tools:
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                # First call (non-streaming) to get full response
                resp = await client.post(
                    f"{LLAMACPP_BASE_URL}/v1/chat/completions",
                    json={**payload, "stream": False},
                )
                resp.raise_for_status()
                response_data = resp.json()

            # Extract assistant message
            assistant_msg = response_data.get("choices", [{}])[0].get("message", {})
            full_content = assistant_msg.get("content", "") or ""

            # Path 1 (preferred): native OpenAI tool_calls
            native_calls = agent_tools.parse_openai_tool_calls(assistant_msg)
            tool_results: list[dict[str, Any]] = []

            if native_calls:
                logger.info("  [Tools] executing %d native tool calls", len(native_calls))
                executed: list[Any] = []
                for call in native_calls[:3]:
                    result = agent_tools.execute_tool(call["name"], call["arguments"])
                    executed.append(result)
                tool_results = [r.to_dict() for r in executed]

                # Append tool results and get final answer.
                # Use OpenAI tool role messages when the backend supports them,
                # with a plain user fallback (llama.cpp ignores unknown roles safely).
                followup_messages = list(messages)
                followup_messages.append({
                    "role": "assistant",
                    "content": full_content or None,
                    "tool_calls": assistant_msg.get("tool_calls"),
                })
                for call, res in zip(native_calls[:3], executed):
                    followup_messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps(res.to_dict(), ensure_ascii=False, default=str),
                    })
                # Fallback summary for servers that drop tool-role messages
                followup_messages.append({
                    "role": "user",
                    "content": tool_calling.format_tool_results_for_followup(executed),
                })

                async with httpx.AsyncClient(timeout=300) as client:
                    resp2 = await client.post(
                        f"{LLAMACPP_BASE_URL}/v1/chat/completions",
                        json={"model": _resolve_served_model(req.model), "messages": followup_messages, "temperature": req.temperature},
                    )
                    resp2.raise_for_status()
                    final_data = resp2.json()

                # Merge tool calls into response
                final_data["tool_calls_executed"] = tool_results
                return final_data

            # Path 2 (fallback): legacy XML <tool_call> blocks
            parsed = tool_calling.parse_tool_calls(full_content)

            if parsed.has_tool_calls:
                logger.info("  [Tools] executing %d XML tool calls", len(parsed.tool_calls))
                text, results = tool_calling.execute_tool_calls(parsed, max_iterations=3)
                tool_results = [r.to_dict() for r in results]

                # Append tool results and get final answer
                messages.append({"role": "assistant", "content": full_content})
                messages.append({
                    "role": "user",
                    "content": tool_calling.format_tool_results_for_followup(results),
                })

                async with httpx.AsyncClient(timeout=300) as client:
                    resp2 = await client.post(
                        f"{LLAMACPP_BASE_URL}/v1/chat/completions",
                        json={"model": _resolve_served_model(req.model), "messages": messages, "temperature": req.temperature},
                    )
                    resp2.raise_for_status()
                    final_data = resp2.json()

                # Merge tool calls into response
                final_data["tool_calls_executed"] = tool_results
                return final_data

            # Path 3 (deterministic): explicit intent but no tool calls.
            # Single shared chain (tool_calling.decide_forced_calls).
            #
            # FIX 2026-10-04 (Round 31): decide_forced_calls returns a FLAT list
            # of (tool_name, args) tuples — e.g. [("system_time", {}),
            # ("web_search", {...})]. Previous code wrongly tried to unpack
            # each tuple as if it were a list of pairs, causing
            # "too many values to unpack (expected 2)" ValueError.
            _last_q = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            _forced_list = tool_calling.decide_forced_calls(_last_q)
            # _forced_list is flat: each element is (name, args).
            # Execute all forced calls as ONE batch (no need for inner loop).
            if _forced_list:
                logger.info("  [Tools] deterministic fallback (non-stream): %s",
                            [n for n, _ in _forced_list])
                _res_list = [agent_tools.execute_tool(n, a) for n, a in _forced_list]
                # Refusal quarantine: never feed a refusal back as history.
                _bridge_ns = (tool_calling.neutral_bridge()
                              if tool_calling.is_refusal_text(full_content)
                              else (full_content or None))
                messages.append({"role": "assistant", "content": _bridge_ns})
                _forced_names = [n for n, _ in _forced_list]
                _follow = tool_calling.format_tool_results_for_followup(
                    _res_list,
                    max_chars=30000 if "read_file" in _forced_names else 5000,
                )
                if any(n in ("track_goal", "run_shell") for n in _forced_names):
                    _follow += ("\n\nREMINDER: now continue the task with tool calls "
                                "(write_file for EVERY file, then RUN it). "
                                "Do NOT output code as plain text without calling tools.")
                if "my_capabilities" in _forced_names:
                    _follow += ("\n\nREMINDER: enumerate EVERY tool BY NAME with its one-line "
                                "function, grouped by category. Never summarize categories "
                                "instead of listing tools.")
                messages.append({"role": "user", "content": _follow})
                async with httpx.AsyncClient(timeout=300) as client:
                    _resp = await client.post(
                        f"{LLAMACPP_BASE_URL}/v1/chat/completions",
                        json={"model": _resolve_served_model(req.model), "messages": messages, "temperature": req.temperature},
                    )
                    _resp.raise_for_status()
                    _final = _resp.json()
                _final["tool_calls_executed"] = [r.to_dict() for r in _res_list]
                # Correction round: tools succeeded but answer is still refusal.
                try:
                    _ans = ((_final.get("choices") or [{}])[0].get("message", {}).get("content") or "")
                    if (any(_r.success and _r.output for _r in _res_list)
                            and tool_calling.is_refusal_text(_ans)):
                        logger.info("  [Tools] refusal-despite-results → corrective call (non-stream)")
                        messages.append({"role": "assistant",
                                         "content": _final["choices"][0]["message"].get("content")})
                        messages.append({"role": "user",
                                         "content": ("SYSTEM CORRECTION: the tools above RAN "
                                                     "SUCCESSFULLY — answer from their outputs. "
                                                     "Restating inability is a FAILURE.")})
                        async with httpx.AsyncClient(timeout=300) as client:
                            _resp2 = await client.post(
                                f"{LLAMACPP_BASE_URL}/v1/chat/completions",
                                json={"model": req.model, "messages": messages,
                                      "temperature": req.temperature},
                            )
                            _resp2.raise_for_status()
                            _final = _resp2.json()
                        _final["tool_calls_executed"] = [r.to_dict() for r in _res_list]
                        _final["corrected_refusal"] = True
                except Exception as _ce:
                    logger.warning(f"  [Tools] correction round failed: {_ce}")
                # Post-filter: model copied tool results verbatim
                try:
                    _ans = ((_final.get("choices") or [{}])[0].get("message", {}).get("content") or "")
                    if _ans.strip().startswith("[Tool Results") or _ans.strip().startswith("✓") or _ans.strip().startswith("✗"):
                        logger.info("  [Post-filter] model copied tool results (non-stream) → retry")
                        messages.append({"role": "assistant", "content": _ans})
                        messages.append({"role": "user", "content": (
                            "=== CRITICAL INSTRUCTION ===\n"
                            "You MUST answer the user's question using the tool results above. "
                            "Do NOT copy the '[Tool Results]' header or raw output into your answer. "
                            "Synthesize a concise response FROM the data. This is your FINAL answer."
                        )})
                    async with httpx.AsyncClient(timeout=300) as client:
                        _resp3 = await client.post(
                            f"{LLAMACPP_BASE_URL}/v1/chat/completions",
                            json={"model": _resolve_served_model(req.model), "messages": messages,
                                  "temperature": req.temperature},
                        )
                        _resp3.raise_for_status()
                        _final = _resp3.json()
                except Exception as _pe:
                    logger.warning(f"  [Post-filter] failed: {_pe}")
                return _final

            return response_data
        except httpx.HTTPError as e:
            logger.error(f"  [Chat] llama.cpp error: {e}")
            # FIX 2026-09-26 (Phase 38): instead of raising HTTPException(502)
            # which crashes the client for long tasks, return a structured
            # error response (200 with status: "backend_unavailable") so the
            # agent can surface it to the user and retry.
            return {
                "id": "chat-error",
                "object": "chat.completion",
                "created": int(__import__("time").time()),
                "model": req.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            f"[Backend error: llama.cpp unreachable — {type(e).__name__}: {e}. "
                            f"The inference server at {LLAMACPP_BASE_URL} may be down. "
                            f"Please verify Ollama/llama-server is running and retry.]"
                        ),
                    },
                    "finish_reason": "error",
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "status": "backend_unavailable",
                "error": f"{type(e).__name__}: {e}",
                "code": 502,
            }
        except Exception as e:
            logger.error(f"  [Chat] unexpected error: {type(e).__name__}: {e}")
            return {
                "id": "chat-error",
                "object": "chat.completion",
                "created": int(__import__("time").time()),
                "model": req.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            f"[Backend error: {type(e).__name__}: {e}. "
                            f"The chat endpoint hit an unexpected error. "
                            f"Please retry or check backend logs.]"
                        ),
                    },
                    "finish_reason": "error",
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "status": "endpoint_error",
                "error": f"{type(e).__name__}: {e}",
                "code": 500,
            }

    # Standard proxy (no tool execution)
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{LLAMACPP_BASE_URL}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"  [Chat] llama.cpp error: {e}")
        return {
            "id": "chat-error",
            "object": "chat.completion",
            "created": int(__import__("time").time()),
            "model": req.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        f"[Backend error: llama.cpp unreachable — {type(e).__name__}: {e}. "
                        f"The inference server at {LLAMACPP_BASE_URL} may be down. "
                        f"Please verify Ollama/llama-server is running and retry.]"
                    ),
                },
                "finish_reason": "error",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "status": "backend_unavailable",
            "error": f"{type(e).__name__}: {e}",
            "code": 502,
        }
    except Exception as e:
        logger.error(f"  [Chat] unexpected error: {type(e).__name__}: {e}")
        return {
            "id": "chat-error",
            "object": "chat.completion",
            "created": int(__import__("time").time()),
            "model": req.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        f"[Backend error: {type(e).__name__}: {e}. "
                        f"The chat endpoint hit an unexpected error. "
                        f"Please retry or check backend logs.]"
                    ),
                },
                "finish_reason": "error",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "status": "endpoint_error",
            "error": f"{type(e).__name__}: {e}",
            "code": 500,
        }


# ============================================================================
# Streaming Chat Endpoint (Phase 11+ v3.3)
# ============================================================================

class StreamChatRequest(BaseModel):
    """Streaming chat request with optional conversation_id."""
    model: str = "alpha-wolf-agent-v8"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    conversation_id: Optional[str] = None  # For persistent history
    auto_tools: bool = True  # Auto-execute tool calls (Phase 11+ v3.3)
    max_tool_iterations: int = 3
    use_native_tools: bool = True  # Send OpenAI tools[] (FIX 2026-09-25)
    use_body_recall: bool = True  # Inject body memory context (FIX 2026-09-26: was missing in stream path)
    use_live_context: bool = True  # Inject LIVE project folder awareness (FIX 2026-09-26)
    use_rag: bool = True  # Inject RAG context from Ollama embeddings (FIX 2026-09-26)
    top_k: int = 5


@app.post("/v1/chat/stream")
async def chat_stream(req: StreamChatRequest):
    """Server-Sent Events streaming endpoint.

    نقطة نهاية البث المباشر باستخدام SSE.

    Returns text/event-stream with chunks:
        event: token
        data: {"chunk": "...", "done": false}

        event: tool_call
        data: {"name": "...", "arguments": {...}}

        event: tool_result
        data: {"success": true, "output": {...}}

        data: [DONE]
    """
    if not HAS_HTTPX:
        raise HTTPException(status_code=503, detail="httpx not installed")

    try:
        # Request trace (tracker mission: see EXACTLY what each client sent).
        _dbg_last = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
        with open(PROJECT_ROOT / "backend" / "requests.log", "a", encoding="utf-8") as _lf:
            _lf.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                  "model": req.model, "n_msgs": len(req.messages),
                                  "conv": (req.conversation_id or "")[:8],
                                  "last_user": _dbg_last[:300]}, ensure_ascii=False) + "\n")
    except Exception:
        pass

    try:
        messages = [{"role": m.role, "content": m.content} for m in req.messages]
        if req.conversation_id:
            history = agent_memory.get_conversation(req.conversation_id, include_system=False)
            if history:
                history_msgs = [{"role": m["role"], "content": m["content"]} for m in history]
                messages = history_msgs + messages

        # FIX 2026-10-06: rewrite broken model alias to working v8 (defensive).
        served_model = _resolve_served_model(req.model)
        payload: dict[str, Any] = {
            "model": served_model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }

        _last_user_stream = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if _last_user_stream:
            if req.use_body_recall and body:
                try:
                    results = body.recall(_last_user_stream, top_k=req.top_k)
                    if results:
                        context_str = "\n\n".join(
                            f"[{r['metadata'].get('source_agent', 'unknown')}] {r['content'][:300]}"
                            for r in results
                        )
                        messages.insert(0, {
                            "role": "system",
                            "content": f"Relevant knowledge from your body:\n\n{context_str}",
                        })
                        logger.info("  [Recall/stream] injected %d results", len(results))
                except Exception as e:
                    logger.warning(f"  [Recall/stream] failed: {e}")
            if req.use_live_context:
                try:
                    lc = live_context.get_live_context()
                    ctx = lc.build_system_context(query=_last_user_stream, max_depth=2, search_top_k=3)
                    messages.insert(0, {"role": "system", "content": ctx})
                    logger.info("  [LiveContext/stream] injected %d chars", len(ctx))
                except Exception as e:
                    logger.warning(f"  [LiveContext/stream] failed: {e}")
            if req.use_rag:
                try:
                    rag_ctx = rag.build_rag_context(_last_user_stream, top_k=min(req.top_k, 3))
                    if rag_ctx:
                        messages.insert(0, {"role": "system", "content": rag_ctx})
                        logger.info("  [RAG/stream] injected %d chars", len(rag_ctx))
                except Exception as e:
                    logger.warning(f"  [RAG/stream] failed: {e}")
            payload["messages"] = messages

        if req.auto_tools and req.use_native_tools:
            try:
                payload["tools"] = agent_tools.to_openai_tools()
                payload["tool_choice"] = "auto"
            except Exception as e:
                logger.warning(f"  [Tools] native streaming tools failed: {e}")

        # P1-2 + P1-5: inject conversation_id into payload so the streaming
        # loop can save checkpoints (P1-2) and persist stream chunks (P1-5).
        if req.conversation_id:
            payload["_conv_id"] = req.conversation_id

        if req.auto_tools:
            async def _save_chunks_and_return():
                # P1-5: wrap the streaming generator to persist each chunk
                # to disk so reconnecting clients can resume (Iron Law #22).
                chunk_id = 0
                async for sse_chunk in streaming.stream_with_tool_execution(
                    LLAMACPP_BASE_URL,
                    payload,
                    max_tool_iterations=req.max_tool_iterations,
                ):
                    chunk_id += 1
                    streaming._save_stream_chunk(req.conversation_id, chunk_id, sse_chunk)
                    yield sse_chunk
                # Done — clear the chunk file (best-effort).
                streaming._clear_stream_chunks(req.conversation_id)

            return StreamingResponse(
                _save_chunks_and_return(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # P1-5: persist chunks even in the simple (non-tool) path so
            # reconnecting clients can resume.
            async def _save_chunks_simple():
                chunk_id = 0
                async for sse_chunk in streaming.stream_from_ollama(
                    LLAMACPP_BASE_URL, payload, emit_terminal=True
                ):
                    chunk_id += 1
                    streaming._save_stream_chunk(req.conversation_id, chunk_id, sse_chunk)
                    yield sse_chunk
                streaming._clear_stream_chunks(req.conversation_id)

            return StreamingResponse(
                _save_chunks_simple(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
    except Exception as e:
        logger.error("chat_stream failed: %s", e)
        async def _error_stream():
            yield f"event: error\ndata: {json.dumps({'error': str(e), 'type': 'endpoint_error'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            _error_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


# ============================================================================
# Tools Registry Endpoints (Phase 11+ v3.3)
# ============================================================================

@app.get("/v1/tools")
async def list_agent_tools(category: Optional[str] = None):
    """List all available agent tools.

    عرض جميع الأدوات المتاحة للوكيل.

    Args:
        category: Optional filter by category (filesystem, compute, network)
    """
    tool_list = agent_tools.list_tools()
    if category:
        tool_list = [t for t in tool_list if t.get("category") == category]
    return {
        "tools": tool_list,
        "count": len(tool_list),
        "categories": list(set(t.get("category") for t in tool_list)),
    }


@app.post("/v1/tools/execute")
async def execute_agent_tool_endpoint(
    name: str = Body(..., embed=True),
    arguments: dict = Body(default_factory=dict, embed=True),
):
    """Execute an agent tool directly (bypass model).

    تنفيذ أداة وكيل مباشرة (بدون النموذج).

    Useful for testing or scripted use. Runs in a worker thread so slow
    tools (vision 300s, shell 300s, index_project) never stall the loop
    (FIX 2026-09-26: full backend wedge root cause).
    """
    import asyncio as _aio
    result = await _aio.to_thread(agent_tools.execute_tool, name, arguments)
    return result.to_dict()


@app.get("/v1/tools/categories")
async def list_tool_categories():
    """List available tool categories."""
    tools_list = agent_tools.list_tools()
    categories = {}
    for t in tools_list:
        cat = t.get("category", "general")
        categories[cat] = categories.get(cat, 0) + 1
    return categories


# ============================================================================
# Checkpoint Endpoints — P1-2 (Round 25, 2026-09-29)
# ============================================================================

class CheckpointRequest(BaseModel):
    """Body for POST /v1/conversations/{conv_id}/checkpoint."""
    step: int = 0
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


@app.post("/v1/conversations/{conv_id}/checkpoint")
async def save_checkpoint_endpoint(conv_id: str, req: CheckpointRequest):
    """Save a checkpoint snapshot for resumable long-running tasks.

    حفظ snapshot لـ checkpoint للمهام الطويلة القابلة للاستئناف.
    """
    import asyncio as _aio
    cp_id = await _aio.to_thread(
        agent_memory.save_checkpoint,
        conv_id,
        req.step,
        req.messages,
        req.metadata,
    )
    if not cp_id:
        raise HTTPException(status_code=500, detail="Checkpoint save failed")
    return {"checkpoint_id": cp_id, "conversation_id": conv_id, "step": req.step}


@app.get("/v1/conversations/{conv_id}/checkpoint")
async def get_checkpoint_endpoint(conv_id: str):
    """Get the latest checkpoint for a conversation.

    جلب آخر checkpoint لمحادثة.
    """
    import asyncio as _aio
    cp = await _aio.to_thread(agent_memory.load_latest_checkpoint, conv_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"No checkpoint for: {conv_id}")
    return cp


@app.get("/v1/conversations/{conv_id}/checkpoints")
async def list_checkpoints_endpoint(conv_id: str):
    """List all checkpoints for a conversation (debug).

    عرض جميع الـ checkpoints لمحادثة (تشخيص).
    """
    import asyncio as _aio
    return await _aio.to_thread(agent_memory.list_checkpoints, conv_id)


@app.delete("/v1/conversations/{conv_id}/checkpoints")
async def delete_checkpoints_endpoint(conv_id: str):
    """Delete all checkpoints for a conversation.

    حذف كل الـ checkpoints لمحادثة. Iron Law #21: explicit user request.
    """
    import asyncio as _aio
    n = await _aio.to_thread(agent_memory.delete_checkpoints, conv_id)
    return {"deleted": n, "conversation_id": conv_id}


# ============================================================================
# Cache Endpoints — P1-4 (Round 25, 2026-09-29)
# ============================================================================

@app.get("/v1/cache/stats")
async def cache_stats_endpoint():
    """Return tool result cache stats.

    إحصائيات ذاكرة التخزين المؤقت لنتائج الأدوات.
    """
    return agent_tools.get_cache_stats()


@app.post("/v1/cache/clear")
async def clear_cache_endpoint():
    """Clear all tool result cache entries.

    مسح جميع إدخالات ذاكرة التخزين المؤقت.
    """
    n = agent_tools.clear_tool_cache()
    return {"cleared": n}


# ============================================================================
# Stream Resumability Endpoints — P1-5 (Round 25, 2026-09-29)
# ============================================================================

@app.get("/v1/chat/stream/resume/{conv_id}")
async def resume_stream_endpoint(conv_id: str, from_chunk: int = 0):
    """Resume a previously interrupted stream from a given chunk id.

    استئناف stream متوقف من chunk id محدد.
    """
    import asyncio as _aio
    chunks = await _aio.to_thread(streaming._load_stream_chunks, conv_id, from_chunk)

    async def _event_gen():
        for cid, data in chunks:
            yield f"id: {cid}\ndata: {data}\n\n"
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(_event_gen(), media_type="text/event-stream")


# ============================================================================
# Conversation History Endpoints (Phase 11+ v3.3)
# ============================================================================

@app.post("/v1/conversations")
async def create_conversation_endpoint(req: CreateConversationRequest):
    """Create a new conversation session.

    إنشاء جلسة محادثة جديدة.
    """
    conv_id = agent_memory.create_conversation(
        title=req.title,
        metadata=req.metadata,
    )
    return {
        "conversation_id": conv_id,
        "title": req.title or "New conversation | محادثة جديدة",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/v1/conversations")
async def list_conversations_endpoint(limit: int = 50, include_deleted: bool = False):
    """List all conversations."""
    convs = agent_memory.list_conversations(limit=limit, include_deleted=include_deleted)
    return {
        "conversations": convs,
        "count": len(convs),
        "total_active": agent_memory.get_conversation_count(),
    }


@app.get("/v1/conversations/{conversation_id}")
async def get_conversation_endpoint(conversation_id: str, limit: int = 100, include_system: bool = True):
    """Get all messages in a conversation."""
    if not agent_memory.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}")
    summary = agent_memory.get_conversation_summary(conversation_id)
    messages = agent_memory.get_conversation(conversation_id, limit=limit, include_system=include_system)
    return {
        **summary,
        "messages": messages,
        "message_count": len(messages),
    }


@app.post("/v1/conversations/{conversation_id}/messages")
async def add_message_endpoint(conversation_id: str, req: AddMessageRequest):
    """Add a message to a conversation."""
    try:
        msg_id = agent_memory.add_message(
            conversation_id=conversation_id,
            role=req.role,
            content=req.content,
            metadata=req.metadata,
            importance=req.importance,
        )
        return {"message_id": msg_id, "status": "added"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/v1/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str, hard: bool = False):
    """Delete (soft by default) a conversation."""
    ok = agent_memory.delete_conversation(conversation_id, hard=hard)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}")
    return {
        "conversation_id": conversation_id,
        "deleted": True,
        "hard": hard,
        "note": "Soft delete preserves history (Iron Law #21)" if not hard else "Hard delete (permanent)",
    }


# ============================================================================
# Skills Endpoints (Phase 11+ v3.3)
# ============================================================================

@app.get("/v1/skills")
async def list_skills_endpoint():
    """List all installed skills."""
    skills_list = agent_skills.list_skills()
    return {
        "skills": [s.to_dict() for s in skills_list],
        "count": len(skills_list),
    }


@app.post("/v1/install_skill", deprecated=True)
async def install_skill_endpoint(req: InstallSkillRequest):
    """Install a skill from a URL or local file.

    تثبيت مهارة من رابط أو ملف محلي.

    Args:
        source: URL (http://...) or local file path
        target_name: Optional name for the skill
        skill_type: 'url' or 'file'

    DEPRECATED: use /v1/skills/text or /v1/skills/install instead (Phase 11+ v3.5).
    """
    logger.warning("DEPRECATED endpoint /v1/install_skill called. Use /v1/skills/text or /v1/skills/install instead.")
    try:
        if req.skill_type == "url" or req.source.startswith(("http://", "https://")):
            _validate_url(req.source)
            result = agent_skills.install_skill_from_url(req.source, req.target_name)
        else:
            result = agent_skills.install_skill_from_file(req.source, req.target_name)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Install failed: {e}")


@app.post("/v1/run_skill", deprecated=True)
async def run_skill_endpoint(req: RunSkillRequest):
    """Execute an installed skill.

    DEPRECATED: use /v1/skills/{skill_name}/run instead (Phase 11+ v3.5).
    """
    logger.warning("DEPRECATED endpoint /v1/run_skill called. Use /v1/skills/{skill_name}/run instead.")
    args = req.arguments or {}
    result = agent_skills.run_skill(req.skill_name, **args)
    return result


@app.delete("/v1/skills/{skill_name}")
async def uninstall_skill_endpoint(skill_name: str):
    """Uninstall a skill."""
    try:
        return agent_skills.uninstall_skill(skill_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"uninstall skill error: {e}")


# ============================================================================
# Skills System v2 (Phase 11+ v3.5) — RESTful endpoints
# ============================================================================

@app.post("/v1/skills/install")
async def install_skill_v2(req: InstallSkillRequest):
    """Install a skill (file path or URL).

    تثبيت مهارة (مسار ملف أو URL).
    Alias for /v1/install_skill with RESTful URL.
    """
    try:
        mgr = _get_skills_manager()
        if req.skill_type == "url" or req.source.startswith(("http://", "https://")):
            _validate_url(req.source)
            return mgr.install_from_url(req.source, req.target_name)
        return mgr.install_from_file(req.source, req.target_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"install skill error: {e}")


@app.post("/v1/skills/{skill_name}/run")
async def run_skill_v2(
    skill_name: str,
    arguments: Optional[dict] = Body(default=None, embed=True),
):
    """Run a skill by name.

    تشغيل مهارة بالاسم.
    Alias for /v1/run_skill with RESTful URL.
    """
    try:
        mgr = _get_skills_manager()
        return mgr.run(skill_name, arguments or {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"run skill error: {e}")


@app.post("/v1/skills/text")
async def install_skill_from_text(
    name: str = Body(...),
    source: str = Body(...),
):
    """Install a skill from inline Python text (Iron Law #33 self-improvement).

    تثبيت مهارة من نص بايثون مباشر (التحسين الذاتي).
    """
    try:
        mgr = _get_skills_manager()
        result = mgr.install_from_text(name, source)
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"install skill from text error: {e}")


@app.get("/v1/skills/registry")
async def skills_registry_endpoint():
    """List all installed skills from the persistent registry.

    قائمة بجميع المهارات المثبتة من السجل الدائم.
    """
    mgr = _get_skills_manager()
    skills_list = mgr.list_all()
    return {
        "skills": skills_list,
        "count": len(skills_list),
        "registry_db": "conversations.db (skills_registry table)",
    }


# ============================================================================
# Tools Discovery (Phase 11+ v3.5)
# ============================================================================

@app.get("/v1/tools/discover")
async def tools_discover_endpoint():
    """Unified tool catalog: built-in tools + skill-discoverable tools.

    كتالوج موحد للأدوات: المدمجة + القابلة للاكتشاف من المهارات.

    Returns a merged catalog with categories, descriptions, and discoverability.
    """
    # 1. Built-in tools (from tools.py)
    builtin = agent_tools.list_tools()

    # 2. Skills (each skill with run() can be a callable tool)
    mgr = _get_skills_manager()
    skill_records = mgr.list_all()
    skill_tools = [
        {
            "name": f"skill:{s['name']}",
            "description": s.get("description", ""),
            "description_ar": s.get("description_ar", ""),
            "version": s.get("version", "0.0.0"),
            "author": s.get("author", ""),
            "parameters": s.get("parameters", {}),
            "category": "skill",
            "discoverable": True,
            "invoke_via": f"POST /v1/skills/{s['name']}/run",
            "path": s.get("path", ""),
            "install_source": s.get("install_source", "unknown"),
        }
        for s in skill_records
    ]

    # 3. MCP tools (lazily loaded)
    mcp_server = _get_mcp_server()
    mcp_tools = [
        {
            "name": f"mcp:{t.name}",
            "description": t.description,
            "category": "mcp",
            "discoverable": True,
            "input_schema": t.input_schema,
        }
        for t in mcp_server.tools.values()
    ]

    unified = builtin + skill_tools + mcp_tools

    return {
        "unified_catalog": unified,
        "counts": {
            "builtin_tools": len(builtin),
            "skills": len(skill_tools),
            "mcp_tools": len(mcp_tools),
            "total": len(unified),
        },
        "categories": list(set(t.get("category", "general") for t in unified)),
        "note": (
            "Tools marked 'discoverable: True' can be invoked via the model "
            "when injected into the system prompt. Built-in tools execute "
            "directly; skills execute via POST /v1/skills/{name}/run."
        ),
    }


# ============================================================================
# Sessions (Phase 11+ v3.5)
# ============================================================================

@app.post("/v1/sessions")
async def upsert_session_endpoint(
    session_id: str = Body(...),
    user_id: Optional[str] = Body(None),
    metadata: Optional[dict] = Body(None),
):
    """Create or update a session record (Iron Law #36 persistence).

    إنشاء أو تحديث سجل جلسة.
    """
    return agent_skills_manager.upsert_session(session_id, user_id, metadata)


@app.get("/v1/sessions")
async def list_sessions_endpoint(limit: int = 100):
    """List all sessions (most recent first)."""
    return {
        "sessions": agent_skills_manager.list_sessions(limit=limit),
        "count": len(agent_skills_manager.list_sessions(limit=limit)),
    }


# ============================================================================
# Memory Episodes (Phase 11+ v3.5) — Wrapper over body KB
# ============================================================================

@app.get("/v1/memory/episodes")
async def memory_episodes_endpoint(min_importance: int = 1, limit: int = 20):
    """List episodes from body KB (episodic memory).

    قائمة الحلقات من قاعدة معرفة الجسم (الذاكرة العرضية).
    Alias for /v1/memory/episode with more RESTful name.
    """
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    return body.recall_episodes(min_importance=min_importance, limit=limit)


# ============================================================================
# RoPE Scaling Config (Phase 11+ v3.5) — FUTURE WORK
# ============================================================================

@app.get("/v1/rope-config")
async def rope_config_endpoint(target_context: int = 524288):
    """Get RoPE scaling configuration proposal (FUTURE — not enabled).

    الحصول على اقتراح توسيع السياق (مستقبل — غير مفعّل).

    Returns:
        Dict with current state, strategies, recommendation, and steps to enable.
    """
    return rope_config.config_proposal(target_context=target_context)


# ============================================================================
# Vision (Phase 11+ v3.5) — PLACEHOLDER
# ============================================================================

@app.get("/v1/vision/status")
async def vision_status_endpoint():
    """Check if vision is currently available.

    التحقق من توفر الرؤية حالياً.
    """
    return {
        "available": vision.is_available(),
        "recommended_model": vision.DEFAULT_VISION_MODEL,
        "fallback_model": vision.FALLBACK_VISION_MODEL,
        "ollama_url": vision.OLLAMA_BASE_URL,
        "local_vision_models": vision.list_local_vision_models(),
        "note": "Vision is a placeholder — see /v1/vision/test to verify interface.",
    }


@app.post("/v1/vision/test")
async def vision_test_endpoint(image_path: str = Body(..., embed=True)):
    """Test vision describe_image endpoint (returns placeholder).

    اختبار نقطة نهاية الرؤية (يُرجع placeholder).
    """
    return vision.describe_image(image_path)


# ============================================================================
# MCP Server Endpoint (Phase 11+ v3.3)
# ============================================================================

_mcp_server_instance = None


def _get_mcp_server():
    """Lazy initialization of MCP server."""
    global _mcp_server_instance
    if _mcp_server_instance is None:
        _mcp_server_instance = agent_mcp.create_alpha_wolf_mcp_server()
    return _mcp_server_instance


@app.get("/v1/mcp/tools")
async def mcp_list_tools():
    """List tools available via MCP protocol."""
    server = _get_mcp_server()
    return {
        "tools": [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in server.tools.values()
        ],
        "count": len(server.tools),
    }


@app.post("/v1/mcp/rpc")
async def mcp_rpc_endpoint(req: Request):
    """MCP JSON-RPC 2.0 endpoint."""
    import json as json_lib
    body = await req.json()
    request = agent_mcp.JSONRPCRequest(
        method=body.get("method", ""),
        params=body.get("params"),
        id=body.get("id"),
    )
    response = await _get_mcp_server().handle_request(request)
    return response.to_dict()


# ============================================================================
# Body CRUD Endpoints
# ============================================================================

@app.post("/v1/recall", deprecated=True)
async def recall(req: RecallRequest):
    """Semantic recall across KBs.

    DEPRECATED: use /v1/memory/recall or /v1/embeddings/search instead (Phase 11+ v3.5+).
    """
    logger.warning("DEPRECATED endpoint /v1/recall called. Use /v1/memory/recall or /v1/embeddings/search instead.")
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    results = body.recall(req.query, kb_filter=req.kb_filter, top_k=req.top_k)
    return {"query": req.query, "results": results, "count": len(results)}


@app.post("/v1/memory/episode")
async def create_episode(req: EpisodeRequest):
    """Store an episode in episodic memory."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    eid = body.remember_episode(
        content=req.content,
        trigger_type=req.trigger_type,
        importance=req.importance,
        session_id=req.session_id,
        summary=req.summary,
    )
    return {"id": eid, "status": "stored"}


@app.get("/v1/memory/episode")
async def list_episodes(min_importance: int = 1, limit: int = 20):
    """List episodes."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    return body.recall_episodes(min_importance=min_importance, limit=limit)


@app.post("/v1/memory/goal")
async def create_goal(req: GoalRequest):
    """Track a goal."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    gid = body.track_goal(
        title=req.title,
        description=req.description,
        priority=req.priority,
        deadline=req.deadline,
        parent_id=req.parent_id,
    )
    return {"id": gid, "status": "tracked"}


@app.patch("/v1/memory/goal/{goal_id}")
async def update_goal(goal_id: str, status: str, progress_pct: Optional[float] = None):
    """Update goal status."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    ok = body.update_goal_status(goal_id, status, progress_pct)
    return {"id": goal_id, "status": status, "ok": ok}


@app.get("/v1/memory/goal")
async def list_goals(status: Optional[str] = "open", limit: int = 20):
    """List goals."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    return body.recall_goals(status=status, limit=limit)


@app.get("/v1/goals", deprecated=True)
async def goals_alias(status: Optional[str] = "open", limit: int = 20):
    """Legacy alias for /v1/memory/goal (backward compat).

    DEPRECATED: use /v1/memory/goal instead.
    """
    logger.warning("DEPRECATED endpoint /v1/goals called. Use /v1/memory/goal instead.")
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    return body.recall_goals(status=status, limit=limit)


@app.post("/v1/memory/mistake")
async def log_mistake(req: MistakeRequest):
    """Log a mistake."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    mid = body.log_mistake(
        context=req.context,
        what_went_wrong=req.what_went_wrong,
        lesson=req.lesson,
        root_cause=req.root_cause,
        prevention=req.prevention,
        severity=req.severity,
    )
    return {"id": mid, "status": "logged"}


@app.get("/v1/memory/mistake")
async def list_mistakes(severity_min: int = 1, limit: int = 20):
    """List mistakes."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    return body.recall_mistakes(severity_min=severity_min, limit=limit)


@app.post("/v1/memory/reflection")
async def create_reflection(req: ReflectionRequest):
    """Record a reflection."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    rid = body.reflect(
        trigger=req.trigger,
        insight=req.insight,
        confidence=req.confidence,
        episode_id=req.episode_id,
    )
    return {"id": rid, "status": "reflected"}


@app.post("/v1/tools")
async def register_tool(req: ToolRequest):
    """Register a tool in body memory (legacy path, kept for compat).

    Use POST /v1/body/tools for new code. GET /v1/tools is the agent
    tool registry (no conflict: different method, but kept explicit here).
    """
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    tid = body.register_tool(
        name=req.name,
        invocation=req.invocation,
        description=req.description,
        category=req.category,
    )
    return {"id": tid, "status": "registered"}


@app.post("/v1/body/tools")
async def register_body_tool(req: ToolRequest):
    """Register a tool in body memory (canonical path — FIX 2026-09-25)."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    tid = body.register_tool(
        name=req.name,
        invocation=req.invocation,
        description=req.description,
        category=req.category,
    )
    return {"id": tid, "status": "registered"}


@app.get("/v1/body/tools")
async def list_body_tools(category: Optional[str] = None):
    """List registered body-memory tools (canonical path — FIX 2026-09-25).

    Previously this was GET /v1/tools which collided with the agent tool
    registry above (duplicate route — second definition unreachable).
    """
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    return body.list_tools(category=category)


@app.post("/v1/graph/entity")
async def add_entity(req: EntityRequest):
    """Add entity to knowledge graph."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    eid = body.add_entity(req.node_type, req.name, req.attributes)
    return {"id": eid, "status": "added"}


@app.post("/v1/graph/relation")
async def add_relation(req: RelationRequest):
    """Add relation to knowledge graph."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    rid = body.add_relation(
        source_id=req.source_id,
        target_id=req.target_id,
        edge_type=req.edge_type,
        weight=req.weight,
        attributes=req.attributes,
    )
    return {"id": rid, "status": "added"}


# ============================================================================
# Live Context Endpoints (Phase 11+ v3.4 — GraphRAG Live Awareness)
# ============================================================================

class LiveContextQueryRequest(BaseModel):
    """Request for live context query (search project files)."""
    query: str
    file_patterns: Optional[list[str]] = None
    max_results: int = 10


class LiveContextRequest(BaseModel):
    """Request for live context summary."""
    max_depth: int = 3
    recent_days: int = 7


@app.post("/v1/live-context/summary")
async def live_context_summary(req: LiveContextRequest):
    """Return a structured summary of the project folder (fresh from disk).

    يُرجع ملخص هيكلي لمجلد المشروع (طازج من القرص).
    """
    try:
        lc = live_context.get_live_context()
        summary = lc.get_project_summary(max_depth=req.max_depth, recent_days=req.recent_days)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"live_context error: {e}")


@app.post("/v1/live-context/search")
async def live_context_search(req: LiveContextQueryRequest):
    """Search the project folder for files containing text (graph traversal).

    البحث في مجلد المشروع عن ملفات تحتوي على نص.
    """
    try:
        lc = live_context.get_live_context()
        results = lc.search_in_files(
            query=req.query,
            file_patterns=req.file_patterns,
            max_results=req.max_results,
        )
        return {
            "query": req.query,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"live_context search error: {e}")


@app.post("/v1/live-context/inject")
async def live_context_inject(query: str = Body(..., embed=True), max_depth: int = Body(2, embed=True), top_k: int = Body(3, embed=True)):
    """Build a system prompt injection with live context for a query.

    بناء حقن سياق نظامي للاستعلام.

    Useful for testing or external integrations.
    """
    try:
        lc = live_context.get_live_context()
        ctx = lc.build_system_context(query=query, max_depth=max_depth, search_top_k=top_k)
        return {
            "query": query,
            "context_chars": len(ctx),
            "context": ctx,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"live_context inject error: {e}")


# ============================================================================
# Code Execution Sandbox Endpoints (Phase 11+ v3.4)
# ============================================================================

class CodeExecRequest(BaseModel):
    """Request for code execution."""
    code: str
    timeout_sec: int = 30


class CodeSafetyCheckRequest(BaseModel):
    """Request for code safety check (no execution)."""
    code: str


@app.post("/v1/code-exec/execute")
async def execute_code(req: CodeExecRequest):
    """Execute Python code in a sandboxed subprocess.

    تنفيذ كود بايثون في بيئة معزولة.

    Safety: AST pre-check + restricted env + 30s timeout (max).
    """
    try:
        import asyncio
        result = await asyncio.to_thread(code_exec.execute_python, req.code, req.timeout_sec)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"code_exec error: {e}")


@app.post("/v1/code-exec/safety-check")
async def code_safety_check(req: CodeSafetyCheckRequest):
    """Run AST safety check on code WITHOUT executing.

    فحص سلامة AST بدون تنفيذ.
    """
    try:
        result = code_exec.safety_check(req.code)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"code_exec safety_check error: {e}")


# ============================================================================
# Live RAG Endpoints (Phase 11+ v3.4 — Ollama Embeddings + ChromaDB)
# ============================================================================

class RAGQueryRequest(BaseModel):
    """RAG query."""
    query: str
    top_k: int = 3


class RAGIndexRequest(BaseModel):
    """RAG index request."""
    patterns: Optional[list[str]] = None
    force: bool = False
    background: bool = False  # True = return immediately, watch via GET /v1/rag/job/{id}


# In-memory RAG job tracker with JSON persistence (survives restarts).
# FIX 2026-09-26 (tracker round 1): jobs were lost on backend restart and the
# UI showed 404 for a job that was actually indexing. On load, any job left
# "running"/"queued" is marked "interrupted" (honest: its process is gone;
# the ChromaDB index itself persists, so re-queueing is incremental, not waste).
_RAG_JOBS_FILE = PROJECT_ROOT / "backend" / "rag_jobs.json"
_rag_jobs: dict[str, dict[str, Any]] = {}
_rag_jobs_lock = threading.Lock()


def _save_rag_jobs() -> None:
    try:
        _RAG_JOBS_FILE.write_text(json.dumps(_rag_jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        logger.warning("rag jobs persist failed: %s", e)


def _load_rag_jobs() -> None:
    global _rag_jobs
    with _rag_jobs_lock:
        try:
            if _RAG_JOBS_FILE.exists():
                _rag_jobs = json.loads(_RAG_JOBS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("rag jobs load failed: %s", e)
            _rag_jobs = {}
        changed = False
        for job in _rag_jobs.values():
            if job.get("status") in ("queued", "running"):
                job["status"] = "interrupted"
                job["note"] = "Backend restarted while this job was active; re-queue to resume (indexing is incremental)."
                job["finished_at"] = datetime.now(timezone.utc).isoformat()
                changed = True
        if changed:
            _save_rag_jobs()


def _run_rag_index_job_sync(job_id: str, patterns: Optional[list[str]], force: bool) -> None:
    """Sync RAG indexing worker (runs inside a thread — never on the loop)."""
    with _rag_jobs_lock:
        job = _rag_jobs.get(job_id, {})
        job.update({"status": "running", "started_at": datetime.now(timezone.utc).isoformat()})
        _save_rag_jobs()
    try:
        from backend.agent import rag as _rag_mod
        r = _rag_mod.get_rag()
        stats = r.index_directory(patterns=patterns, force=force)
        with _rag_jobs_lock:
            job.update({"status": "done", "indexed": stats,
                        "total_chunks": r._total_chunks(),
                        "finished_at": datetime.now(timezone.utc).isoformat()})
            _save_rag_jobs()
    except Exception as e:
        logger.error("RAG background job %s failed: %s", job_id, e)
        with _rag_jobs_lock:
            job.update({"status": "failed", "error": f"{type(e).__name__}: {e}",
                        "finished_at": datetime.now(timezone.utc).isoformat()})
            _save_rag_jobs()


async def _run_rag_index_job(job_id: str, patterns: Optional[list[str]], force: bool) -> None:
    """Background worker for RAG indexing (threaded — keeps loop responsive).

    FIX 2026-09-26 (user-observed full wedge): the sync embedding loop ran
    INSIDE the event loop and starved every request for minutes. Now it runs
    in a worker thread via asyncio.to_thread.
    """
    import asyncio as _aio
    await _aio.to_thread(_run_rag_index_job_sync, job_id, patterns, force)


@app.post("/v1/rag/query")
async def rag_query(req: RAGQueryRequest):
    """Query the RAG store for similar chunks (Ollama + ChromaDB).

    البحث في متجر RAG عن قطع مشابهة.
    """
    try:
        import asyncio
        r = await asyncio.to_thread(rag.get_rag)
        result = await asyncio.to_thread(r.query, req.query, top_k=req.top_k)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag query error: {e}")


@app.post("/v1/rag/index")
async def rag_index(req: RAGIndexRequest, background_tasks: BackgroundTasks):
    """Index the project folder into RAG (slow — use background=true).

    فهرسة مجلد المشروع في RAG.
    Sync mode returns stats directly; background mode returns a job id
    immediately (GET /v1/rag/job/{job_id} to watch progress).
    """
    if req.background:
        job_id = uuid.uuid4().hex[:12]
        with _rag_jobs_lock:
            _rag_jobs[job_id] = {"job_id": job_id, "status": "queued",
                                 "created_at": datetime.now(timezone.utc).isoformat()}
            _save_rag_jobs()
        background_tasks.add_task(_run_rag_index_job, job_id, req.patterns, req.force)
        return {"job_id": job_id, "status": "queued",
                "watch": f"/v1/rag/job/{job_id}"}
    try:
        import asyncio
        r = await asyncio.to_thread(rag.get_rag)
        stats = await asyncio.to_thread(r.index_directory, patterns=req.patterns, force=req.force)
        return {
            "indexed": stats,
            "total_chunks": r._total_chunks(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag index error: {e}")


@app.get("/v1/rag/job/{job_id}")
async def rag_job_status(job_id: str):
    """Status of a background RAG indexing job.

    حالة مهمة فهرسة RAG في الخلفية.
    """
    with _rag_jobs_lock:
        job = _rag_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    return job


@app.get("/v1/rag/stats")
async def rag_stats():
    """RAG store stats."""
    try:
        import asyncio
        r = await asyncio.to_thread(rag.get_rag)
        return await asyncio.to_thread(r.stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag stats error: {e}")


# ============================================================================
# Web Search Engine Endpoints (dedicated engine: backend/agent/web_search.py)
# ============================================================================

class WebSearchRequest(BaseModel):
    """Web search request (delegates to the Wolf's search engine)."""
    query: str
    max_results: int = 5
    lang: str = "auto"  # ar|en|auto


class WebFetchRequest(BaseModel):
    """Fetch a page as readable text (retrieval/جلب step)."""
    url: str
    max_chars: int = 8000


@app.post("/v1/web/search")
async def web_search_endpoint(req: WebSearchRequest):
    """Search the web (multi-provider engine + TTL cache).

    البحث على الويب (محرك متعدد الموفرين + كاش).
    Same engine as the `web_search` tool — direct HTTP access for UI/scripts.
    """
    try:
        import asyncio
        from backend.agent import web_search as engine
        return await asyncio.to_thread(engine.search, req.query, max_results=req.max_results, lang=req.lang)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"web search error: {e}")


@app.post("/v1/web/fetch")
async def web_fetch_endpoint(req: WebFetchRequest):
    """Fetch a URL and extract readable text.

    جلب رابط واستخراج نصه المقروء.
    Same engine as the `fetch_page` tool.
    """
    try:
        _validate_url(req.url)
        import asyncio
        from backend.agent import web_search as engine
        return await asyncio.to_thread(engine.fetch_page, req.url, max_chars=req.max_chars)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"web fetch error: {e}")


@app.get("/v1/body/health")
async def body_health():
    """Health check (Iron Law #15)."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    return body.health_check()


@app.post("/v1/body/backup")
async def body_backup():
    """Create backup snapshot (Iron Law #14)."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    import asyncio
    try:
        def _do_backup() -> str:
            # FIX 2026-09-26 (Phase 38): create a NEW body instance in this
            # thread so SQLite (created in the lifespan thread) does not raise
            # "objects created in a thread can only be used in that same thread".
            from body.alpha_wolf_body import AlphaWolfBody
            local = AlphaWolfBody()
            try:
                return local.backup()
            finally:
                local.close()
        backup_path = await asyncio.to_thread(_do_backup)
        return {"backup_path": backup_path, "status": "created"}
    except Exception as e:
        # FIX 2026-09-26 (Phase 38): never let backup failures 500 the whole
        # endpoint — return a structured error with partial state instead so
        # the user (and any automated agent) knows exactly what failed and
        # can retry with a single-disk scope later.
        logger.error("body_backup failed: %s: %s", type(e).__name__, e)
        return {
            "status": "failed",
            "error": f"{type(e).__name__}: {e}",
            "suggestion": "Try again, or back up specific layers (graph, sqlite, chromadb) separately.",
            "body_initialized": True,
        }


@app.get("/v1/self/summary")
async def self_summary():
    """Alpha Wolf self-summary (Wolf Trait: Self-Aware)."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    import asyncio
    def _do_summary() -> dict:
        # FIX 2026-09-26 (Phase 38): same threading fix as body_backup —
        # create a fresh body in the worker thread so SQLite is valid.
        from body.alpha_wolf_body import AlphaWolfBody
        local = AlphaWolfBody()
        try:
            return local.get_self_summary()
        finally:
            local.close()
    try:
        return await asyncio.to_thread(_do_summary)
    except Exception as e:
        logger.error("self_summary failed: %s: %s", type(e).__name__, e)
        return {
            "status": "failed",
            "error": f"{type(e).__name__}: {e}",
            "name": "Alpha Wolf Agent",
            "note": "Body initialized but summary query failed; see backend logs.",
        }


# ============================================================================
# Self-Model + Weakness Scan + Body Inspection (Wolf self-awareness)
# ============================================================================

@app.get("/v1/self/model")
async def self_model_endpoint():
    """Machine-readable self-model: who the Wolf is and what it can do.

    نموذج ذاتي مقروء آلياً: من هو الذئب وماذا يستطيع.
    Lets the agent understand itself: identity, tools, skills, memory,
    inference backend, and where to look for weaknesses (/v1/self/gaps).
    """
    tools_list = agent_tools.list_tools()
    try:
        skills_list = _get_skills_manager().list_all()
    except Exception:
        skills_list = []
    health = None
    if body:
        try:
            health = body.health_check()
        except Exception as e:
            health = {"ok": False, "error": str(e)}
    brain: dict[str, Any] = {}
    budget: dict[str, Any] = {}
    try:
        from backend.agent.capabilities import brain_facts
        brain = brain_facts()
    except Exception as e:
        brain = {"error": str(e)[:200]}
    try:
        from backend.agent.streaming import prompt_budget_report
        budget = prompt_budget_report()
    except Exception as e:
        budget = {"error": str(e)[:200]}
    return {
        "name": "Alpha Wolf Agent",
        "traits": ["mistake_hunter", "goal_persistence", "tenacity", "deep_thinking",
                   "resourceful", "self_aware", "reinforcement_learning"],
        "capabilities": {
            "tools": {"count": len(tools_list),
                      "names": [t.get("name") for t in tools_list],
                      "categories": sorted(set(t.get("category", "general") for t in tools_list))},
            "skills": {"count": len(skills_list),
                       "names": [s.get("name") for s in skills_list]},
            "self_extension": ["install_skill", "run_skill"],
            "web": ["web_search", "fetch_page", "/v1/web/search", "/v1/web/fetch"],
            "memory": bool(body),
        },
        "inference": {"base_url": LLAMACPP_BASE_URL, "model": os.environ.get("LLAMACPP_MODEL", "alpha-wolf-agent-v8")},
        "brain": brain,
        "prompt_budget": budget,
        "body_health": health,
        "weakness_scan": "/v1/self/gaps",
        "body_browser": "/v1/body/browse",
    }


@app.get("/v1/self/gaps")
async def self_gaps_endpoint():
    """Scan the Wolf's own body for weaknesses (honest, machine-readable).

    فحص جسد الذئب لاكتشاف نقاط الضعف (بصدق، مقروء آلياً).
    Each gap: id, severity (critical|warning|info), area, detail, suggestion.
    """
    import asyncio
    gaps: list[dict[str, Any]] = []

    def add(gid: str, severity: str, area: str, detail: str, suggestion: str) -> None:
        gaps.append({"id": gid, "severity": severity, "area": area,
                     "detail": detail, "suggestion": suggestion})

    # --- RAG coverage ---
    try:
        r = await asyncio.to_thread(rag.get_rag)
        stats = await asyncio.to_thread(r.stats)
        chunks = int(stats.get("total_chunks", 0) or 0)
        if chunks == 0:
            add("rag-empty", "critical", "memory",
                "RAG index is empty — the agent cannot recall project knowledge.",
                "POST /v1/rag/index with background=true, then watch /v1/rag/job/{id}.")
        else:
            from pathlib import Path as _P
            root = _P(r.project_root) if getattr(r, "project_root", None) else PROJECT_ROOT
            candidates = sum(1 for pat in ("*.md", "*.py", "*.txt", "*.json", "*.toml")
                             for p in root.rglob(pat) if p.is_file()
                             and not any(x in p.parts for x in
                                         ("node_modules", ".git", "__pycache__", ".venv", "venv",
                                          "backups", "dist", "build", ".cache")))
            if chunks < candidates:
                add("rag-underindexed", "warning", "memory",
                    f"RAG has {chunks} chunks for ~{candidates} files — some knowledge is invisible.",
                    "POST /v1/rag/index (incremental: only new/changed chunks embed).")
        if not stats.get("ollama_healthy"):
            add("ollama-embeddings-down", "critical", "memory",
                "Ollama embeddings unreachable — RAG queries and indexing cannot work.",
                "Start Ollama and pull nomic-embed-text.")
    except Exception as e:
        add("rag-unavailable", "critical", "memory",
            f"RAG subsystem error: {type(e).__name__}: {e}", "Check backend logs.")

    # --- Self-knowledge: is the project log indexed? ---
    try:
        r = await asyncio.to_thread(rag.get_rag)
        indexed = False
        try:
            if getattr(r, "collection", None) is not None:
                got = r.collection.get(where={"source": "PROJECT_LOG.md"}, limit=1)
                indexed = bool(got and got.get("ids"))
        except Exception:
            indexed = False
        if not indexed:
            q = await asyncio.to_thread(r.query, "project log training phases identity", top_k=3)
            d = q.to_dict() if hasattr(q, "to_dict") else {}
            srcs = " ".join(c.get("source", "") for c in d.get("chunks", []))
            indexed = "PROJECT_LOG" in srcs
        if not indexed:
            add("self-history-blind", "warning", "self_awareness",
                "The agent cannot recall its own PROJECT_LOG.md — self-history is blind.",
                "POST /v1/rag/index to include large docs (head-indexed since 2026-09-26).")
    except Exception:
        pass

    # --- Prompt budget vs served context (Round 13) ---
    try:
        from backend.agent.streaming import prompt_budget_report
        pb = await asyncio.to_thread(prompt_budget_report)
        if not pb.get("fits"):
            add("prompt-exceeds-context", "critical", "inference",
                f"Agent prompt ~{pb.get('total_estimate_tokens')} tokens does NOT fit the "
                f"served context {pb.get('served_context_tokens')} "
                f"(source={pb.get('context_source')}) — Ollama truncates it, so the model "
                "loses its rules and tool schemas.",
                "Raise PARAMETER num_ctx in data/Alpha_Wolf_Modelfile and run "
                "`ollama create alpha-wolf-agent -f <Modelfile>`.")
        elif pb.get("context_source") == "fallback":
            add("context-unknown", "info", "inference",
                "Could not read the served context from Ollama — assuming "
                f"{pb.get('served_context_tokens')} tokens (history is trimmed early).",
                "Check that Ollama is reachable at OLLAMA_BASE_URL.")
    except Exception as e:
        add("budget-unavailable", "warning", "inference",
            f"Prompt budget check failed: {type(e).__name__}: {e}", "Check backend logs.")

    # --- Web providers ---
    try:
        from backend.agent import web_search as engine
        probe = await asyncio.to_thread(engine.search, "test", max_results=1)
        src = probe.get("source")
        if src == "wikipedia":
            add("web-degraded", "warning", "web",
                "Web search degrades to Wikipedia-only (engines walled on this network).",
                "Set TAVILY_API_KEY / BRAVE_SEARCH_API_KEY / SERPAPI_API_KEY in .env.")
        elif not probe.get("success"):
            add("web-down", "critical", "web",
                f"All web providers failed: {probe.get('errors')}", "Check network / set API keys.")
    except Exception as e:
        add("web-unavailable", "warning", "web", f"Search engine error: {e}", "Check backend logs.")

    # --- Tools & skills ---
    try:
        n_tools = len(await asyncio.to_thread(agent_tools.list_tools))
        if n_tools < 10:
            add("tools-missing", "warning", "tools",
                f"Only {n_tools} tools registered (expected 12+).", "Check backend/agent/tools.py registry.")
    except Exception as e:
        add("tools-unavailable", "critical", "tools", f"Tool registry error: {e}", "Check backend logs.")
    try:
        n_skills = len(await asyncio.to_thread(_get_skills_manager().list_all))
        if n_skills == 0:
            add("no-skills", "info", "skills",
                "No skills installed — self-extension unused.", "The agent can install_skill() for itself.")
    except Exception as e:
        add("skills-unavailable", "warning", "skills", f"Skills registry error: {e}", "Check backend logs.")

    # --- Inference backend ---
    if HAS_HTTPX:
        try:
            import httpx as _hx
            with _hx.Client(timeout=5) as _c:
                _r = _c.get(f"{LLAMACPP_BASE_URL}/api/tags")
                if _r.status_code != 200:
                    add("inference-unhealthy", "critical", "inference",
                        f"Inference server HTTP {_r.status_code}.", "Start Ollama / llama-server.")
        except Exception as e:
            add("inference-down", "critical", "inference",
                f"Inference server unreachable at {LLAMACPP_BASE_URL}: {type(e).__name__}.",
                "Start Ollama (or set LLAMACPP_BASE_URL).")
    if not body:
        add("body-down", "critical", "memory", "Body not initialized.", "Restart backend.")

    # --- Disk ---
    try:
        if body:
            h = await asyncio.to_thread(body.health_check)
            du = (h or {}).get("disk_usage", {})
            if isinstance(du, dict) and du.get("size_mb", 0) > 5000:
                add("body-disk-heavy", "info", "storage",
                    f"Body folder is {du.get('size_mb')} MB.", "Apply backup retention (G15).")
    except Exception:
        pass

    sev_rank = {"critical": 0, "warning": 1, "info": 2}
    gaps.sort(key=lambda g: sev_rank.get(g["severity"], 3))
    return {"gaps": gaps, "count": len(gaps),
            "criticals": sum(1 for g in gaps if g["severity"] == "critical"),
            "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/v1/body/browse")
async def body_browse_endpoint(max_depth: int = 3):
    """Browse the body folder tree (read-only self-visibility).

    تصفح شجرة مجلد الجسد (رؤية ذاتية للقراءة فقط).
    """
    try:
        lc = live_context.get_live_context()
        return lc.get_body_tree(max_depth=max(1, min(max_depth, 5)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"body browse error: {e}")


@app.get("/v1/body/read")
async def body_read_endpoint(path: str, max_chars: int = 32000):
    """Read a file inside the body folder (guarded, read-only).

    قراءة ملف داخل مجلد الجسد (محمي، للقراءة فقط).
    `path` is relative to body/ — traversal outside is rejected.
    """
    # FIX 2026-09-26 (Round 17): prevent path traversal at the endpoint level.
    # Reject any path containing '..' or absolute path components before
    # passing to read_body_file (which has its own guard, but defense in depth).
    import asyncio
    import os
    if ".." in path or path.startswith("/") or path.startswith("\\") or (len(path) > 1 and path[1] == ":"):
        raise HTTPException(status_code=400, detail="Path traversal is not allowed")
    try:
        lc = await asyncio.to_thread(live_context.get_live_context)
        out = await asyncio.to_thread(lc.read_body_file, path, max_chars=max(500, min(max_chars, 100000)))
        if not out.get("success"):
            raise HTTPException(status_code=400, detail=out.get("error"))
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"body read error: {e}")


# ============================================================================
# Root
# ============================================================================

@app.get("/")
async def root():
    return {
        "name": "Alpha Wolf Agent Backend",
        "version": "0.3.0",
        "phase": "11+ v3.4 (Agent Capabilities + GraphRAG + Code Sandbox + Live RAG)",
        "endpoints": [
            "/v1/chat/completions",
            "/v1/chat/stream",
            "/v1/recall",
            "/v1/memory/episode", "/v1/memory/goal", "/v1/memory/mistake", "/v1/memory/reflection",
            "/v1/tools", "/v1/tools/execute", "/v1/tools/categories",
            "/v1/body/tools",
            "/v1/conversations",
            "/v1/skills", "/v1/install_skill", "/v1/run_skill",
            "/v1/mcp/tools", "/v1/mcp/rpc",
            "/v1/graph/entity", "/v1/graph/relation",
            "/v1/body/health", "/v1/body/backup", "/v1/self/summary",
            # Phase 11+ v3.4 — Agent capabilities
            "/v1/live-context/summary", "/v1/live-context/search", "/v1/live-context/inject",
            "/v1/code-exec/execute", "/v1/code-exec/safety-check",
            "/v1/rag/query", "/v1/rag/index", "/v1/rag/stats", "/v1/rag/job/{id}",
            "/v1/web/search", "/v1/web/fetch",
            "/v1/self/model", "/v1/self/gaps", "/v1/body/browse", "/v1/body/read",
            # Phase 11+ v3.5 — Self-Improvement + Memory + Tools
            "/v1/skills/install", "/v1/skills/{name}/run", "/v1/skills/text", "/v1/skills/registry",
            "/v1/tools/discover", "/v1/sessions", "/v1/memory/episodes",
            "/v1/rope-config", "/v1/vision/status", "/v1/vision/test",
            # Phase 40 Round 26 — Self-Improvement P2 endpoints
            "/v1/skills/forge", "/v1/skills/auto",
            "/v1/eval/{conv_id}", "/v1/eval/history", "/v1/eval/suggestions",
            "/v1/training/export", "/v1/training/files", "/v1/training/analyze",
            "/v1/training/train",
            "/v1/memory/short-term", "/v1/memory/short-term/clear",
            "/v1/memory/unified-recall",
        ],
        "docs": "/docs",
    }


# ============================================================================
# P2 Round 26 (2026-09-29) — Self-Improvement Endpoints
# ============================================================================
# Auto-skill forge, self-evaluation, training data export, LoRA scaffolding,
# and unified memory recall. All endpoints loopback-only by default.

# Tokens required for "dangerous" sub-operations (write to disk / train GPU):
# - ALPHA_WOLF_FORGE_TOKEN    : enables auto_save=true in /v1/skills/forge
# - ALPHA_WOLF_TRAIN_TOKEN    : enables actual LoRA training in /v1/training/train
# - ALPHA_WOLF_DEPLOY_TOKEN   : enables LoRA deployment (not implemented this round)
FORGE_TOKEN = os.environ.get("ALPHA_WOLF_FORGE_TOKEN", "").strip()
TRAIN_TOKEN = os.environ.get("ALPHA_WOLF_TRAIN_TOKEN", "").strip()


# ----- P2-1: Auto Skill Forge -----

@app.post("/v1/skills/forge")
async def forge_skill_endpoint(req: Request):
    """Auto-create a skill. auto_save=true requires ALPHA_WOLF_FORGE_TOKEN.

    إنشاء مهارة تلقائياً. الكتابة للقرص تتطلب توكن.
    """
    body = await req.json()
    auto_save = bool(body.get("auto_save", False))

    if auto_save:
        if not FORGE_TOKEN:
            raise HTTPException(
                status_code=403,
                detail=(
                    "auto_save=true requires ALPHA_WOLF_FORGE_TOKEN env var "
                    "to be set on the server. Set it in .env to enable."
                ),
            )
        provided = req.headers.get("X-Forge-Token", "")
        if provided != FORGE_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid X-Forge-Token")

    try:
        from backend.agent import auto_skill_forge
        result = auto_skill_forge.create_skill(
            name=body.get("name", ""),
            description=body.get("description", ""),
            code_template=body.get("code_template", ""),
            tags=body.get("tags"),
            auto_save=auto_save,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"forge failed: {e}")


@app.get("/v1/skills/auto")
async def list_auto_forged_skills_endpoint():
    """List all auto-generated skills.

    قائمة المهارات المُنشأة تلقائياً.
    """
    try:
        from backend.agent import auto_skill_forge
        return {"skills": auto_skill_forge.list_auto_forged_skills()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"list failed: {e}")


# ----- P2-2: Self-Evaluation -----

@app.post("/v1/eval/{conv_id}")
async def evaluate_conversation_endpoint(conv_id: str):
    """Auto-evaluate a conversation.

    تقييم تلقائي لمحادثة.
    """
    try:
        from backend.agent import self_evaluator
        return self_evaluator.evaluate_conversation(conv_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"eval failed: {e}")


@app.get("/v1/eval/history")
async def eval_history_endpoint(limit: int = 50):
    """Get self-evaluation history (latest eval per conversation).

    سجل التقييم الذاتي.
    """
    try:
        from backend.agent import self_evaluator
        return {
            "history": self_evaluator.get_evaluation_history(limit=limit),
            "count": len(self_evaluator.get_evaluation_history(limit=limit)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"history failed: {e}")


@app.get("/v1/eval/suggestions")
async def eval_suggestions_endpoint():
    """Get improvement suggestions based on recent evaluations.

    اقتراحات تحسين بناءً على التقييمات الحديثة.
    """
    try:
        from backend.agent import self_evaluator
        return {"suggestions": self_evaluator.get_improvement_suggestions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"suggestions failed: {e}")


# ----- P2-3: Training Data Flywheel -----

@app.post("/v1/training/export")
async def export_training_data_endpoint(min_score: float = 7.0, limit: int = 100):
    """Export successful conversations as JSONL training data.

    تصدير المحادثات الناجحة كبيانات تدريب JSONL.
    """
    try:
        from backend.agent import training_data_flywheel
        return training_data_flywheel.export_successful_conversations(
            min_score=min_score, limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"export failed: {e}")


@app.get("/v1/training/files")
async def list_training_files_endpoint():
    """List all auto-generated training data files.

    قائمة ملفات بيانات التدريب.
    """
    try:
        from backend.agent import training_data_flywheel
        return {"files": training_data_flywheel.list_training_files()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"list failed: {e}")


# ----- P2-4: Auto LoRA (scaffolding) -----

@app.get("/v1/training/analyze")
async def analyze_weaknesses_endpoint():
    """Analyze self-evaluation history for weaknesses (read-only).

    تحليل نقاط الضعف من سجل التقييم الذاتي.
    """
    try:
        from backend.agent import auto_lora_trainer
        return auto_lora_trainer.analyze_weaknesses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"analyze failed: {e}")


@app.post("/v1/training/train")
async def train_lora_endpoint(req: Request):
    """Train LoRA. BLOCKED unless ALPHA_WOLF_TRAIN_TOKEN matches confirm_token.

    تدريب LoRA (مسودة — يتطلب توكن).
    """
    try:
        body = await req.json()
        from backend.agent import auto_lora_trainer
        return auto_lora_trainer.train_lora(
            base_model=body.get("base_model", "llama3.1:8b"),
            adapter_name=body.get("adapter_name", "v_self_improve"),
            training_file=body.get("training_file", ""),
            epochs=int(body.get("epochs", 1)),
            confirm_token=body.get("confirm_token"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"train failed: {e}")


# ----- P2-5: Memory Layers -----

@app.get("/v1/memory/short-term")
async def short_term_endpoint():
    """Inspect the short-term memory cache (last 10 conversations).

    فحص الذاكرة قصيرة المدى.
    """
    try:
        from backend.agent import memory_layers
        return {
            "recent": memory_layers.short_term_list_recent(limit=5),
            "stats": memory_layers.short_term_stats(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"short_term failed: {e}")


@app.post("/v1/memory/short-term/clear")
async def short_term_clear_endpoint():
    """Clear the short-term cache (Iron Law #21: explicit action).

    مسح الذاكرة قصيرة المدى.
    """
    try:
        from backend.agent import memory_layers
        cleared = memory_layers.short_term_clear()
        return {"cleared": cleared}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"clear failed: {e}")


@app.get("/v1/memory/unified-recall")
async def unified_recall_endpoint(
    q: str,
    top_k: int = 5,
    include_short_term: bool = True,
    include_long_term: bool = True,
    include_episodic: bool = True,
    include_semantic: bool = True,
):
    """Unified recall across all 4 memory layers.

    بحث موحد عبر كل طبقات الذاكرة الأربع.
    """
    try:
        from backend.agent import memory_layers
        return memory_layers.recall_unified(
            query=q,
            top_k=top_k,
            include_short_term=include_short_term,
            include_long_term=include_long_term,
            include_episodic=include_episodic,
            include_semantic=include_semantic,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"recall failed: {e}")


# ============================================================================
# Admin Endpoints (Phase 35 — graceful shutdown for one-click launcher)
# ============================================================================

# Optional shared secret: requests must include header `X-Admin-Token: <token>`
# if ALPHA_WOLF_ADMIN_TOKEN is set in the environment. If unset, admin endpoints
# are open but only bound to localhost — keep it that way unless behind a proxy.
ADMIN_TOKEN = os.environ.get("ALPHA_WOLF_ADMIN_TOKEN", "").strip()


def _check_admin(request: Request) -> None:
    """Verify X-Admin-Token header if ADMIN_TOKEN is configured.
    
    التحقق من رمز الإدارة عند تهيئة ALPHA_WOLF_ADMIN_TOKEN.
    
    If the token env var is empty (default), admin endpoints are reachable
    only from 127.0.0.1 / localhost — FastAPI's own bind address is the second
    layer of defense, since we bind to 127.0.0.1 by default.
    """
    if not ADMIN_TOKEN:
        # No token configured — only allow if request comes from loopback.
        client_host = (request.client.host if request and request.client else "") or ""
        if client_host not in ("127.0.0.1", "::1", "localhost"):
            logger.warning(
                "Admin endpoint blocked from non-loopback host: %s "
                "(set ALPHA_WOLF_ADMIN_TOKEN to require auth)",
                client_host,
            )
            raise HTTPException(status_code=403, detail="Admin endpoints are loopback-only")
        return
    provided = request.headers.get("X-Admin-Token", "")
    if provided != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")


def _kill_process_listening_on(port: int) -> Optional[int]:
    """Find and kill the PID listening on `port` (Windows-friendly).
    
    إيجاد وقتل العملية المستمعة على المنفذ المحدد.
    Returns PID killed, or None if no process found.
    """
    try:
        if sys.platform == "win32":
            # Windows: netstat -ano | findstr :PORT
            out = subprocess.check_output(
                ["netstat", "-ano"],
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        else:
            out = subprocess.check_output(
                ["ss", "-ltnp"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in out.splitlines():
        # Match "  TCP    0.0.0.0:8501    0.0.0.0:0    LISTENING    1234"
        if f":{port}" not in line or "LISTENING" not in line and "LISTEN" not in line:
            continue
        parts = line.split()
        # Last column is PID
        for tok in reversed(parts):
            if tok.isdigit():
                pid = int(tok)
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(pid)],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        os.kill(pid, signal.SIGTERM)
                    logger.info("Killed PID %s on port %s", pid, port)
                    return pid
                except Exception as exc:
                    logger.warning("Failed to kill PID %s: %s", pid, exc)
        break
    return None


def _self_shutdown(delay_seconds: float = 1.0) -> None:
    """Schedule a graceful shutdown of THIS process after delay.
    
    جدولة إيقاف هذا الخادم بعد تأخير قصير (للسماح للرد بالوصول أولاً).
    """
    def _do():
        time.sleep(delay_seconds)
        logger.info("Admin shutdown requested — terminating FastAPI process")
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            # Fallback: hard exit
            os._exit(0)

    threading.Thread(target=_do, daemon=True).start()


@app.post("/v1/admin/shutdown")
async def admin_shutdown(request: Request, background: BackgroundTasks):
    """Gracefully stop the FastAPI backend.
    
    إيقاف الخادم بأناقة.
    
    The endpoint returns 200, then schedules SIGTERM to the current process
    after a 1s delay so the response can flush. The Streamlit frontend (if
    open) will detect the backend is offline and can show a notice.
    """
    _check_admin(request)
    logger.warning("Admin shutdown endpoint called")
    _self_shutdown(delay_seconds=1.0)
    return {
        "status": "shutting_down",
        "message": "Backend will terminate in ~1 second",
        "pid": os.getpid(),
    }


@app.post("/v1/admin/stop-all")
async def admin_stop_all(request: Request, background: BackgroundTasks):
    """Stop BOTH backend AND Streamlit frontend.
    
    إيقاف الخادم والواجهة معاً.
    
    1. Kills the process listening on port 8501 (Streamlit)
    2. Schedules SIGTERM for this FastAPI process
    3. Returns 200 immediately so the UI can confirm
    """
    _check_admin(request)
    logger.warning("Admin stop-all endpoint called — stopping everything")
    frontend_pid = _kill_process_listening_on(8501)
    _self_shutdown(delay_seconds=1.0)
    return {
        "status": "stopping_all",
        "message": "Backend + Frontend will terminate in ~1 second",
        "backend_pid": os.getpid(),
        "frontend_pid_killed": frontend_pid,
    }


@app.get("/v1/admin/status")
async def admin_status(request: Request):
    """Show admin protection status (no auth needed for status, but auth-gated if token set).
    
    عرض حالة حماية الإدارة.
    """
    _check_admin(request)
    return {
        "admin_token_configured": bool(ADMIN_TOKEN),
        "backend_pid": os.getpid(),
        "bound_host": FASTAPI_HOST,
        "bound_port": FASTAPI_PORT,
        "platform": sys.platform,
    }


# ============================================================================
# Entry Points
# ============================================================================

def run():
    """Production entry point."""
    import uvicorn
    uvicorn.run(app, host=FASTAPI_HOST, port=FASTAPI_PORT, log_level="info")


def run_dev():
    """Development entry point (auto-reload)."""
    import uvicorn
    uvicorn.run("backend.main:app", host=FASTAPI_HOST, port=FASTAPI_PORT,
                log_level="debug", reload=True)


if __name__ == "__main__":
    run()