# 🐺 Alpha Wolf Agent — Body README (Operator Manual)

> **Iron Law #15 (Verify Before Claim)** | **Iron Law #36 (5-Layer Save)** | **Phase 11+ v3.0**

## What is this?

The **body** is Alpha Wolf Agent's persistent memory and knowledge base. It complements the small (8B) model by providing:
- Semantic search across specialized knowledge bases
- Typed knowledge graph (entities + relations)
- Structured memory (goals, mistakes, episodes, reflections)
- Audit trail (every modification logged)

**The body makes the model persistent across sessions. Without it, Alpha Wolf forgets everything on restart.**

---

## 🚀 Quick Start

### 1. Initialize the body (first time only):
```bash
cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
python body/init_body.py
```

This creates:
- 12 ChromaDB collections (one per domain)
- 1 NetworkX typed knowledge graph
- 1 SQLite database with 11 tables
- zvec directory (on-demand init)
- Curation log

### 2. Verify health:
```bash
python body/alpha_wolf_body.py --verify
```

Expected output: JSON with all 4 layers OK.

### 3. Run demo (creates sample data):
```bash
python body/alpha_wolf_body.py --demo
```

This exercises every method (track_goal, log_mistake, reflect, remember_episode, register_tool, update_kb, add_entity, add_relation, recall, backup).

### 4. Get self-summary:
```bash
python body/alpha_wolf_body.py --summary
```

Returns Alpha Wolf's current state (Wolf traits + memory stats).

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│              Alpha Wolf Agent Body (Phase 11+ v3.1)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LAYER 1: Ingestion Pipeline (NEW)                              │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Format Detector  →  Quality Check  →  Blacklist     │      │
│  │  (8 categories)    (min_score=0.6)   (Iron Law #7)  │      │
│  │  ↓                                                  │      │
│  │  Ingestion Pipeline → Canonical Format → Soft Delete │      │
│  │  (HF Hub + local)    (uniform text)   (Iron Law #21)│      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                  │
│  LAYER 2: 4-Layer DB Storage                                   │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐│
│   │   ChromaDB      │  │   NetworkX      │  │   SQLite        ││
│   │  (Vectors)      │  │  (Graph)        │  │  (Structured)   ││
│   │                 │  │                 │  │                 ││
│   │ 12 collections  │  │ 10 node types   │  │ 13 tables       ││
│   │ HNSW index      │  │ 11 edge types   │  │ ACID + FK       ││
│   │ ~30-50ms query  │  │ ~10ms traversal │  │ ~5-20ms query   ││
│   └─────────────────┘  └─────────────────┘  └─────────────────┘│
│            │                    │                    │          │
│            └────────────────────┴────────────────────┘          │
│                              ↓                                  │
│                  ┌─────────────────────────┐                    │
│                  │   AlphaWolfBody Class    │                    │
│                  │  (alpha_wolf_body.py)    │                    │
│                  └─────────────────────────┘                    │
│                              ↓                                  │
│                  ┌─────────────────────────┐                    │
│                  │  FastAPI Backend (8001)  │                    │
│                  │  + llama.cpp (8080)      │                    │
│                  └─────────────────────────┘                    │
│                              ↓                                  │
│                  ┌─────────────────────────┐                    │
│                  │  Chainlit Frontend (8000)│                    │
│                  │  (Quхائд's UI)          │                    │
│                  └─────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📖 Key Concepts

### Wolf Traits → Body Methods

| Wolf Trait | What it does in body |
|-----------|----------------------|
| **Mistake Hunter** | `body.log_mistake(context, what_went_wrong, lesson)` |
| **Goal Persistence** | `body.track_goal(title, priority, deadline)` |
| **Tenacity** | `body.reflect()` + `applied_count` tracking |
| **Deep Thinking** | `body.reflect(trigger, insight, confidence)` |
| **Resourceful** | `body.register_tool(name, invocation)` |
| **Self-Aware** | `body.get_self_summary()` |
| **Reinforcement Learning** | `body.reflect()` with applied_count |

### Storage Layers

1. **Vectors (ChromaDB)** — semantic search ("find similar docs")
2. **Graph (NetworkX)** — relationships ("what tools apply to goal X?")
3. **Structured (SQLite)** — queries ("show active goals")
4. **Backup (zvec)** — cold storage (offline-capable)

### Where data lives

| Data | Location |
|------|----------|
| Vectors | `body/knowledge_graph/chromadb/` |
| Graph | `body/knowledge_graph/networkx/graph.pickle` |
| Structured | `body/memory/state.db` |
| Backups | `body/backups/YYYY-MM-DD_HHMMSS/` |
| Audit log | `body/curation_log.jsonl` |
| **Ingestion** | `body/intake/` (format_detector + ingestion_pipeline) |
| **Datasets registry** | `body/memory/state.db` table `datasets` |
| **Quality metrics** | `body/memory/state.db` table `quality_metrics` |

---

## 🛠️ Common Tasks

### Add a goal:
```python
from body.alpha_wolf_body import AlphaWolfBody

body = AlphaWolfBody()
gid = body.track_goal(
    title="Complete body infrastructure",
    description="Build 4-layer DB stack for Alpha Wolf",
    priority=10,
    deadline="2026-10-01",
)
print(f"Goal tracked: {gid}")
body.close()
```

### Log a mistake:
```python
body.log_mistake(
    context="Initial plan was ChromaDB + edges.json",
    what_went_wrong="edges.json has no graph queries",
    lesson="Need NetworkX typed graph + SQLite structured memory",
    severity=8,
)
```

### Store a reflection:
```python
body.reflect(
    trigger="After 3-Expert deliberation",
    insight="Hybrid stack gives best AGORA fit",
    confidence=0.85,
)
```

### Semantic recall:
```python
results = body.recall("wolf traits personality", kb_filter="kb_self", top_k=5)
for r in results:
    print(f"  - {r['content'][:80]}... (dist={r['distance']:.2f})")
```

### Add to knowledge graph:
```python
wolf_id = body.add_entity("Concept", "Alpha Wolf Agent", {"domain": "AI"})
trait_id = body.add_entity("Concept", "Wolf Traits", {"domain": "personality"})
body.add_relation(wolf_id, trait_id, "knows_about")
```

### Backup the body:
```python
backup_path = body.backup()
print(f"Snapshot saved at: {backup_path}")
```

### Health check:
```python
health = body.health_check()
print(json.dumps(health, indent=2))
```

### Ingest a new dataset (Phase 11+ v3.1):

```python
from body.intake.format_detector import FormatDetector
from body.intake.ingestion_pipeline import IngestionPipeline
from pathlib import Path

# Detect format
detector = FormatDetector()
fp = detector.detect(Path("data/new_dataset.jsonl"))
print(f"Format: {fp['file_format']}, Task: {fp['task_type']}, Quality: {fp['quality']['overall_score']:.2f}")

# Full ingestion
pipeline = IngestionPipeline()
result = pipeline.ingest(Path("data/new_dataset.jsonl"), target_kb="kb_code")
print(f"Status: {result['status']}, Rows: {result.get('rows_indexed', 0)}")

# From HuggingFace
result = pipeline.ingest_from_hf("HuggingFaceH4/ultrachat_200k", target_kb="kb_chat")
print(f"Status: {result['status']}")
```

---

## 🌐 API Endpoints (FastAPI)

Start backend:
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

Then visit http://127.0.0.1:8001/docs for Swagger UI.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/chat/completions` | POST | OpenAI-compatible chat (proxies to llama.cpp) |
| `/v1/recall` | POST | Semantic search across KBs |
| `/v1/memory/episode` | POST/GET | Episodic memory CRUD |
| `/v1/memory/goal` | POST/PATCH/GET | Goal tracking CRUD |
| `/v1/memory/mistake` | POST/GET | Mistake log CRUD |
| `/v1/memory/reflection` | POST | Reflection CRUD |
| `/v1/tools` | POST/GET | Tool registry |
| `/v1/graph/entity` | POST | Add knowledge graph node |
| `/v1/graph/relation` | POST | Add knowledge graph edge |
| `/v1/body/health` | GET | Body health check |
| `/v1/body/backup` | POST | Create backup snapshot |
| `/v1/self/summary` | GET | Alpha Wolf self-summary |

---

## 💬 Frontend UI (Chainlit)

Start frontend:
```bash
chainlit run frontend/app.py --port 8000 --watch
```

Then visit http://localhost:8000.

Features:
- 💬 Chat with Alpha Wolf (sees its thinking steps)
- 📊 Sidebar: model status, body health
- 🎯 Action buttons: list goals, mistakes, tools
- 💾 Backup trigger
- 🌓 Dark/light mode toggle
- ⌨️ Keyboard navigation (WCAG 2.1 AA compliant)

---

## 🔧 Troubleshooting

### Body won't initialize:
```bash
# Check Python version (need 3.12+)
python --version

# Check dependencies
python -c "import chromadb, networkx, sqlite3, zvec; print('OK')"

# Re-run init
python body/init_body.py
```

### Backend not reachable from frontend:
```bash
# Check backend is running
curl http://127.0.0.1:8001/

# Check CORS (should allow localhost:8000)
# Edit backend/main.py if needed
```

### ChromaDB errors:
```bash
# Check ChromaDB version
python -c "import chromadb; print(chromadb.__version__)"

# Reset ChromaDB (warning: loses data)
rm -rf body/knowledge_graph/chromadb/*
python body/init_body.py
```

### Graph nodes not persisting:
```bash
# Check pickle file
ls -la body/knowledge_graph/networkx/graph.pickle

# Check graph manually
python -c "
import pickle
with open('body/knowledge_graph/networkx/graph.pickle', 'rb') as f:
    g = pickle.load(f)
print(f'Nodes: {g.number_of_nodes()}, Edges: {g.number_of_edges()}')
"
```

---

## 📊 Performance Benchmarks

| Operation | Latency (warm) |
|-----------|----------------|
| Vector recall (1k results) | ~50ms |
| Graph traversal (depth=3) | ~10ms |
| SQLite query (10k rows) | ~10ms |
| Backup (full body) | ~5s |
| Health check | ~20ms |

---

## 🛡️ Security Notes

- **No authentication** by default (local-only deployment)
- **No encryption at rest** (body files are plaintext)
- **Add authentication** before exposing backend to network
- **Add encryption** for sensitive knowledge bases
- See `GAPS_AND_PRIORITIES.md` for security recommendations

---

## 🔗 Related Files

- **[SCHEMA.md](SCHEMA.md)** — Detailed schema documentation
- **[GAPS_AND_PRIORITIES.md](GAPS_AND_PRIORITIES.md)** — Critical gaps + priorities
- **[../DATA_MINDMAP.html](../DATA_MINDMAP.html)** — Visual architecture map
- **[../PROJECT_PLAN.md](../PROJECT_PLAN.md)** — Project master plan
- **[../PROJECT_LOG.md](../PROJECT_LOG.md)** — Change log

---

## 📜 Iron Laws Applied

This body was built following **21 Iron Laws** including:
- #8 (3-Expert Consensus) — architecture approved by panel
- #13 (Self-Critical Check) — caught nx.DiGraph falsy bug
- #14 (Snapshot Before Edit) — backups before any edit
- #15 (Verify Before Claim) — health_check() returns structured dict
- #21 (NO Deletion) — soft delete via deleted_at columns
- #42 (Workspace-Body Separation) — body in workspace, NOT in body

**Full list:** see [SCHEMA.md](SCHEMA.md#-iron-law-compliance)

---

## 🤝 For Developers

### Code conventions:
- Type hints everywhere (`from __future__ import annotations`)
- Docstrings (Google style)
- No hardcoded paths — all via `Path(__file__).resolve().parent`
- Iron Law #21: soft delete only (never DELETE)
- Iron Law #14: snapshot before any edit (via `body.backup()`)
- Iron Law #36: every write goes to curation_log

### Adding new methods:
1. Update `SCHEMA.md` first (Iron Law #19 — rules FIRST)
2. Add method to `AlphaWolfBody` class
3. Add corresponding API endpoint to `backend/main.py`
4. Add CLI demo to `alpha_wolf_body.py --demo`
5. Update this README

### Testing:
```bash
# Run health check
python body/alpha_wolf_body.py --verify

# Run demo
python body/alpha_wolf_body.py --demo

# Test backend
curl http://127.0.0.1:8001/v1/body/health
```

---

## 🐺 Contribution to Alpha Wolf

This body is Alpha Wolf Agent's **cognitive extension**. It is:
- ✅ Persistent (survives session restart)
- ✅ Structured (typed graph + ACID tables)
- ✅ Searchable (semantic + graph + SQL)
- ✅ Auditable (every write logged)
- ✅ Self-aware (health_check + self_summary)
- ✅ Wolf-trait-aligned (7 traits mapped to methods)

**Alpha Wolf grows with every interaction. This body is its growth medium.**

---

**Last update:** 2026-09-25 — Phase 11+ v3.0
**Maintained by:** Quхائд هشام + The Expert Team
**License:** MIT