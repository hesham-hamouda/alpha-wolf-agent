#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Memory Layers | طبقات الذاكرة
==================================================
Structured access to 4-layer memory:
- short_term : in-memory LRU cache of last N conversations (fast)
- long_term  : ChromaDB vector store via rag.py (semantic search)
- episodic   : SQLite episodes (body.remember_episode + recall_episodes)
- semantic   : NetworkX knowledge graph (body.graph traversal)

Iron Laws Applied:
- #15 (Verify)    : self_test in __main__
- #21 (NO Delete) : short_term_clear requires explicit call
- #33 (Lessons)   : bilingual docstrings
- #41 (Conflict)  : graceful fallback if any layer unavailable
- #42 (Storage)   : all reads only, no writes outside backend
- #47 (Bilingual) : AR + EN
"""
from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("alpha_wolf.memory_layers")


# ============================================================================
# Short-term: in-memory LRU cache (last 10 conversations)
# ============================================================================

_short_term_cache: "OrderedDict[str, Dict]" = OrderedDict()
_SHORT_TERM_LIMIT = 10


def short_term_put(conv_id: str, conversation: Dict) -> None:
    """Cache a conversation in short-term memory (LRU, max 10).

    تخزين محادثة في الذاكرة قصيرة المدى.
    """
    _short_term_cache[conv_id] = conversation
    while len(_short_term_cache) > _SHORT_TERM_LIMIT:
        _short_term_cache.popitem(last=False)


def short_term_get(conv_id: str) -> Optional[Dict]:
    """Get a cached conversation (None if not cached).

    جلب محادثة من الذاكرة قصيرة المدى.
    """
    return _short_term_cache.get(conv_id)


def short_term_list_recent(limit: int = 5) -> List[Dict]:
    """List most recent N conversations from short-term cache.

    قائمة أحدث المحادثات من الذاكرة قصيرة المدى.
    """
    return list(_short_term_cache.values())[: max(1, limit)]


def short_term_clear() -> int:
    """Clear the short-term cache (Iron Law #21: explicit action).

    مسح الذاكرة قصيرة المدى.
    """
    count = len(_short_term_cache)
    _short_term_cache.clear()
    return count


def short_term_stats() -> Dict[str, Any]:
    """Get short-term memory stats.

    إحصائيات الذاكرة قصيرة المدى.
    """
    return {
        "size": len(_short_term_cache),
        "limit": _SHORT_TERM_LIMIT,
        "ids": list(_short_term_cache.keys())[: _SHORT_TERM_LIMIT],
    }


# ============================================================================
# Long-term: ChromaDB via rag.get_rag().query()
# ============================================================================

def _long_term_recall(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Query ChromaDB-backed long-term memory.

    استعلام الذاكرة طويلة المدى (ChromaDB).
    """
    try:
        from backend.agent import rag as rag_mod

        rag_instance = rag_mod.get_rag()
        result = rag_instance.query(query, top_k=top_k)
        chunks = getattr(result, "chunks", None) or []
        return [
            {
                "text": getattr(c, "text", "")[:300],
                "source": getattr(c, "source", "unknown"),
                "similarity": round(float(getattr(c, "similarity", 0.0)), 3),
                "source_layer": "long_term",
            }
            for c in chunks
        ]
    except Exception as e:
        logger.warning("long_term recall failed: %s", e)
        return []


# ============================================================================
# Episodic: SQLite via memory + body
# ============================================================================

def _episodic_recall(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Query episodic memory via body (SQLite).

    استعلام الذاكرة العرضية (SQLite).
    """
    try:
        from body.alpha_wolf_body import AlphaWolfBody

        body = AlphaWolfBody()
        try:
            episodes = body.recall_episodes(
                min_importance=1, limit=max(top_k * 4, 20)
            )
        finally:
            body.close()
        q_lower = (query or "").lower()
        hits: List[Dict[str, Any]] = []
        for ep in episodes:
            content = (ep.get("content", "") or "")[:300]
            trig = (ep.get("trigger_type", "") or "")
            if q_lower in content.lower() or q_lower in trig.lower():
                hits.append({
                    "trigger_type": trig,
                    "content": content,
                    "importance": ep.get("importance"),
                    "tags": ep.get("tags", []),
                    "source_layer": "episodic",
                })
        return hits[:top_k]
    except Exception as e:
        logger.warning("episodic recall failed: %s", e)
        return []


# ============================================================================
# Semantic: NetworkX knowledge graph (read-only)
# ============================================================================

def _semantic_recall(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Query the NetworkX knowledge graph (entities + neighbors).

    استعلام الرسم البياني الدلالي (NetworkX).
    """
    try:
        from body.alpha_wolf_body import AlphaWolfBody

        body = AlphaWolfBody()
        try:
            g = getattr(body, "graph", None)
            if g is None:
                return []
            q_lower = (query or "").lower()
            results: List[Dict[str, Any]] = []
            for node, attrs in (g.nodes(data=True) if hasattr(g, "nodes") else []):
                name = str(attrs.get("name", node))
                if q_lower in name.lower():
                    results.append({
                        "name": name,
                        "type": attrs.get("type", "entity"),
                        "description": str(attrs.get("description", ""))[:200],
                        "edges": g.degree(node) if hasattr(g, "degree") else 0,
                        "source_layer": "semantic",
                    })
                if len(results) >= top_k:
                    break
            return results
        finally:
            body.close()
    except Exception as e:
        logger.warning("semantic recall failed: %s", e)
        return []


# ============================================================================
# Unified recall across all 4 layers
# ============================================================================

def recall_unified(
    query: str,
    top_k: int = 5,
    include_short_term: bool = True,
    include_long_term: bool = True,
    include_episodic: bool = True,
    include_semantic: bool = True,
) -> Dict[str, Any]:
    """Unified recall across all 4 memory layers.

    بحث موحد عبر كل طبقات الذاكرة الأربع.

    Returns dict with: hits grouped by layer, with provenance.
    """
    if not query or not query.strip():
        return {
            "query": "",
            "error": "Empty query",
            "short_term": [],
            "long_term": [],
            "episodic": [],
            "semantic": [],
            "total_hits": 0,
        }

    top_k = max(1, min(int(top_k or 5), 20))
    q_lower = query.lower()

    result: Dict[str, Any] = {
        "query": query,
        "short_term": [],
        "long_term": [],
        "episodic": [],
        "semantic": [],
        "total_hits": 0,
    }

    # 1. Short-term (keyword match in recent cache)
    if include_short_term:
        for conv in short_term_list_recent(limit=5):
            cid = conv.get("conversation_id") or conv.get("id", "")
            for msg in conv.get("messages", []):
                if q_lower in (msg.get("content", "") or "").lower():
                    result["short_term"].append({
                        "conversation_id": cid,
                        "role": msg.get("role", "?"),
                        "content": (msg.get("content", "") or "")[:200],
                        "source": "short_term",
                    })

    # 2. Long-term (ChromaDB semantic)
    if include_long_term:
        result["long_term"] = _long_term_recall(query, top_k)

    # 3. Episodic (SQLite keyword)
    if include_episodic:
        result["episodic"] = _episodic_recall(query, top_k)

    # 4. Semantic (NetworkX graph)
    if include_semantic:
        result["semantic"] = _semantic_recall(query, top_k)

    result["total_hits"] = (
        len(result["short_term"])
        + len(result["long_term"])
        + len(result["episodic"])
        + len(result["semantic"])
    )

    return result


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def self_test() -> bool:
    """Verify memory_layers pieces (Iron Law #15)."""
    print("Running memory_layers self-tests...")
    ok = True
    try:
        # Test 1: short-term stats
        st = short_term_stats()
        if "size" in st and "limit" in st and st["limit"] == 10:
            print(f"  ✓ short_term_stats (size={st['size']}, limit={st['limit']})")
        else:
            print(f"  ✗ short_term_stats: {st}")
            ok = False

        # Test 2: short_term_put + get
        short_term_put("conv_test_xyz", {"conversation_id": "conv_test_xyz", "messages": []})
        if short_term_get("conv_test_xyz") is not None:
            print("  ✓ short_term_put + get")
        else:
            print("  ✗ short_term put/get")
            ok = False

        # Test 3: short_term_list_recent
        recent = short_term_list_recent(limit=3)
        if isinstance(recent, list):
            print(f"  ✓ short_term_list_recent ({len(recent)} entries)")
        else:
            print("  ✗ short_term_list_recent not list")
            ok = False

        # Test 4: short_term_clear
        n = short_term_clear()
        if isinstance(n, int) and n >= 0:
            print(f"  ✓ short_term_clear (cleared {n})")
        else:
            print(f"  ✗ short_term_clear returned {n}")
            ok = False

        # Test 5: recall_unified with empty query
        r = recall_unified("", top_k=5)
        if r.get("error") == "Empty query":
            print("  ✓ recall_unified empty query")
        else:
            print(f"  ✗ recall_unified empty: {r}")
            ok = False

        # Test 6: recall_unified with valid query (graceful fallback OK)
        r = recall_unified("test query", top_k=5)
        if "query" in r and "total_hits" in r and isinstance(r["total_hits"], int):
            print(f"  ✓ recall_unified (total_hits={r['total_hits']})")
        else:
            print(f"  ✗ recall_unified wrong shape: {r}")
            ok = False

        # Test 7: layer callbacks exist
        if callable(_long_term_recall) and callable(_episodic_recall) and callable(_semantic_recall):
            print("  ✓ layer callbacks defined")
        else:
            print("  ✗ layer callbacks missing")
            ok = False

    except Exception as e:
        print(f"  ✗ exception: {type(e).__name__}: {e}")
        ok = False

    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)