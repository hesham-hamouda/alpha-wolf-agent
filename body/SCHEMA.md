# 🐺 Alpha Wolf Body — Schema (Self-Documenting Blueprint)

> **Auto-generated** | Last update: 2026-09-25 | **Iron Law #36 (5-Layer Save)** | **Phase 11+ v3.0**

This file is the **canonical reference** for Alpha Wolf Agent's body infrastructure. It explains:
- **WHAT** is stored (the data)
- **WHY** each piece exists (the rationale)
- **HOW** it connects (the relationships)
- **WHEN** to use each method (the use cases)

For operators: see [README.md](README.md) | For gaps: see [GAPS_AND_PRIORITIES.md](GAPS_AND_PRIORITIES.md) | For mind map: see [DATA_MINDMAP.html](../DATA_MINDMAP.html)

---

## 🎯 Why a "Body"?

> Per Quхائд's verbatim directive (2026-09-23):
> *"ده نموذج ذكاء بننشئه اه ولكن هايكون طفره. فكرته انه متكامل مع جسد الوكيل الذى يعيش فيه وياخذ نفس اسمه... الفرق بينه وبين نماذج الذكاء العاديه ان نموذج الذكاء الاساسى حجمه ليس كبير ولكن امتداده قواعد البيانانات والذاكره وخلافه التى ستكون داخل المجلد الذى سيعيش فيه"*

The body is the **persistent memory + knowledge extension** that compensates for the small (8B) model's limited weights. It's where Alpha Wolf:
- Stores everything it learns (mistakes, reflections, episodic memories)
- Retrieves knowledge on demand (semantic + graph + structured)
- Tracks goals and progress across sessions
- Self-curates from external sources (HuggingFace)

**Without a body, the model forgets everything after each session. With a body, Alpha Wolf grows.**

---

## 🏗️ Architecture: 4-Layer DB Stack

| Layer | Tech | Purpose | Why this choice |
|-------|------|---------|-----------------|
| **L1. Vectors** | ChromaDB 1.4.0 | Semantic search across all knowledge | Already installed, proven, HNSW index fast (~30-50ms) |
| **L2. Graph** | NetworkX 3.6.1 | Typed knowledge graph (entities + relations) | Replaces schema-free `edges.json` from Phase 6 with real graph queries |
| **L3. Structured** | SQLite (stdlib + sqlite-utils) | Goals, mistakes, episodes, projects, sessions, reflections, tools | ACID guarantees, FK constraints, simple file backup |
| **L4. Backup** | zvec 0.7.0 | Cold storage for old memories (offline-capable) | Complements ChromaDB, on-demand init |

**Why hybrid?**
- ChromaDB is great for vectors but lacks structured queries
- NetworkX is great for graph but lacks full-text search
- SQLite is great for tables but lacks semantic search
- Combining = best of all worlds (AGORA paper pattern)

---

## 📁 Directory Structure

```
body/
├── alpha_wolf_body.py           # ← Main wrapper class (single entry point)
├── init_body.py                 # ← Initialization script (run once)
├── SCHEMA.md                    # ← THIS FILE (self-documenting)
├── README.md                    # ← Operator manual
├── curation_log.jsonl           # ← Append-only audit log (every add/update/delete)
│
├── knowledge_graph/
│   ├── chromadb/                # ChromaDB persistence (12 collections)
│   │   └── chroma.sqlite3
│   ├── networkx/
│   │   ├── graph.pickle         # ← Canonical typed graph
│   │   ├── schema.json          # ← Node/edge type registry
│   │   └── backups/             # ← Daily snapshots (Iron Law #14)
│   └── sync_log.jsonl           # NetworkX ↔ SQLite entity sync log
│
├── memory/
│   ├── state.db                 # ← SQLite (11 tables, ACID)
│   ├── embeddings/
│   │   └── zvec/                # zvec backup layer (on-demand init)
│   ├── episodic/                # Per-day episodic logs (YYYY-MM-DD.jsonl)
│   └── backups/                 # Daily *.db snapshots
│
├── intake/
│   ├── staging/                 # HuggingFace ingestion temp
│   ├── ingest_log.jsonl
│   └── quarantine/              # Rejected items (Iron Law #7 anti-contamination)
│
├── backups/                     # Full body snapshots (YYYY-MM-DD_HHMMSS/)
└── logs/                        # Operation logs
```

**Iron Law #42:** All body files live in workspace (`E:\Projects...\Alpha Wolf Agent\body\`), NEVER in `E:\Agents\The Expert Team\` (body).

---

## 🗄️ ChromaDB Collections (12 total)

Per AGORA-inspired multi-DB network:

| Collection | Domain | Use Case |
|-----------|--------|----------|
| `kb_self` | Alpha Wolf's identity + memories | Self-summary, identity verification |
| `kb_science_marine` | Marine biology (oysters, algae, coral) | Domain expertise retrieval |
| `kb_science_agriculture` | Crops, yield, fertilizers | Domain expertise retrieval |
| `kb_science_chemistry` | Molecules, drugs, reactions | Domain expertise retrieval |
| `kb_science_climate` | ClimateBERT, time-series | Domain expertise retrieval |
| `kb_science_proteomics` | ESM2, ProtBERT, DNABERT | Domain expertise retrieval |
| `kb_vision` | Florence-2, BiomedCLIP, SAM | Vision model metadata |
| `kb_code` | Code patterns (CodeAlpaca distilled) | Code retrieval |
| `kb_reasoning` | Reasoning patterns (Bespoke-Stratos) | Reasoning examples |
| `kb_mistakes` | Mistakes log + lessons (Wolf Trait) | Learning from failures |
| `kb_goals` | Active goals + progress (Wolf Trait) | Goal tracking |
| `kb_tools` | Tool registry + invocation patterns | Tool discovery |

**Metadata schema** (per document):
```python
{
    "evidence_score": float,    # 0-1, AGORA-style confidence
    "citation_count": int,      # How many times cited
    "reuse_count": int,         # How many times retrieved
    "last_used": ISO8601,       # For decay/cleanup
    "source_agent": str,        # "alpha-wolf" | "user" | "hf-fetcher"
    "domain": str,              # Optional domain tag
    "confidence": float,        # Optional self-rated confidence
}
```

---

## 🕸️ NetworkX — Typed Knowledge Graph

### Node Types (10)

| Type | Required Fields | Optional Fields | Example |
|------|-----------------|-----------------|---------|
| `Concept` | name | domain, description | "Alpha Wolf Agent" |
| `Tool` | name, invocation | version, description | "alpha_wolf_search" |
| `Person` | name | role, email | "القائد هشام" |
| `Place` | name | kind | "local-machine" |
| `Dataset` | name, source | size, license, path | "ultrachat_50k" |
| `Mistake` | context, lesson | severity | (mirrors mistakes table) |
| `Goal` | title, status | priority, deadline | (mirrors goals table) |
| `Reflection` | trigger, insight | confidence | (mirrors reflections table) |
| `Episode` | summary | importance | (mirrors episodes table) |
| `KB` | name | domain | "kb_self" |

### Edge Types (11)

| Type | Direction | Weight | Example |
|------|-----------|--------|---------|
| `trains_on` | Goal → Dataset | — | "Alpha Wolf Agent" → "ultrachat_50k" |
| `depends_on` | any → any | — | "Chainlit" → "FastAPI" |
| `contradicts` | Claim → Claim | — | (rare) |
| `supports` | Evidence → Claim | — | (rare) |
| `replaces` | any → any | — | "V2" → "V1" |
| `similar_to` | any → any | 0-1 (cosine) | "Mistake Hunter" → "Reflection" |
| `knows_about` | Agent/Concept → any | — | "Alpha Wolf" → "Wolf Traits" |
| `learned_from` | Mistake → Episode | — | (track cause-effect) |
| `applies_to` | Tool → Goal | — | "search_kb" → "Build body infrastructure" |
| `blocks` | Mistake → Goal | — | (preventive warnings) |
| `achieves` | Episode → Goal | — | (milestone tracking) |

**Why typed?** Untyped edges (Phase 6 plan = `edges.json`) = no queries. Typed edges = can ask "what tools apply to goal X?" in O(graph_traversal).

---

## 🗃️ SQLite Schema (13 tables — updated Phase 11+ v3.1)

### 1. `projects` — Active project tracker
**Purpose:** Track what project Alpha Wolf is currently working on (one at a time).

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,           -- e.g., "project-alpha-wolf-agent-v1"
    name TEXT NOT NULL UNIQUE,     -- "Alpha Wolf Agent"
    phase TEXT NOT NULL,           -- "Phase 11+ v3.0 - Body Infrastructure"
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    iron_law_ref TEXT,             -- e.g., "Iron Law #44"
    metadata TEXT                  -- JSON blob for flexibility
);
```

**Why:** Allows Alpha Wolf to resume context after session restart.

### 2. `episodes` — Episodic memory (Wolf Trait: Self-Aware)
**Purpose:** Record every meaningful occurrence (interaction, mistake, learning, etc.)

```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL,
    duration_ms INTEGER,
    trigger_type TEXT CHECK (trigger_type IN ('user_task', 'cron', 'self_reflection', 'fetch_and_learn', 'mistake_recovery')),
    content TEXT NOT NULL,
    summary TEXT,
    importance INTEGER CHECK (importance BETWEEN 1 AND 10),
    embedding_id TEXT,             -- FK to embeddings.doc_id (zvec/ChromaDB)
    session_id TEXT,
    created_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ          -- soft delete (Iron Law #21)
);
```

**Indexes:**
- `idx_episodes_trigger ON (trigger_type, occurred_at DESC) WHERE deleted_at IS NULL`
- `idx_episodes_importance ON (importance DESC, occurred_at DESC) WHERE deleted_at IS NULL`
- `idx_episodes_session ON (session_id) WHERE session_id IS NOT NULL`

### 3. `goals` — Goal tracking (Wolf Trait: Goal Persistence)
```sql
CREATE TABLE goals (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES goals(id) ON DELETE SET NULL,  -- nested goals
    title TEXT NOT NULL,
    description TEXT,
    status TEXT CHECK (status IN ('open', 'active', 'blocked', 'done', 'abandoned')),
    priority INTEGER CHECK (priority BETWEEN 1 AND 10),
    deadline TIMESTAMPTZ,
    progress_pct REAL CHECK (progress_pct BETWEEN 0 AND 100),
    created_at, updated_at, completed_at, deleted_at
);
```

**Why:** Track what Alpha Wolf is working toward across sessions.

### 4. `mistakes` — Mistake log (Wolf Trait: Mistake Hunter)
```sql
CREATE TABLE mistakes (
    id TEXT PRIMARY KEY,
    episode_id TEXT REFERENCES episodes(id) ON DELETE SET NULL,
    context TEXT NOT NULL,
    what_went_wrong TEXT NOT NULL,
    root_cause TEXT,
    lesson TEXT NOT NULL,            -- Iron Law #33: lessons → code guardrails
    prevention TEXT,
    severity INTEGER CHECK (severity BETWEEN 1 AND 10),
    recurrence_count INTEGER DEFAULT 0,
    related_entity_id TEXT,          -- FK to entities.id (graph node)
    created_at, deleted_at
);
```

**Why:** Alpha Wolf explicitly hunts mistakes (not hides them). This table is the **source of truth** for what NOT to repeat.

### 5. `reflections` — Deep insights (Wolf Trait: Reinforcement Learning)
```sql
CREATE TABLE reflections (
    id TEXT PRIMARY KEY,
    episode_id TEXT REFERENCES episodes(id),
    trigger TEXT NOT NULL,
    insight TEXT NOT NULL,
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),
    applied_count INTEGER DEFAULT 0,  -- incremented when reflection is used
    created_at, deleted_at
);
```

**Why:** "Failure is data" — each reflection captures a learning moment.

### 6. `tools` — Tool registry (Wolf Trait: Resourceful)
```sql
CREATE TABLE tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    invocation TEXT NOT NULL,        -- function signature or JSON schema
    description TEXT,
    category TEXT,
    enabled INTEGER DEFAULT 1,
    invocation_count INTEGER DEFAULT 0,
    last_invoked_at TIMESTAMPTZ,
    created_at
);
```

**Why:** Alpha Wolf needs to know what tools it can call (function-calling).

### 7. `entities` — Graph node mirror
```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    name TEXT NOT NULL,
    attributes TEXT,                 -- JSON blob
    graph_synced_at TIMESTAMPTZ,
    created_at, deleted_at,
    UNIQUE(node_type, name)
);
```

**Why:** Allows SQL queries on graph nodes (e.g., "find all Tools in category X").

### 8. `relations` — Graph edge mirror
```sql
CREATE TABLE relations (
    id TEXT PRIMARY KEY,
    source_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    target_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0 CHECK (weight BETWEEN 0 AND 1),
    attributes TEXT,
    graph_synced_at TIMESTAMPTZ,
    created_at,
    UNIQUE(source_id, target_id, edge_type)
);
```

**Why:** Allows SQL queries on graph edges (e.g., "what Goals depend on Dataset X?").

### 9. `sessions` — Session grouping
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    started_at, ended_at,
    model TEXT,                      -- e.g., "minimax-330/minimax-M3"
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    metadata TEXT
);
```

**Why:** Track usage statistics (tokens, duration) per session.

### 10. `curation_log` — Audit trail (Iron Law #36 — 5-Layer Save)
```sql
CREATE TABLE curation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    action TEXT CHECK (action IN ('add', 'update', 'delete', 'fetch_and_learn')),
    target_kb TEXT,
    target_id TEXT,
    summary TEXT,
    source TEXT
);
```

**Why:** Every modification is logged for auditability and rollback.

### 11. `sqlite_sequence` — Auto-managed
Auto-created by SQLite for AUTOINCREMENT columns.

### 12. `datasets` — Dataset inventory (Phase 11+ v3.1 — NEW)

**Purpose:** Track every dataset ingested via the Body Ingestion Pipeline. Enables "Format Translation SFT" — Alpha Wolf understands any dataset without retraining.

```sql
CREATE TABLE datasets (
    id TEXT PRIMARY KEY,                          -- UUID
    name TEXT NOT NULL,                           -- "ultrachat_50k.jsonl"
    source TEXT NOT NULL,                         -- "local" | "huggingface" | "url"
    repo_id TEXT,                                 -- HF repo_id (e.g., "HuggingFaceH4/ultrachat_200k")
    target_kb TEXT NOT NULL,                      -- "kb_code", "kb_science_marine", etc.
    format_fingerprint TEXT NOT NULL,             -- JSON blob (detected schema + quality)
    quality_score REAL,                           -- 0-1 from FormatDetector
    license TEXT,                                 -- "MIT", "Apache-2.0", etc.
    size_bytes INTEGER,
    rows_total INTEGER,                           -- Estimated row count
    rows_indexed INTEGER,                         -- Actually indexed in ChromaDB
    status TEXT DEFAULT 'staged' CHECK (status IN ('staged','ingested','quarantined')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    ingested_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,                       -- soft delete (Iron Law #21)
    UNIQUE(name, source, repo_id)
);
CREATE INDEX idx_datasets_status ON datasets(status);
CREATE INDEX idx_datasets_target_kb ON datasets(target_kb);
```

**Why:** Enables self-curation. New datasets auto-ingested (zero retraining). Blacklisted datasets quarantined (Iron Law #7).

### 13. `quality_metrics` — Per-dataset quality tracking (Phase 11+ v3.1 — NEW)

**Purpose:** Track quality metrics over time per dataset (drift detection).

```sql
CREATE TABLE quality_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT REFERENCES datasets(id) ON DELETE SET NULL,
    ts TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metric_name TEXT NOT NULL,                   -- "duplicate_rate", "missing_rate"
    metric_value REAL,
    notes TEXT
);
CREATE INDEX idx_quality_dataset_ts ON quality_metrics(dataset_id, ts);
```

**Why:** Track quality drift over time. If a dataset's quality degrades (e.g., new entries are worse), trigger re-evaluation.

---

## 🐺 Wolf Traits → Body Methods Mapping

| Wolf Trait | Method(s) | What it does |
|-----------|-----------|--------------|
| **Mistake Hunter** | `log_mistake()`, `recall_mistakes()` | Logs every failure with context + lesson |
| **Goal Persistence** | `track_goal()`, `update_goal_status()`, `recall_goals()` | Tracks goals across sessions |
| **Tenacity** | (via `reflections.applied_count`) | Counts how often a reflection is reused |
| **Deep Thinking** | `reflect()`, `recall_reflections()` | Records insights with confidence scores |
| **Resourceful** | `register_tool()`, `list_tools()`, `mark_tool_invoked()` | Tool registry + usage tracking |
| **Self-Aware** | `get_self_summary()`, `health_check()` | Alpha Wolf knows what it knows |
| **Reinforcement Learning** | `reflect()` + `applied_count` tracking | Each reflection counts when applied |

---

## 🔄 Data Flow: How Information Moves

```
User Input
    ↓
FastAPI /v1/chat/completions
    ↓
[body.recall()] injects top-k relevant context from ChromaDB
    ↓
llama.cpp generates response (with body context in system prompt)
    ↓
User sees response in Chainlit UI
    ↓
(parallel) body.remember_episode() logs the interaction
    ↓
(parallel) body.log_mistake() / body.reflect() if applicable
```

**Self-Curation Flow** (when Alpha Wolf wants to learn something new):
```
body.update_kb(content, target_kb="kb_science_marine")
    ↓
ChromaDB.add(documents=[content], metadata={...})
    ↓
curation_log.jsonl + SQLite curation_log (audit)
```

---

## 📊 Iron Law Compliance

| # | Iron Law | How Applied in Body |
|---|----------|---------------------|
| #8 | 3-Expert Consensus | Architecture approved by 3-expert panel |
| #13 | Self-Critical Check | Critical bug found + fixed (nx.DiGraph falsy) |
| #14 | Snapshot Before Edit | `backup()` method creates timestamped snapshots |
| #15 | Verify Before Claim | `health_check()` returns structured dict |
| #17 | User Preferences Override | Local-first, no cloud services |
| #18 | 3-Expert Max Parallel | Parallel expert dispatches in Phase A |
| #19 | New Rules FIRST | N/A for body (governance already complete) |
| #20 | Self-Awareness + Gap Priority | Gap analysis file maintained |
| #21 | NO Deletion | soft delete via `deleted_at` columns |
| #22 | Autonomous Execution | All methods run without user prompts |
| #23 | Arabic Explanation | Arabic comments in code (selective) |
| #25 | Info Sharing + Suggestions | Curation log + memory dispatch |
| #26 | Arabic Response | All user-facing replies in Arabic |
| #27 | Continuous + Obstacle Removal | "DiGraph falsy" bug fixed in same session |
| #28 | Compliance Measurement | Compliance script covers body files |
| #36 | 5-Layer Save | AGORA dispatch + this file + memory + governance |
| #42 | Workspace-Body Separation | Body in `E:\Projects...\`, NOT in `E:\Agents\...` |
| #43 | 6-Line Arabic Explanation | Every recommendation has 6-line summary |
| #44 | Model Development Methodology | 5 Gates applied (Research → Personality → ...) |
| #45 | Training Session Logging | Training log template created |
| #46 | Model Caching & Reuse | Base model cached, NO re-download |
| #7  | Anti-Contamination | Blacklist in `format_detector.py` |
| #9  | Tool/Server Problem | RTX 5060 Ti sm_120 compatibility verified |
| #33 | Lessons → Code | `pickle` import bug fixed in same session |

---

## 🚀 Ingestion Pipeline (Phase 11+ v3.1)

The body now includes a **self-curation pipeline** that enables Alpha Wolf to understand any dataset without retraining.

### `body/intake/format_detector.py`

Auto-detects dataset format, schema, task type, and quality metrics.

**8 Format Categories:**
| # | Category | Detection Key | Example Datasets |
|---|----------|---------------|------------------|
| 1 | Conversational | `messages`, `conversations`, `chat` | UltraChat, OASST, ShareGPT |
| 2 | Instruction | `instruction`, `input`, `output` | Alpaca, Open-Platypus |
| 3 | Tool-Calling | `system`, `chat`, `tools` | glaive, ToolBench |
| 4 | Code | `query`, `answer`, `code` | CodeFeedback, CodeAlpaca |
| 5 | Classification | `text`, `label` | IMDb, MultiNLI |
| 6 | QA | `question`, `answers`, `context` | SQuAD, TriviaQA |
| 7 | Embedding Pairs | `sentence1`, `sentence2`, `score` | AllNLI, STS |
| 8 | Tabular | (CSV/Parquet files) | Titanic, Iris |

**Quality Thresholds:**
- `min_text_length`: 5 chars
- `max_duplicate_rate`: 5%
- `max_missing_rate`: 10%
- `min_quality_score`: 0.6

**Blacklist (Iron Law #7):**
- `wolf_*` patterns
- `ollama/*-text` (Iron Law #17 — no Ollama text LLMs)
- `*-GGUF` (disk cost)
- Datasets > 50GB

### `body/intake/ingestion_pipeline.py`

Full ingestion: detect → quality check → convert canonical → embed + index → register.

**Workflow:**
```python
from body.intake.ingestion_pipeline import IngestionPipeline

pipeline = IngestionPipeline()

# Local file
result = pipeline.ingest(Path("data/ultrachat.jsonl"), target_kb="kb_chat")
print(result["status"])  # "ingested" or "quarantined"

# HuggingFace dataset
result = pipeline.ingest_from_hf("HuggingFaceH4/ultrachat_200k", target_kb="kb_chat")

# Batch
results = pipeline.ingest_batch([Path("a.jsonl"), Path("b.jsonl")], target_kb="kb_chat")
```

**Canonical Format** (for embedding):
```json
{
    "id": "uuid",
    "task_type": "conversational",
    "text": "user: What is Python?\nassistant: A programming language.",
    "metadata": {
        "dataset_name": "ultrachat.jsonl",
        "source": "huggingface",
        "format_type": "jsonl",
        "row_index": 42,
        "ingested_at": "2026-09-25T..."
    }
}
```

### Mix E Training (Format Translation SFT)

Trains Alpha Wolf on **diverse formats** (7-8 datasets) instead of memorization.

| Dataset | Format | % |
|---------|--------|---|
| UltraChat-200k | `{"messages": [...]}` | 25% |
| glaive-function-calling-v2 | `{"system", "chat", "tools"}` | 15% |
| CodeFeedback | `{"query", "answer"}` | 15% |
| Open-Platypus | `{"instruction", "output"}` | 15% |
| OASST | `{"text", "role"}` | 10% |
| OpenHermes-2.5 | `{"conversations": [...]}` | 10% |
| HuggingFaceH4/no_robots | `{"messages": [...]}` | 5% |
| Custom (Marine Biology) | TBD | 5% |

**Why Mix E:** Generalization > Memorization. Alpha Wolf learns to parse ANY format, not memorize specific datasets.

**Combined with Ingestion Pipeline:**
- Train ONCE on Mix E
- Body auto-ingests new datasets via `pipeline.ingest_from_hf()`
- Zero retraining for new datasets
- **"Train once, understand any dataset"** — the طفرة

---

## 🚀 Quick Reference

### Start the body:
```bash
cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
python body/init_body.py                  # First time only
python body/alpha_wolf_body.py --verify    # Health check
python body/alpha_wolf_body.py --demo     # Run all methods
```

### Start the full stack:
```bash
# Terminal 1: llama.cpp (inference)
llama-server -m models/alpha-wolf-Q4_K_M.gguf --ctx-size 500000 --port 8080

# Terminal 2: FastAPI backend
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload

# Terminal 3: Chainlit frontend
chainlit run frontend/app.py --port 8000 --watch

# Terminal 4: Alpha Wolf UI opens at http://localhost:8000
```

### Backup:
```bash
# Via CLI
python body/alpha_wolf_body.py --verify
# Then trigger backup programmatically:
python -c "from body.alpha_wolf_body import AlphaWolfBody; b=AlphaWolfBody(); print(b.backup())"
```

---

## 🔮 Future Extensions

- **Phase 7+:** zvec becomes primary (ChromaDB fallback)
- **Phase 8:** LlamaIndex integration for RAG patterns
- **Phase 9:** ReAct loop training data ingestion (via Quхائд's Mix D phases)
- **Phase 10:** Long-horizon session continuity (sleep mode + wake)

---

**Last update:** 2026-09-25 — Phase 11+ v3.0 — Body Infrastructure Complete
**Total Iron Laws applied:** 21 (out of 45 total)
**Wolf traits tracked:** 7/7
**Body stack:** ChromaDB + NetworkX + SQLite + zvec (4-layer hybrid)
**Confidence:** HIGH (Iron Law #15 — verify before claim)