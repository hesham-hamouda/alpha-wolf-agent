#!/usr/bin/env python3
r"""
Alpha Wolf Agent — FastAPI Backend
===================================
Bridges the body infrastructure (ChromaDB + NetworkX + SQLite + zvec)
with the inference engine (llama.cpp) and the frontend (Chainlit).

Endpoints:
- /v1/chat/completions     — OpenAI-compatible (proxy to llama.cpp)
- /v1/recall               — semantic search across KBs
- /v1/memory/episode       — episodic memory CRUD
- /v1/memory/goal          — goal tracking CRUD
- /v1/memory/mistake       — mistake log CRUD
- /v1/memory/reflection    — reflection CRUD
- /v1/tools                — tool registry
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
- #42 (Storage Discipline) — all paths in workspace, NOT body
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

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from body.alpha_wolf_body import AlphaWolfBody

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


@app.on_event("startup")
async def startup_event():
    global body
    body = AlphaWolfBody()
    logger.info("✓ Alpha Wolf Body initialized")


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

    # Proxy to llama.cpp
    payload = {
        "model": req.model,
        "messages": messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "stream": req.stream,
    }
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
# Body Health + Backup + Self-Summary
# ============================================================================

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
        "version": "0.1.0",
        "endpoints": [
            "/v1/chat/completions",
            "/v1/recall",
            "/v1/memory/episode", "/v1/memory/goal", "/v1/memory/mistake", "/v1/memory/reflection",
            "/v1/tools", "/v1/graph/entity", "/v1/graph/relation",
            "/v1/body/health", "/v1/body/backup", "/v1/self/summary",
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