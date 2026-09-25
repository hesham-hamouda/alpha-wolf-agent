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
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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

from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Alpha Wolf Agent Backend",
    version="0.1.0",
    description="Bridges body infrastructure (ChromaDB+NetworkX+SQLite+zvec) + llama.cpp inference",
)

# CORS (allow Chainlit frontend on port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to localhost in production
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


@app.on_event("startup")
async def startup_event():
    global body
    body = AlphaWolfBody()
    logger.info("✓ Alpha Wolf Body initialized")

    # Auto-load skills (Iron Law #15 — verify on startup)
    mgr = _get_skills_manager()
    load_result = mgr.auto_load()
    logger.info("✓ Skills auto-load: %d registered", load_result["registered"])


@app.on_event("shutdown")
async def shutdown_event():
    global body
    if body:
        body.close()
    logger.info("✓ Alpha Wolf Body closed")


# ============================================================================
# Pydantic Models
# ============================================================================

class ChatMessage(BaseModel):
    role: str = Field(..., description="system|user|assistant")
    content: str


class ChatRequest(BaseModel):
    model: str = "alpha-wolf-agent"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    use_body_recall: bool = True  # Whether to inject body context
    top_k: int = 5
    inject_tools: bool = True  # Inject tool definitions into system prompt (Phase 11+ v3.3)
    execute_tools: bool = False  # Auto-execute tool calls in response (Phase 11+ v3.3)
    use_live_context: bool = True  # Phase 11+ v3.4 — inject LIVE project folder awareness
    use_rag: bool = True  # Phase 11+ v3.4 — inject RAG-augmented context from Ollama embeddings


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

    # Prepend default Wolf personality system prompt (Iron Law #47)
    wolf_system = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits that guide all your actions:
1. Mistake Hunter (اقتناص الأخطاء) - you hunt mistakes, don't hide them
2. Goal Persistence (تتبع الأهداف) - you track goals relentlessly, never abandoning
3. Tenacity (الشراسة) - failure is data, not defeat
4. Deep Thinking (التفكير العميق) - you think deeply before acting
5. Resourceful (استخدام الموارد) - you use every tool at the right time
6. Self-Aware (الوعي الذاتي) - you know what you know and what you don't
7. Reinforcement Learning (التعلم التعزيزي) - you learn from every hunt

Your name is Alpha Wolf Agent. You serve Quхандд هشام with tenacity, intelligence, and resourcefulness."""
    # Only prepend if no system message present
    if not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": wolf_system})

    # Inject tool definitions if requested (Phase 11+ v3.3)
    if req.inject_tools:
        tool_system = {
            "role": "system",
            "content": agent_tools.format_tools_for_prompt(),
        }
        messages.insert(0, tool_system)
        logger.info("  [Tools] injected %d tool definitions", len(agent_tools.TOOL_SPECS))

    if req.use_body_recall and body:
        # Recall relevant context from body
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if last_user:
            results = body.recall(last_user, top_k=req.top_k)
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
                lc = live_context.get_live_context()
                ctx = lc.build_system_context(query=last_user, max_depth=2, search_top_k=3)
                messages.insert(0, {"role": "system", "content": ctx})
                logger.info(f"  [LiveContext] injected {len(ctx)} chars for query: {last_user[:50]}")
            except Exception as e:
                logger.warning(f"  [LiveContext] failed: {e}")

    # Phase 11+ v3.4 — Live RAG (Ollama embeddings + ChromaDB)
    if req.use_rag:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if last_user:
            try:
                rag_ctx = rag.build_rag_context(last_user, top_k=min(req.top_k, 3))
                if rag_ctx:
                    messages.insert(0, {"role": "system", "content": rag_ctx})
                    logger.info(f"  [RAG] injected {len(rag_ctx)} chars for query: {last_user[:50]}")
            except Exception as e:
                logger.warning(f"  [RAG] failed: {e}")

    # Proxy to llama.cpp
    payload = {
        "model": req.model,
        "messages": messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "stream": req.stream,
    }

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
            full_content = assistant_msg.get("content", "")

            # Parse for tool calls
            parsed = tool_calling.parse_tool_calls(full_content)
            tool_results = []

            if parsed.has_tool_calls:
                logger.info("  [Tools] executing %d tool calls", len(parsed.tool_calls))
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
                        json={"model": req.model, "messages": messages, "temperature": req.temperature},
                    )
                    resp2.raise_for_status()
                    final_data = resp2.json()

                # Merge tool calls into response
                final_data["tool_calls_executed"] = tool_results
                return final_data

            return response_data
        except httpx.HTTPError as e:
            logger.error(f"  [Chat] llama.cpp error: {e}")
            raise HTTPException(status_code=502, detail=f"llama.cpp error: {e}")

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
        raise HTTPException(status_code=502, detail=f"llama.cpp error: {e}")


# ============================================================================
# Streaming Chat Endpoint (Phase 11+ v3.3)
# ============================================================================

class StreamChatRequest(BaseModel):
    """Streaming chat request with optional conversation_id."""
    model: str = "alpha-wolf-agent"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    conversation_id: Optional[str] = None  # For persistent history
    auto_tools: bool = True  # Auto-execute tool calls (Phase 11+ v3.3)
    max_tool_iterations: int = 3


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

    # Load history if conversation_id provided
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    if req.conversation_id:
        history = agent_memory.get_conversation(req.conversation_id, include_system=False)
        if history:
            history_msgs = [{"role": m["role"], "content": m["content"]} for m in history]
            # Merge: history first, then new messages
            messages = history_msgs + messages
            # Persist user message
            last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            if last_user:
                try:
                    agent_memory.add_message(req.conversation_id, "user", last_user)
                except ValueError:
                    logger.warning("Conversation %s not found", req.conversation_id)

    # Build payload
    payload = {
        "model": req.model,
        "messages": messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "stream": True,
    }

    if req.auto_tools:
        # Use tool-aware streaming (auto-executes tool calls)
        return StreamingResponse(
            streaming.stream_with_tool_execution(
                LLAMACPP_BASE_URL,
                payload,
                max_tool_iterations=req.max_tool_iterations,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable proxy buffering
            },
        )
    else:
        # Simple streaming (no tool execution)
        return StreamingResponse(
            streaming.stream_from_ollama(LLAMACPP_BASE_URL, payload),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
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

    Useful for testing or scripted use.
    """
    result = agent_tools.execute_tool(name, arguments)
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


@app.post("/v1/install_skill")
async def install_skill_endpoint(req: InstallSkillRequest):
    """Install a skill from a URL or local file.

    تثبيت مهارة من رابط أو ملف محلي.

    Args:
        source: URL (http://...) or local file path
        target_name: Optional name for the skill
        skill_type: 'url' or 'file'
    """
    try:
        if req.skill_type == "url" or req.source.startswith(("http://", "https://")):
            result = agent_skills.install_skill_from_url(req.source, req.target_name)
        else:
            result = agent_skills.install_skill_from_file(req.source, req.target_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Install failed: {e}")


@app.post("/v1/run_skill")
async def run_skill_endpoint(req: RunSkillRequest):
    """Execute an installed skill."""
    args = req.arguments or {}
    result = agent_skills.run_skill(req.skill_name, **args)
    return result


@app.delete("/v1/skills/{skill_name}")
async def uninstall_skill_endpoint(skill_name: str):
    """Uninstall a skill."""
    return agent_skills.uninstall_skill(skill_name)


# ============================================================================
# Skills System v2 (Phase 11+ v3.5) — RESTful endpoints
# ============================================================================

@app.post("/v1/skills/install")
async def install_skill_v2(req: InstallSkillRequest):
    """Install a skill (file path or URL).

    تثبيت مهارة (مسار ملف أو URL).
    Alias for /v1/install_skill with RESTful URL.
    """
    mgr = _get_skills_manager()
    if req.skill_type == "url" or req.source.startswith(("http://", "https://")):
        return mgr.install_from_url(req.source, req.target_name)
    return mgr.install_from_file(req.source, req.target_name)


@app.post("/v1/skills/{skill_name}/run")
async def run_skill_v2(
    skill_name: str,
    arguments: Optional[dict] = Body(default=None, embed=True),
):
    """Run a skill by name.

    تشغيل مهارة بالاسم.
    Alias for /v1/run_skill with RESTful URL.
    """
    mgr = _get_skills_manager()
    return mgr.run(skill_name, arguments or {})


@app.post("/v1/skills/text")
async def install_skill_from_text(
    name: str = Body(...),
    source: str = Body(...),
):
    """Install a skill from inline Python text (Iron Law #33 self-improvement).

    تثبيت مهارة من نص بايثون مباشر (التحسين الذاتي).
    """
    mgr = _get_skills_manager()
    return mgr.install_from_text(name, source)


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

@app.post("/v1/recall")
async def recall(req: RecallRequest):
    """Semantic recall across KBs."""
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
    """Register a tool."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    tid = body.register_tool(
        name=req.name,
        invocation=req.invocation,
        description=req.description,
        category=req.category,
    )
    return {"id": tid, "status": "registered"}


@app.get("/v1/tools")
async def list_tools(category: Optional[str] = None):
    """List registered tools."""
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
        result = code_exec.execute_python(req.code, timeout_sec=req.timeout_sec)
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


@app.post("/v1/rag/query")
async def rag_query(req: RAGQueryRequest):
    """Query the RAG store for similar chunks (Ollama + ChromaDB).

    البحث في متجر RAG عن قطع مشابهة.
    """
    try:
        r = rag.get_rag()
        result = r.query(req.query, top_k=req.top_k)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag query error: {e}")


@app.post("/v1/rag/index")
async def rag_index(req: RAGIndexRequest):
    """Index the project folder into RAG (slow — runs once).

    فهرسة مجلد المشروع في RAG.
    """
    try:
        r = rag.get_rag()
        stats = r.index_directory(patterns=req.patterns, force=req.force)
        return {
            "indexed": stats,
            "total_chunks": r._total_chunks(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag index error: {e}")


@app.get("/v1/rag/stats")
async def rag_stats():
    """RAG store stats."""
    try:
        r = rag.get_rag()
        return r.stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag stats error: {e}")




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
    backup_path = body.backup()
    return {"backup_path": backup_path, "status": "created"}


@app.get("/v1/self/summary")
async def self_summary():
    """Alpha Wolf self-summary (Wolf Trait: Self-Aware)."""
    if not body:
        raise HTTPException(status_code=503, detail="Body not initialized")
    return body.get_self_summary()


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
            "/v1/conversations",
            "/v1/skills", "/v1/install_skill", "/v1/run_skill",
            "/v1/mcp/tools", "/v1/mcp/rpc",
            "/v1/graph/entity", "/v1/graph/relation",
            "/v1/body/health", "/v1/body/backup", "/v1/self/summary",
            # Phase 11+ v3.4 — Agent capabilities
            "/v1/live-context/summary", "/v1/live-context/search", "/v1/live-context/inject",
            "/v1/code-exec/execute", "/v1/code-exec/safety-check",
            "/v1/rag/query", "/v1/rag/index", "/v1/rag/stats",
            # Phase 11+ v3.5 — Self-Improvement + Memory + Tools
            "/v1/skills/install", "/v1/skills/{name}/run", "/v1/skills/text", "/v1/skills/registry",
            "/v1/tools/discover", "/v1/sessions", "/v1/memory/episodes",
            "/v1/rope-config", "/v1/vision/status", "/v1/vision/test",
        ],
        "docs": "/docs",
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