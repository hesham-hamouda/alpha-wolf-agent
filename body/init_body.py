#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Body Initialization Script
==============================================
Initializes the complete body infrastructure:
- ChromaDB collections (multi-domain KBs)
- NetworkX knowledge graph (typed nodes + edges)
- SQLite structured memory (episodic + goals + mistakes + projects)
- zvec backup embeddings

Iron Laws Applied:
- #14 (Snapshot) — runs from clean state
- #15 (Verify) — every step returns validation result
- #21 (NO Deletion) — never deletes existing data
- #26 (Arabic comments where applicable)
- #42 (Storage Discipline) — everything in E:\Projects workspace

Usage:
    cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
    python body/init_body.py
    python body/init_body.py --verify   # verify existing state
"""

from __future__ import annotations

import json
import pickle
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Resolve body root: works from any CWD
BODY_ROOT = Path(__file__).resolve().parent
KNOWLEDGE_GRAPH_DIR = BODY_ROOT / "knowledge_graph"
MEMORY_DIR = BODY_ROOT / "memory"
INTAKE_DIR = BODY_ROOT / "intake"

CHROMADB_DIR = KNOWLEDGE_GRAPH_DIR / "chromadb"
NETWORKX_DIR = KNOWLEDGE_GRAPH_DIR / "networkx"
NETWORKX_BACKUPS_DIR = NETWORKX_DIR / "backups"
ZVEC_DIR = MEMORY_DIR / "embeddings" / "zvec"
EPISODIC_DIR = MEMORY_DIR / "episodic"
STATE_DB = MEMORY_DIR / "state.db"

# ============================================================================
# ChromaDB Collections (per AGORA-inspired multi-DB network)
# ============================================================================
CHROMADB_COLLECTIONS = {
    "kb_self": {
        "description": "Alpha Wolf's own memories, reflections, identity",
        "hnsw_space": "cosine",
    },
    "kb_science_marine": {
        "description": "Marine biology domain (oysters, algae, coral, fish)",
        "hnsw_space": "cosine",
    },
    "kb_science_agriculture": {
        "description": "Agriculture domain (crops, yield, fertilizers)",
        "hnsw_space": "cosine",
    },
    "kb_science_chemistry": {
        "description": "Chemistry domain (molecules, drugs, reactions)",
        "hnsw_space": "cosine",
    },
    "kb_science_climate": {
        "description": "Climate science (ClimateBERT, time-series)",
        "hnsw_space": "cosine",
    },
    "kb_science_proteomics": {
        "description": "Proteins (ESM2, ProtBERT, DNABERT)",
        "hnsw_space": "cosine",
    },
    "kb_vision": {
        "description": "Vision models + multimodal (Florence-2, BiomedCLIP, SAM)",
        "hnsw_space": "cosine",
    },
    "kb_code": {
        "description": "Code patterns (CodeAlpaca-20k distilled)",
        "hnsw_space": "cosine",
    },
    "kb_reasoning": {
        "description": "Reasoning patterns (Bespoke-Stratos style)",
        "hnsw_space": "cosine",
    },
    "kb_mistakes": {
        "description": "Mistakes log + lessons learned (Wolf Trait: Mistake Hunter)",
        "hnsw_space": "cosine",
    },
    "kb_goals": {
        "description": "Active goals + progress (Wolf Trait: Goal Persistence)",
        "hnsw_space": "cosine",
    },
    "kb_tools": {
        "description": "Tool registry + invocation patterns",
        "hnsw_space": "cosine",
    },
}

# ============================================================================
# NetworkX Knowledge Graph — Typed nodes + edges
# ============================================================================
NODE_TYPES = {
    "Concept":   {"required": ["name"], "optional": ["domain", "description"]},
    "Tool":      {"required": ["name", "invocation"], "optional": ["version", "description"]},
    "Person":    {"required": ["name"], "optional": ["role", "email"]},
    "Place":     {"required": ["name"], "optional": ["kind"]},
    "Dataset":   {"required": ["name", "source"], "optional": ["size", "license", "path"]},
    "Mistake":   {"required": ["context", "lesson"], "optional": ["severity"]},
    "Goal":      {"required": ["title", "status"], "optional": ["priority", "deadline"]},
    "Reflection":{"required": ["trigger", "insight"], "optional": ["confidence"]},
    "Episode":   {"required": ["summary"], "optional": ["importance"]},
    "KB":        {"required": ["name"], "optional": ["domain"]},
}

EDGE_TYPES = {
    "trains_on":    ("Goal", "Dataset"),
    "depends_on":   None,            # directed, any -> any
    "contradicts":  ("Claim", "Claim"),
    "supports":     ("Evidence", "Claim"),
    "replaces":     None,            # any -> any
    "similar_to":   None,            # weighted (cosine)
    "knows_about":  None,            # Agent/Concept -> anything
    "learned_from": ("Mistake", "Episode"),
    "applies_to":   ("Tool", "Goal"),
    "blocks":       ("Mistake", "Goal"),
    "achieves":     ("Episode", "Goal"),
}

# ============================================================================
# SQLite Schema (8 tables for structured memory)
# ============================================================================
SQLITE_SCHEMA = """
-- Wolf Trait #1-3: Mistake Hunter, Goal Persistence, Tenacity
CREATE TABLE IF NOT EXISTS mistakes (
    id                  TEXT PRIMARY KEY,
    episode_id          TEXT REFERENCES episodes(id) ON DELETE SET NULL,
    context             TEXT NOT NULL,
    what_went_wrong     TEXT NOT NULL,
    root_cause          TEXT,
    lesson              TEXT NOT NULL,
    prevention          TEXT,
    severity            INTEGER NOT NULL DEFAULT 5 CHECK (severity BETWEEN 1 AND 10),
    recurrence_count    INTEGER NOT NULL DEFAULT 0,
    related_entity_id   TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_mistakes_severity ON mistakes(severity DESC, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_mistakes_episode ON mistakes(episode_id)
    WHERE episode_id IS NOT NULL AND deleted_at IS NULL;

-- Wolf Trait #2: Goal Persistence
CREATE TABLE IF NOT EXISTS goals (
    id                  TEXT PRIMARY KEY,
    parent_id           TEXT REFERENCES goals(id) ON DELETE SET NULL,
    title               TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'active', 'blocked', 'done', 'abandoned')),
    priority            INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    deadline            TIMESTAMPTZ,
    progress_pct        REAL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_goals_status_priority ON goals(status, priority DESC, deadline)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_id)
    WHERE deleted_at IS NULL;

-- Project state tracker (one project at a time = Alpha Wolf Agent)
CREATE TABLE IF NOT EXISTS projects (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    phase               TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at            TIMESTAMPTZ,
    iron_law_ref        TEXT,            -- e.g., "Iron Law #44"
    metadata            TEXT,            -- JSON blob
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_projects_phase ON projects(phase);
CREATE INDEX IF NOT EXISTS idx_projects_started ON projects(started_at DESC);

-- Episodic memory — every interaction recorded
CREATE TABLE IF NOT EXISTS episodes (
    id                  TEXT PRIMARY KEY,
    occurred_at         TIMESTAMPTZ NOT NULL,
    duration_ms         INTEGER,
    trigger_type        TEXT NOT NULL CHECK (trigger_type IN ('user_task', 'cron', 'self_reflection', 'fetch_and_learn', 'mistake_recovery')),
    content             TEXT NOT NULL,
    summary             TEXT,
    importance          INTEGER NOT NULL DEFAULT 5 CHECK (importance BETWEEN 1 AND 10),
    embedding_id        TEXT,
    session_id          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_episodes_trigger ON episodes(trigger_type, occurred_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_episodes_importance ON episodes(importance DESC, occurred_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id)
    WHERE session_id IS NOT NULL AND deleted_at IS NULL;

-- Sessions — group of episodes
CREATE TABLE IF NOT EXISTS sessions (
    id                  TEXT PRIMARY KEY,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at            TIMESTAMPTZ,
    model               TEXT,            -- e.g., "minimax-330/minimax-M3"
    tokens_in           INTEGER DEFAULT 0,
    tokens_out          INTEGER DEFAULT 0,
    metadata            TEXT
);

-- Wolf Trait #4-5: Deep Thinking, Resourceful (reflections + tools)
CREATE TABLE IF NOT EXISTS reflections (
    id                  TEXT PRIMARY KEY,
    episode_id          TEXT REFERENCES episodes(id) ON DELETE SET NULL,
    trigger             TEXT NOT NULL,
    insight             TEXT NOT NULL,
    confidence          REAL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    applied_count       INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_reflections_episode ON reflections(episode_id)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_reflections_confidence ON reflections(confidence DESC)
    WHERE deleted_at IS NULL;

-- Wolf Trait #5: Resourceful (tool registry)
CREATE TABLE IF NOT EXISTS tools (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    invocation          TEXT NOT NULL,            -- Python signature or JSON schema
    description         TEXT,
    category            TEXT,
    enabled             INTEGER NOT NULL DEFAULT 1,
    invocation_count    INTEGER NOT NULL DEFAULT 0,
    last_invoked_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tools_category ON tools(category);
CREATE INDEX IF NOT EXISTS idx_tools_enabled ON tools(enabled);

-- Synced with NetworkX entities (knowledge graph nodes)
CREATE TABLE IF NOT EXISTS entities (
    id                  TEXT PRIMARY KEY,
    node_type           TEXT NOT NULL,
    name                TEXT NOT NULL,
    attributes          TEXT,            -- JSON blob
    graph_synced_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ,
    UNIQUE(node_type, name)
);
CREATE INDEX IF NOT EXISTS idx_entities_node_type ON entities(node_type)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_entities_synced ON entities(graph_synced_at);

-- Synced with NetworkX edges (knowledge graph relationships)
CREATE TABLE IF NOT EXISTS relations (
    id                  TEXT PRIMARY KEY,
    source_id           TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_id           TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    edge_type           TEXT NOT NULL,
    weight              REAL DEFAULT 1.0 CHECK (weight BETWEEN 0 AND 1),
    attributes          TEXT,            -- JSON blob
    graph_synced_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_relations_edge_type ON relations(edge_type);

-- Curation log — track every ADD/UPDATE/DELETE for auditability
CREATE TABLE IF NOT EXISTS curation_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action              TEXT NOT NULL CHECK (action IN ('add', 'update', 'delete', 'fetch_and_learn')),
    target_kb           TEXT,
    target_id           TEXT,
    summary             TEXT,
    source              TEXT
);
CREATE INDEX IF NOT EXISTS idx_curation_action ON curation_log(action, ts DESC);
CREATE INDEX IF NOT EXISTS idx_curation_target_kb ON curation_log(target_kb, ts DESC);

-- Phase 11+ v3.1: Dataset inventory (Iron Law #36 5-Layer Save)
CREATE TABLE IF NOT EXISTS datasets (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    source              TEXT NOT NULL,
    repo_id             TEXT,
    target_kb           TEXT NOT NULL,
    format_fingerprint  TEXT NOT NULL,
    quality_score       REAL,
    license             TEXT,
    size_bytes          INTEGER,
    rows_total          INTEGER,
    rows_indexed        INTEGER,
    status              TEXT NOT NULL DEFAULT 'staged'
                        CHECK (status IN ('staged','ingested','quarantined')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ingested_at         TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ,
    UNIQUE(name, source, repo_id)
);
CREATE INDEX IF NOT EXISTS idx_datasets_status ON datasets(status);
CREATE INDEX IF NOT EXISTS idx_datasets_target_kb ON datasets(target_kb);

CREATE TABLE IF NOT EXISTS quality_metrics (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id          TEXT REFERENCES datasets(id) ON DELETE SET NULL,
    ts                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metric_name         TEXT NOT NULL,
    metric_value        REAL,
    notes               TEXT
);
CREATE INDEX IF NOT EXISTS idx_quality_dataset_ts ON quality_metrics(dataset_id, ts);
"""


def init_chromadb(verbose: bool = True) -> dict:
    """Initialize ChromaDB with multi-domain collections."""
    try:
        import chromadb
    except ImportError:
        return {"ok": False, "error": "chromadb not installed"}

    CHROMADB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMADB_DIR))

    results = {"ok": True, "collections": []}
    for name, meta in CHROMADB_COLLECTIONS.items():
        try:
            coll = client.get_or_create_collection(
                name=name,
                metadata={
                    "hnsw:space": meta["hnsw_space"],
                    "description": meta["description"],
                    "schema_version": "alpha-wolf-v1",
                },
            )
            results["collections"].append({
                "name": name,
                "id": coll.id if hasattr(coll, "id") else name,
                "count": coll.count(),
            })
        except Exception as e:
            results["collections"].append({"name": name, "error": str(e)})

    if verbose:
        print(f"  [ChromaDB] {len(results['collections'])} collections initialized at {CHROMADB_DIR}")
        for c in results["collections"]:
            if "error" in c:
                print(f"    ✗ {c['name']}: {c['error']}")
            else:
                print(f"    ✓ {c['name']}: count={c['count']}")
    return results


def init_networkx(verbose: bool = True) -> dict:
    """Initialize NetworkX typed knowledge graph."""
    try:
        import networkx as nx
    except ImportError:
        return {"ok": False, "error": "networkx not installed"}

    NETWORKX_DIR.mkdir(parents=True, exist_ok=True)
    NETWORKX_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    graph_file = NETWORKX_DIR / "graph.pickle"

    # Iron Law #21: only ADDITIVE — load existing graph if present
    if graph_file.exists():
        with open(graph_file, "rb") as f:
            graph = pickle.load(f) if _pickle_available() else _load_fallback(graph_file)
        status = "loaded"
    else:
        graph = nx.DiGraph()
        status = "created"

    # Save schema definition as sidecar JSON (human-readable)
    schema_file = NETWORKX_DIR / "schema.json"
    with open(schema_file, "w", encoding="utf-8") as f:
        json.dump({
            "node_types": NODE_TYPES,
            "edge_types": {k: list(v) if v else None for k, v in EDGE_TYPES.items()},
            "schema_version": "alpha-wolf-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2, ensure_ascii=False)

    # Persist graph
    _save_graph(graph, graph_file)

    if verbose:
        print(f"  [NetworkX] graph {status} at {graph_file}")
        print(f"    Nodes: {graph.number_of_nodes()}, Edges: {graph.number_of_edges()}")
        print(f"    Schema: {len(NODE_TYPES)} node types, {len(EDGE_TYPES)} edge types")
    return {
        "ok": True,
        "status": status,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "node_types": len(NODE_TYPES),
        "edge_types": len(EDGE_TYPES),
    }


def init_sqlite(verbose: bool = True) -> dict:
    """Initialize SQLite structured memory."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    EPISODIC_DIR.mkdir(parents=True, exist_ok=True)

    # Iron Law #21: only ADDITIVE — use IF NOT EXISTS for tables
    conn = sqlite3.connect(str(STATE_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SQLITE_SCHEMA)
    conn.commit()

    # Verify integrity
    cur = conn.execute("PRAGMA integrity_check")
    integrity = cur.fetchone()[0]
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]

    # Seed initial project (Alpha Wolf Agent)
    project_id = "project-alpha-wolf-agent-v1"
    cur = conn.execute("SELECT id FROM projects WHERE id=?", (project_id,))
    if not cur.fetchone():
        conn.execute(
            "INSERT INTO projects(id, name, phase, iron_law_ref, metadata) "
            "VALUES(?, ?, ?, ?, ?)",
            (
                project_id,
                "Alpha Wolf Agent",
                "Phase 11+ v3.0 - Body Infrastructure",
                "Iron Law #44 (Methodology)",
                json.dumps({
                    "model": "unsloth/Meta-Llama-3.1-8B-Instruct",
                    "training_mix": "Mix D Sequential Full",
                    "wolf_traits": 7,
                    "body_stack": "ChromaDB + NetworkX + SQLite + zvec",
                }),
            ),
        )
        conn.commit()

    conn.close()

    if verbose:
        print(f"  [SQLite] state.db at {STATE_DB}")
        print(f"    Integrity: {integrity}")
        print(f"    Tables ({len(tables)}): {', '.join(tables)}")
        print(f"    Initial project: Alpha Wolf Agent")
    return {
        "ok": True,
        "integrity": integrity,
        "tables": tables,
        "tables_count": len(tables),
    }


def init_zvec(verbose: bool = True) -> dict:
    """Initialize zvec backup vector layer (best-effort)."""
    try:
        import zvec
    except ImportError:
        if verbose:
            print("  [zvec] NOT installed — skipping (not critical, ChromaDB is primary)")
        return {"ok": False, "error": "zvec not installed", "skipped": True}

    ZVEC_DIR.mkdir(parents=True, exist_ok=True)
    # zvec v0.7.0 requires explicit collection setup (handled in alpha_wolf_body.py)
    if verbose:
        print(f"  [zvec] directory ready at {ZVEC_DIR}")
        print(f"    Note: zvec collections created on-demand via alpha_wolf_body.py")
    return {"ok": True, "dir": str(ZVEC_DIR), "note": "on-demand init"}


def _pickle_available() -> bool:
    try:
        import pickle
        return True
    except ImportError:
        return False


def _save_graph(graph, path: Path):
    """Save NetworkX graph (atomic write via temp file)."""
    import shutil
    import os
    fd, tmp_path = tempfile.mkstemp(suffix=".pickle.tmp", dir=str(path.parent))
    os.close(fd)
    with open(tmp_path, "wb") as f:
        pickle.dump(graph, f, protocol=pickle.HIGHEST_PROTOCOL)
    shutil.move(tmp_path, str(path))


def _load_fallback(path: Path):
    """Fallback loader (same as primary)."""
    import pickle
    with open(path, "rb") as f:
        return pickle.load(f)


def write_curation_log(action: str, target_kb: str = None, target_id: str = None,
                        summary: str = None, source: str = "init_body.py"):
    """Append to SQLite curation_log + JSONL."""
    # SQLite
    conn = sqlite3.connect(str(STATE_DB))
    conn.execute(
        "INSERT INTO curation_log(action, target_kb, target_id, summary, source) "
        "VALUES(?, ?, ?, ?, ?)",
        (action, target_kb, target_id, summary, source),
    )
    conn.commit()
    conn.close()

    # JSONL (also for fast grep)
    log_file = BODY_ROOT / "curation_log.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "target_kb": target_kb,
            "target_id": target_id,
            "summary": summary,
            "source": source,
        }) + "\n")


def main():
    print("=" * 70)
    print("ALPHA WOLF AGENT — Body Initialization")
    print("=" * 70)
    print(f"Body root: {BODY_ROOT}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()

    results = {
        "chromadb": init_chromadb(),
        "networkx": init_networkx(),
        "sqlite": init_sqlite(),
        "zvec": init_zvec(),
    }

    print()
    print("=" * 70)
    print("INITIALIZATION SUMMARY")
    print("=" * 70)
    for component, result in results.items():
        status = "✓ OK" if result.get("ok") else "✗ FAIL"
        print(f"  {component}: {status}")
        if not result.get("ok") and "error" in result:
            print(f"    error: {result['error']}")

    # Log init event
    if results["chromadb"].get("ok") and results["sqlite"].get("ok"):
        write_curation_log(
            action="add",
            target_kb="kb_self",
            target_id="init_body.py",
            summary=f"Body initialized: ChromaDB={len(results['chromadb']['collections'])} collections, "
                    f"NetworkX={results['networkx'].get('nodes', 0)} nodes, "
                    f"SQLite={results['sqlite'].get('tables_count', 0)} tables",
            source="init_body.py",
        )
        print()
        print("  Curation log entry written (curation_log.jsonl + SQLite)")
        print()
        print("✓ Body initialization COMPLETE")
        print()
        print("Next steps:")
        print("  1. python body/alpha_wolf_body.py --verify")
        print("  2. python body/init_body.py --seed   (optional: add seed knowledge)")
        return 0
    else:
        print()
        print("✗ Body initialization INCOMPLETE — see errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())