#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Body Wrapper Class
======================================
Single entry point to interact with the body (ChromaDB + NetworkX + SQLite + zvec).

Wolf Traits mapped to body methods:
- Mistake Hunter       → log_mistake() / recall_mistakes()
- Goal Persistence     → track_goal() / recall_goals()
- Tenacity             → (handled via applied_count on reflections)
- Deep Thinking        → reflect() / recall_reflections()
- Resourceful          → register_tool() / invoke_tool()
- Self-Aware           → health_check() / get_self_summary()
- Reinforcement Learn. → reflect() applied_count tracking

Usage:
    cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
    python body/alpha_wolf_body.py --verify     # health check
    python body/alpha_wolf_body.py --demo      # run all methods

Iron Laws Applied:
- #14 (Snapshot)        → backup() method
- #15 (Verify)          → health_check() returns structured dict
- #21 (NO Deletion)      → soft delete via deleted_at
- #22 (Autonomous)       → methods run without user prompts
- #36 (5-Layer Save)     → all writes logged to curation_log
"""

from __future__ import annotations

import json
import pickle
import shutil
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BODY_ROOT = Path(__file__).resolve().parent

# Try to import dependencies (graceful degradation if missing)
try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    import zvec
    HAS_ZVEC = True
except ImportError:
    HAS_ZVEC = False


class AlphaWolfBody:
    """Unified wrapper for Alpha Wolf Agent's body infrastructure.

    Layers:
    1. ChromaDB  (vectors, semantic search)
    2. NetworkX  (typed knowledge graph)
    3. SQLite    (structured memory: goals, mistakes, episodes, etc.)
    4. zvec      (backup vector layer)
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else BODY_ROOT
        self.chromadb_dir = self.root / "knowledge_graph" / "chromadb"
        self.networkx_dir = self.root / "knowledge_graph" / "networkx"
        self.graph_file = self.networkx_dir / "graph.pickle"
        self.schema_file = self.networkx_dir / "schema.json"
        self.state_db = self.root / "memory" / "state.db"
        self.zvec_dir = self.root / "memory" / "embeddings" / "zvec"
        self.backups_dir = self.root / "backups"
        self.curation_log_jsonl = self.root / "curation_log.jsonl"

        # Initialize connections
        self._init_chromadb()
        self._init_networkx()
        self._init_sqlite()
        self._init_zvec()

    # ========================================================================
    # Initialization (private)
    # ========================================================================

    def _init_chromadb(self):
        if not HAS_CHROMADB:
            self.chroma_client = None
            return
        self.chroma_client = chromadb.PersistentClient(path=str(self.chromadb_dir))

    def _init_networkx(self):
        if not HAS_NETWORKX:
            self.graph = None
            return
        if self.graph_file.exists():
            with open(self.graph_file, "rb") as f:
                self.graph = pickle.load(f)
        else:
            self.graph = nx.DiGraph()
            self._save_graph()

    def _init_sqlite(self):
        self.sqlite_conn = sqlite3.connect(str(self.state_db), isolation_level=None)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL")
        self.sqlite_conn.execute("PRAGMA foreign_keys=ON")

    def _init_zvec(self):
        if not HAS_ZVEC:
            return
        # zvec v0.7.0 requires collections to be created on-demand
        # (handled in update_kb / recall methods)
        pass

    # ========================================================================
    # Wolf Trait #1 — Mistake Hunter
    # ========================================================================

    def log_mistake(self, context: str, what_went_wrong: str, lesson: str,
                    root_cause: Optional[str] = None, prevention: Optional[str] = None,
                    severity: int = 5, episode_id: Optional[str] = None,
                    related_entity_id: Optional[str] = None) -> str:
        """Log a mistake with context + lesson (Wolf Trait: Mistake Hunter)."""
        mid = str(uuid.uuid4())
        with self.sqlite_conn:
            self.sqlite_conn.execute(
                "INSERT INTO mistakes(id, context, what_went_wrong, root_cause, lesson, "
                "prevention, severity, episode_id, related_entity_id) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (mid, context, what_went_wrong, root_cause, lesson, prevention,
                 severity, episode_id, related_entity_id),
            )
        # Sync to ChromaDB kb_mistakes (text only, embedding via Ollama later)
        if self.chroma_client:
            try:
                coll = self.chroma_client.get_or_create_collection("kb_mistakes")
                coll.add(
                    documents=[f"{context}\n\nWhat went wrong: {what_went_wrong}\n\nLesson: {lesson}"],
                    ids=[mid],
                    metadatas=[{
                        "severity": severity,
                        "episode_id": episode_id or "",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "source_agent": "alpha-wolf",
                    }],
                )
            except Exception:
                pass  # graceful degradation
        # Log curation
        self._log_curation("add", "kb_mistakes", mid, f"Severity {severity}: {lesson[:50]}")
        return mid

    def recall_mistakes(self, severity_min: int = 1, limit: int = 20) -> list[dict]:
        """Recall mistakes (Wolf Trait: learning from failures)."""
        cur = self.sqlite_conn.execute(
            "SELECT id, context, what_went_wrong, lesson, severity, recurrence_count, created_at "
            "FROM mistakes WHERE severity >= ? AND deleted_at IS NULL "
            "ORDER BY severity DESC, created_at DESC LIMIT ?",
            (severity_min, limit),
        )
        return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    # ========================================================================
    # Wolf Trait #2 — Goal Persistence
    # ========================================================================

    def track_goal(self, title: str, description: Optional[str] = None,
                   priority: int = 5, deadline: Optional[str] = None,
                   parent_id: Optional[str] = None,
                   status: str = "open") -> str:
        """Track a goal with status (Wolf Trait: Goal Persistence)."""
        gid = str(uuid.uuid4())
        with self.sqlite_conn:
            self.sqlite_conn.execute(
                "INSERT INTO goals(id, parent_id, title, description, status, priority, deadline) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (gid, parent_id, title, description, status, priority, deadline),
            )
        self._log_curation("add", "kb_goals", gid, f"Goal: {title}")
        return gid

    def update_goal_status(self, goal_id: str, status: str,
                           progress_pct: Optional[float] = None) -> bool:
        """Update goal status (open -> active -> done)."""
        if status == "done":
            sql = (
                "UPDATE goals SET status=?, progress_pct=COALESCE(?, progress_pct), "
                "updated_at=CURRENT_TIMESTAMP, completed_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND deleted_at IS NULL"
            )
        else:
            sql = (
                "UPDATE goals SET status=?, progress_pct=COALESCE(?, progress_pct), "
                "updated_at=CURRENT_TIMESTAMP, completed_at=completed_at "
                "WHERE id=? AND deleted_at IS NULL"
            )
        with self.sqlite_conn:
            cur = self.sqlite_conn.execute(sql, (status, progress_pct, goal_id))
            return cur.rowcount > 0

    def recall_goals(self, status: Optional[str] = "open", limit: int = 20) -> list[dict]:
        """Recall active goals."""
        if status:
            cur = self.sqlite_conn.execute(
                "SELECT id, title, status, priority, progress_pct, deadline "
                "FROM goals WHERE status=? AND deleted_at IS NULL "
                "ORDER BY priority DESC, deadline LIMIT ?",
                (status, limit),
            )
        else:
            cur = self.sqlite_conn.execute(
                "SELECT id, title, status, priority, progress_pct, deadline "
                "FROM goals WHERE deleted_at IS NULL "
                "ORDER BY priority DESC, deadline LIMIT ?",
                (limit,),
            )
        return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    # ========================================================================
    # Wolf Trait #4 — Deep Thinking (Reflections)
    # ========================================================================

    def reflect(self, trigger: str, insight: str, confidence: float = 0.5,
                episode_id: Optional[str] = None) -> str:
        """Record a reflection (Wolf Trait: Reinforcement Learning)."""
        rid = str(uuid.uuid4())
        with self.sqlite_conn:
            self.sqlite_conn.execute(
                "INSERT INTO reflections(id, episode_id, trigger, insight, confidence) "
                "VALUES(?, ?, ?, ?, ?)",
                (rid, episode_id, trigger, insight, confidence),
            )
        self._log_curation("add", "kb_self", rid, f"Reflection: {insight[:80]}")
        return rid

    def recall_reflections(self, min_confidence: float = 0.5, limit: int = 10) -> list[dict]:
        """Recall past reflections."""
        cur = self.sqlite_conn.execute(
            "SELECT id, trigger, insight, confidence, applied_count, created_at "
            "FROM reflections WHERE confidence >= ? AND deleted_at IS NULL "
            "ORDER BY confidence DESC, applied_count DESC LIMIT ?",
            (min_confidence, limit),
        )
        return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    # ========================================================================
    # Wolf Trait #5 — Resourceful (Episodic Memory)
    # ========================================================================

    def remember_episode(self, content: str, trigger_type: str = "user_task",
                         importance: int = 5, session_id: Optional[str] = None,
                         summary: Optional[str] = None) -> str:
        """Store an episode in episodic memory."""
        eid = str(uuid.uuid4())
        with self.sqlite_conn:
            self.sqlite_conn.execute(
                "INSERT INTO episodes(id, occurred_at, trigger_type, content, importance, "
                "session_id, summary) "
                "VALUES(?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)",
                (eid, trigger_type, content, importance, session_id, summary),
            )
        return eid

    def recall_episodes(self, trigger_type: Optional[str] = None,
                        min_importance: int = 1, limit: int = 20) -> list[dict]:
        """Recall episodes (episodic memory replay)."""
        if trigger_type:
            cur = self.sqlite_conn.execute(
                "SELECT id, occurred_at, trigger_type, content, importance, summary "
                "FROM episodes WHERE trigger_type=? AND importance >= ? AND deleted_at IS NULL "
                "ORDER BY occurred_at DESC LIMIT ?",
                (trigger_type, min_importance, limit),
            )
        else:
            cur = self.sqlite_conn.execute(
                "SELECT id, occurred_at, trigger_type, content, importance, summary "
                "FROM episodes WHERE importance >= ? AND deleted_at IS NULL "
                "ORDER BY occurred_at DESC LIMIT ?",
                (min_importance, limit),
            )
        return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    # ========================================================================
    # Wolf Trait #5 — Resourceful (Tool Registry)
    # ========================================================================

    def register_tool(self, name: str, invocation: str, description: Optional[str] = None,
                      category: Optional[str] = None) -> str:
        """Register a tool (function/tool calling)."""
        tid = str(uuid.uuid4())
        with self.sqlite_conn:
            self.sqlite_conn.execute(
                "INSERT INTO tools(id, name, invocation, description, category) "
                "VALUES(?, ?, ?, ?, ?)",
                (tid, name, invocation, description, category),
            )
        return tid

    def list_tools(self, category: Optional[str] = None, enabled_only: bool = True) -> list[dict]:
        """List registered tools."""
        if category:
            cur = self.sqlite_conn.execute(
                "SELECT id, name, invocation, description, category, invocation_count, last_invoked_at "
                "FROM tools WHERE category=? AND enabled=? ORDER BY name",
                (category, 1 if enabled_only else None),
            )
        else:
            cur = self.sqlite_conn.execute(
                "SELECT id, name, invocation, description, category, invocation_count, last_invoked_at "
                "FROM tools WHERE enabled=? ORDER BY category, name",
                (1 if enabled_only else None,),
            )
        return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

    def mark_tool_invoked(self, tool_name: str):
        """Mark tool as invoked (Wolf Trait: usage tracking)."""
        with self.sqlite_conn:
            self.sqlite_conn.execute(
                "UPDATE tools SET invocation_count = invocation_count + 1, "
                "last_invoked_at = CURRENT_TIMESTAMP WHERE name=?",
                (tool_name,),
            )

    # ========================================================================
    # Semantic Search (ChromaDB + zvec)
    # ========================================================================

    def update_kb(self, content: str, target_kb: str = "kb_self",
                  metadata: Optional[dict] = None) -> str:
        """Add/update knowledge in a KB collection (self-curation)."""
        if not self.chroma_client:
            return ""
        try:
            coll = self.chroma_client.get_or_create_collection(target_kb)
            doc_id = str(uuid.uuid4())
            meta = metadata or {}
            meta.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            meta.setdefault("source_agent", "alpha-wolf")
            coll.add(documents=[content], ids=[doc_id], metadatas=[meta])
            self._log_curation("add", target_kb, doc_id, content[:80])
            return doc_id
        except Exception as e:
            print(f"  update_kb error: {e}")
            return ""

    def recall(self, query: str, kb_filter: Optional[str] = None,
               top_k: int = 5) -> list[dict]:
        """Semantic recall via ChromaDB."""
        if not self.chroma_client:
            return []
        try:
            coll = self.chroma_client.get_or_create_collection(kb_filter or "kb_self")
            results = coll.query(query_texts=[query], n_results=top_k)
            docs = results.get("documents", [[]])[0]
            ids = results.get("ids", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0] if results.get("distances") else [None]*len(docs)
            return [
                {"id": i, "content": d, "metadata": m, "distance": dist}
                for i, d, m, dist in zip(ids, docs, metas, distances)
            ]
        except Exception as e:
            print(f"  recall error: {e}")
            return []

    # ========================================================================
    # Knowledge Graph (NetworkX)
    # ========================================================================

    def add_entity(self, node_type: str, name: str,
                   attributes: Optional[dict] = None) -> str:
        """Add entity to knowledge graph."""
        if self.graph is None:
            return ""
        eid = str(uuid.uuid4())
        # Iron Law #21: check for existing entity by (node_type, name)
        for node_id, data in self.graph.nodes(data=True):
            if data.get("node_type") == node_type and data.get("name") == name:
                return node_id  # return existing
        attrs = attributes or {}
        attrs.update({"node_type": node_type, "name": name, "id": eid})
        self.graph.add_node(eid, **attrs)
        self._save_graph()
        # Sync to SQLite
        with self.sqlite_conn:
            self.sqlite_conn.execute(
                "INSERT OR IGNORE INTO entities(id, node_type, name, attributes, graph_synced_at) "
                "VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (eid, node_type, name, json.dumps(attrs)),
            )
        return eid

    def add_relation(self, source_id: str, target_id: str, edge_type: str,
                     weight: float = 1.0, attributes: Optional[dict] = None) -> str:
        """Add typed edge to knowledge graph."""
        if self.graph is None:
            return ""
        rid = str(uuid.uuid4())
        attrs = attributes or {}
        attrs.update({"edge_type": edge_type, "weight": weight, "id": rid})
        self.graph.add_edge(source_id, target_id, **attrs)
        self._save_graph()
        # Sync to SQLite
        with self.sqlite_conn:
            self.sqlite_conn.execute(
                "INSERT OR IGNORE INTO relations(id, source_id, target_id, edge_type, weight, attributes, graph_synced_at) "
                "VALUES(?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (rid, source_id, target_id, edge_type, weight, json.dumps(attrs)),
            )
        return rid

    def get_related(self, entity_id: str, depth: int = 2) -> list[dict]:
        """Get related entities via graph traversal."""
        if not self.graph or entity_id not in self.graph:
            return []
        result = []
        for target_id in nx.single_source_shortest_path_length(
            self.graph, entity_id, cutoff=depth
        ).keys():
            if target_id != entity_id:
                data = self.graph.nodes[target_id]
                result.append({"id": target_id, **data})
        return result

    # ========================================================================
    # Backup (Iron Law #14)
    # ========================================================================

    def backup(self) -> str:
        """Create snapshot of entire body (Iron Law #14)."""
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        dst = self.backups_dir / ts
        dst.mkdir(parents=True, exist_ok=True)

        # Snapshot graph
        if self.graph_file.exists():
            shutil.copy2(self.graph_file, dst / "graph.pickle")

        # Snapshot SQLite via online backup API
        backup_db = sqlite3.connect(str(dst / "state.db"))
        with backup_db:
            self.sqlite_conn.backup(backup_db)

        # Snapshot ChromaDB
        if self.chromadb_dir.exists():
            shutil.copytree(self.chromadb_dir, dst / "chromadb", dirs_exist_ok=True)

        # Manifest
        manifest = {
            "timestamp": ts,
            "graph_nodes": self.graph.number_of_nodes() if self.graph is not None else 0,
            "graph_edges": self.graph.number_of_edges() if self.graph is not None else 0,
            "tables": [row[0] for row in self.sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()],
        }
        with open(dst / "MANIFEST.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        return str(dst)

    # ========================================================================
    # Health Check (Iron Law #15)
    # ========================================================================

    def health_check(self) -> dict:
        """Return structured health snapshot."""
        import os
        return {
            "chromadb": {
                "ok": HAS_CHROMADB,
                "collections": len(self.chroma_client.list_collections()) if self.chroma_client else 0,
            },
            "networkx": {
                "ok": HAS_NETWORKX,
                "nodes": self.graph.number_of_nodes() if self.graph is not None else 0,
                "edges": self.graph.number_of_edges() if self.graph is not None else 0,
            },
            "sqlite": {
                "ok": True,
                "integrity": self.sqlite_conn.execute("PRAGMA integrity_check").fetchone()[0],
                "tables": [row[0] for row in self.sqlite_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()],
                "size_mb": round(os.path.getsize(self.state_db) / 1024 / 1024, 2),
            },
            "zvec": {"ok": HAS_ZVEC},
            "disk_usage": {
                "body_root": str(self.root),
                "size_mb": sum(
                    os.path.getsize(os.path.join(dirpath, f))
                    for dirpath, _, files in os.walk(self.root)
                    for f in files
                ) / 1024 / 1024,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_self_summary(self) -> dict:
        """Return Alpha Wolf self-summary (Wolf Trait: Self-Aware)."""
        return {
            "name": "Alpha Wolf Agent",
            "model": "unsloth/Meta-Llama-3.1-8B-Instruct",
            "training_mix": "Mix D Sequential Full",
            "wolf_traits": {
                "mistake_hunter": len(self.recall_mistakes(limit=100)),
                "goal_persistence": len(self.recall_goals(status=None, limit=100)),
                "tenacity": "(counted via reflection applied_count)",
                "deep_thinking": len(self.recall_reflections(min_confidence=0.3, limit=100)),
                "resourceful": len(self.list_tools()),
                "self_aware": True,
                "reinforcement_learning": True,
            },
            "memory": {
                "episodic_count": len(self.recall_episodes(min_importance=1, limit=1000)),
                "active_goals": len(self.recall_goals(status="active", limit=100)),
                "open_goals": len(self.recall_goals(status="open", limit=100)),
            },
        }

    # ========================================================================
    # Internal helpers
    # ========================================================================

    def _save_graph(self):
        if self.graph is None:
            return
        fd, tmp = tempfile.mkstemp(suffix=".pickle.tmp", dir=str(self.graph_file.parent))
        import os
        os.close(fd)
        with open(tmp, "wb") as f:
            pickle.dump(self.graph, f, protocol=pickle.HIGHEST_PROTOCOL)
        shutil.move(tmp, str(self.graph_file))

    def _log_curation(self, action: str, target_kb: Optional[str], target_id: Optional[str],
                      summary: Optional[str], source: str = "alpha_wolf_body.py"):
        """Log to SQLite curation_log + JSONL."""
        try:
            self.sqlite_conn.execute(
                "INSERT INTO curation_log(action, target_kb, target_id, summary, source) "
                "VALUES(?, ?, ?, ?, ?)",
                (action, target_kb, target_id, summary, source),
            )
            with open(self.curation_log_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "action": action,
                    "target_kb": target_kb,
                    "target_id": target_id,
                    "summary": summary,
                    "source": source,
                }) + "\n")
        except Exception as e:
            print(f"  _log_curation error: {e}")

    def close(self):
        """Close all connections."""
        try:
            self.sqlite_conn.close()
        except Exception:
            pass


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Alpha Wolf Body CLI")
    parser.add_argument("--verify", action="store_true", help="Run health check")
    parser.add_argument("--demo", action="store_true", help="Run all methods demo")
    parser.add_argument("--summary", action="store_true", help="Print self-summary")
    args = parser.parse_args()

    body = AlphaWolfBody()

    if args.verify or (not args.demo and not args.summary):
        print("=" * 70)
        print("ALPHA WOLF BODY — Health Check")
        print("=" * 70)
        health = body.health_check()
        print(json.dumps(health, indent=2, ensure_ascii=False))
        body.close()
        return 0

    if args.summary:
        print("=" * 70)
        print("ALPHA WOLF AGENT — Self Summary")
        print("=" * 70)
        print(json.dumps(body.get_self_summary(), indent=2, ensure_ascii=False))
        body.close()
        return 0

    if args.demo:
        print("=" * 70)
        print("ALPHA WOLF BODY — Demo (all methods)")
        print("=" * 70)

        # 1. Track goal
        gid = body.track_goal("Build body infrastructure", priority=10, status="active")
        print(f"  [Goal] tracked: {gid[:8]}...")

        # 2. Log mistake
        mid = body.log_mistake(
            context="Initial body plan was ChromaDB + edges.json (insufficient)",
            what_went_wrong="edges.json is schema-free JSON, no graph queries",
            lesson="Need NetworkX typed graph + SQLite structured memory",
            severity=8,
        )
        print(f"  [Mistake] logged: {mid[:8]}...")

        # 3. Reflect
        rid = body.reflect(
            trigger="After 3-Expert deliberation on body framework",
            insight="Hybrid stack (ChromaDB+NetworkX+SQLite+zvec) gives best AGORA fit",
            confidence=0.85,
        )
        print(f"  [Reflection] stored: {rid[:8]}...")

        # 4. Remember episode
        eid = body.remember_episode(
            content="Phase 11+ v3.0: built body with hybrid 4-layer DB stack",
            importance=9,
            trigger_type="self_reflection",
        )
        print(f"  [Episode] stored: {eid[:8]}...")

        # 5. Register tool (idempotent — unique name each run)
        tool_name = f"alpha_wolf_search_{uuid.uuid4().hex[:8]}"
        tid = body.register_tool(
            name=tool_name,
            invocation="alpha_wolf.recall(query, kb_filter, top_k)",
            description="Semantic search across body KBs",
            category="retrieval",
        )
        print(f"  [Tool] registered: {tid[:8]}... ({tool_name})")

        # 6. Add knowledge to KB
        kid = body.update_kb(
            content="Alpha Wolf Agent has 7 Wolf traits: mistake hunter, goal persistence, tenacity, deep thinking, resourceful, self-aware, reinforcement learning",
            target_kb="kb_self",
        )
        print(f"  [KB] updated: {kid[:8]}...")

        # 7. Add graph entities + relation (idempotent — unique names each run)
        wolf_name = f"Alpha Wolf Agent {uuid.uuid4().hex[:6]}"
        trait_name = f"Wolf Traits {uuid.uuid4().hex[:6]}"
        wolf_id = body.add_entity("Concept", wolf_name, {"domain": "AI"})
        trait_id = body.add_entity("Concept", trait_name, {"domain": "personality"})
        rel_id = body.add_relation(wolf_id, trait_id, "knows_about")
        print(f"  [Graph] entity + relation: {wolf_id[:8]}... --{rel_id[:8]}...--> {trait_id[:8]}...")

        # 8. Recall
        results = body.recall("wolf traits personality", kb_filter="kb_self", top_k=3)
        print(f"  [Recall] found {len(results)} results for 'wolf traits personality'")

        # 9. Backup
        backup_path = body.backup()
        print(f"  [Backup] snapshot at: {backup_path}")

        # 10. Health + Summary
        print()
        print(json.dumps(body.health_check(), indent=2))
        print()
        print(json.dumps(body.get_self_summary(), indent=2, ensure_ascii=False))

        body.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())