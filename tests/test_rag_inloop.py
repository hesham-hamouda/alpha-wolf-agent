"""RAG-in-loop regression (FIX 2026-10-14): sync embed/build calls made inside
a running event loop must still return vectors/context (via sync fallbacks),
never die on asyncio.run(RuntimeError). Skipped when Ollama is unreachable."""
import asyncio
import sys
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent import rag  # noqa: E402


def _ollama_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/", timeout=5)
        return True
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(not _ollama_up(), reason="Ollama down")


@requires_ollama
def test_embed_text_inside_running_loop():
    async def _go():
        return rag.embed_text("wolf traits goals")
    vec = asyncio.run(_go())
    assert isinstance(vec, list) and len(vec) > 10


@requires_ollama
def test_build_rag_context_inside_running_loop():
    async def _go():
        return rag.build_rag_context("wolf traits goals", top_k=2)
    ctx = asyncio.run(_go())
    assert isinstance(ctx, str) and len(ctx) > 100
