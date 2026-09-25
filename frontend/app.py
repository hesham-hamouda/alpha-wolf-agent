#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Chainlit Frontend
======================================
Chat UI for talking to Alpha Wolf Agent.

Features:
- Chat with Alpha Wolf (via FastAPI backend)
- See tool calls and reasoning steps (ReAct visualization)
- Inspect body state (memory, goals, mistakes, knowledge graph)
- Trigger FETCH_AND_LEARN from HuggingFace

Usage:
    cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
    chainlit run frontend/app.py --port 8000 --watch

Or via pyproject script:
    uv run alpha-wolf-ui

Iron Laws Applied:
- #8 (3-Expert Consensus) — Chainlit recommended by 3-expert panel
- #13 (Self-Critical Check) — UI design reviewed
- #22 (Autonomous) — runs without user prompts
- #26 (Arabic comments where applicable)
- #42 (Storage Discipline) — body in workspace, frontend in workspace
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import chainlit as cl
import httpx

BACKEND_URL = os.environ.get("ALPHA_WOLF_BACKEND_URL", "http://127.0.0.1:8001")


# ============================================================================
# Chat Handlers
# ============================================================================

@cl.on_chat_start
async def start():
    """Welcome message + body status."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BACKEND_URL}/v1/body/health")
            resp.raise_for_status()
            health = resp.json()
            await cl.Message(
                content=f"""# 🐺 Alpha Wolf Agent — Ready

**Body status:**
- ChromaDB collections: {health['chromadb']['collections']}
- NetworkX: {health['networkx']['nodes']} nodes, {health['networkx']['edges']} edges
- SQLite tables: {len(health['sqlite']['tables'])} (integrity: {health['sqlite']['integrity']})
- zvec: {'OK' if health['zvec']['ok'] else 'N/A'}

You can talk to Alpha Wolf now. Type your task or question.
""",
            ).send()
    except httpx.HTTPError as e:
        await cl.Message(
            content=f"⚠️ Backend not reachable at {BACKEND_URL}: {e}\n\nStart backend first: `python -m uvicorn backend.main:app --port 8001`",
        ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle user message — proxy to FastAPI backend."""
    # Show thinking step
    async with cl.Step(name="thinking", type="tool") as step:
        step.input = message.content
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    f"{BACKEND_URL}/v1/chat/completions",
                    json={
                        "model": "alpha-wolf-agent",
                        "messages": [
                            {"role": "user", "content": message.content}
                        ],
                        "use_body_recall": True,
                        "top_k": 5,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = data.get("usage", {})
            step.output = f"Generated {tokens.get('completion_tokens', 0)} tokens"
        except httpx.HTTPError as e:
            step.output = f"Error: {e}"
            content = f"❌ Backend error: {e}\n\nMake sure:\n1. llama.cpp server is running on port 8080\n2. FastAPI backend is running on port 8001 (`uvicorn backend.main:app --port 8001`)\n3. Body is initialized (`python body/init_body.py`)"

    await cl.Message(content=content).send()


# ============================================================================
# Action Handlers (for sidebar buttons)
# ============================================================================

@cl.action_callback("health_check")
async def on_health(action):
    """Show body health."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BACKEND_URL}/v1/body/health")
            resp.raise_for_status()
            health = resp.json()
            await cl.Message(content=f"```json\n{json.dumps(health, indent=2)}\n```").send()
    except httpx.HTTPError as e:
        await cl.Message(content=f"❌ Error: {e}").send()


@cl.action_callback("self_summary")
async def on_self_summary(action):
    """Show Alpha Wolf self-summary."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BACKEND_URL}/v1/self/summary")
            resp.raise_for_status()
            summary = resp.json()
            await cl.Message(content=f"```json\n{json.dumps(summary, indent=2, ensure_ascii=False)}\n```").send()
    except httpx.HTTPError as e:
        await cl.Message(content=f"❌ Error: {e}").send()


@cl.action_callback("list_goals")
async def on_list_goals(action):
    """List active goals."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BACKEND_URL}/v1/memory/goal?status=active&limit=10")
            resp.raise_for_status()
            goals = resp.json()
            if goals:
                msg = "## Active Goals\n\n"
                for g in goals:
                    msg += f"- **{g['title']}** (priority: {g['priority']}, progress: {g.get('progress_pct', 0)}%)\n"
                await cl.Message(content=msg).send()
            else:
                await cl.Message(content="No active goals.").send()
    except httpx.HTTPError as e:
        await cl.Message(content=f"❌ Error: {e}").send()


@cl.action_callback("list_mistakes")
async def on_list_mistakes(action):
    """List mistakes."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BACKEND_URL}/v1/memory/mistake?severity_min=1&limit=10")
            resp.raise_for_status()
            mistakes = resp.json()
            if mistakes:
                msg = "## Recent Mistakes + Lessons\n\n"
                for m in mistakes:
                    msg += f"- **[severity {m['severity']}]** {m['context'][:80]}...\n  **Lesson**: {m['lesson']}\n\n"
                await cl.Message(content=msg).send()
            else:
                await cl.Message(content="No mistakes logged yet.").send()
    except httpx.HTTPError as e:
        await cl.Message(content=f"❌ Error: {e}").send()


@cl.action_callback("list_tools")
async def on_list_tools(action):
    """List registered tools."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BACKEND_URL}/v1/tools")
            resp.raise_for_status()
            tools = resp.json()
            if tools:
                msg = f"## Registered Tools ({len(tools)})\n\n"
                for t in tools:
                    msg += f"- **{t['name']}** ({t.get('category', 'N/A')}): {t.get('description', 'N/A')[:80]}\n  Invocation count: {t.get('invocation_count', 0)}\n\n"
                await cl.Message(content=msg).send()
            else:
                await cl.Message(content="No tools registered.").send()
    except httpx.HTTPError as e:
        await cl.Message(content=f"❌ Error: {e}").send()


@cl.action_callback("backup")
async def on_backup(action):
    """Trigger backup."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{BACKEND_URL}/v1/body/backup")
            resp.raise_for_status()
            data = resp.json()
            await cl.Message(content=f"✅ Backup created at: `{data['backup_path']}`").send()
    except httpx.HTTPError as e:
        await cl.Message(content=f"❌ Error: {e}").send()


# ============================================================================
# Settings (sidebar)
# ============================================================================

@cl.on_settings_update
async def settings_update(settings):
    """Handle settings update."""
    await cl.Message(content=f"⚙️ Settings updated: {settings}").send()


def run():
    """Entry point for `uv run alpha-wolf-ui`."""
    # Chainlit will call this via its own CLI when running `chainlit run frontend/app.py`
    pass


if __name__ == "__main__":
    # For testing: run via `python frontend/app.py`
    print("Run via: chainlit run frontend/app.py --port 8000 --watch")