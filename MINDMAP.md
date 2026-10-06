# 🧠 Alpha Wolf Agent — Project Mind Map

> خريطة ذهنية شاملة للمشروع — أين هو الآن، كيف وصلنا، إلى أين يتجه.

## 🎯 Project Mission

**Alpha Wolf Agent** = AI agent محلي (offline) مبني على Llama-3.1-8B + LoRA adapter.
- **الغرض:** مساعد شخصي للقائد هشام، يعمل بدون إنترنت، يحتفظ بالذاكرة، يمكنه استخدام أدوات.
- **الفلسفة:** "wolf" = mistake_hunting, goal_persistence, tenacity, deep_thinking, resourceful, self_aware, reinforcement_learning.

---

## 🏗️ Current Architecture (October 2026)

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Streamlit)                       │
│  http://127.0.0.1:8501                                       │
│  - 7 pages: Chat, Agent, Memory, Tools, Projects, Health,     │
│    Inspector                                                 │
│  - 67 APIClient methods (98.63% backend integration)         │
│  - WCAG 2.1 AA + Mobile Responsive                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼  HTTP/SSE
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI :8001)                    │
│  - 73 endpoints                                              │
│  - 25+ tools (file, code, web, memory, body, self-extension) │
│  - 29+ tool implementations (TOOL_SPECS)                      │
│  - Force-execute detectors + Sanity checks                    │
│  - Retry + Cache + Checkpoints + Compression                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼  HTTP
┌─────────────────────────────────────────────────────────────┐
│                    OLLAMA (:11434)                            │
│  Models installed:                                           │
│  - alpha-wolf-agent-v8 (4.9 GB, Wolf merged) ✅              │
│  - llama3.1:8b (4.9 GB, BASE — for re-training fallback)    │
│  - nomic-embed-text (274 MB, embeddings)                      │
│  - moondream, qwen2.5vl, qwen3 (vision/variants)              │
│  ❌ REMOVED: alpha-wolf-agent (broken), gemma4 (unused)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    BODY (Knowledge Storage)                   │
│  - 4-layer memory: short-term, long-term, episodic, semantic │
│  - ChromaDB: 3218 chunks in `alpha_wolf_project_index`       │
│  - NetworkX: knowledge graph (entities + relations)          │
│  - SQLite: 16 tables (episodes, goals, mistakes, etc.)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Map

```
E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\
├── backend/                      # FastAPI backend
│   ├── main.py                  # 73 endpoints, admin auth, route aliases
│   ├── run_server.py             # Entry point
│   ├── agent/
│   │   ├── streaming.py         # SSE + system prompt + force-execute
│   │   ├── tools.py              # 29+ tool implementations + sanitizers
│   │   ├── tool_calling.py       # Intent detectors + decide_forced_calls
│   │   ├── rag.py                # ChromaDB + max_total_chars=4000
│   │   ├── memory.py             # Conversations + checkpoints
│   │   ├── auto_skill_forge.py   # Self-extension (NEW R26)
│   │   ├── self_evaluator.py     # Quality scoring (NEW R26)
│   │   ├── training_data_flywheel.py  # JSONL export (NEW R26)
│   │   ├── auto_lora_trainer.py  # SCAFFOLD (NEW R26)
│   │   ├── memory_layers.py      # 4-layer unified recall (NEW R26)
│   │   ├── code_exec.py          # Python execution + safety check
│   │   ├── web_search.py         # Google News + Bing + Wiki chain
│   │   ├── skills_manager.py     # Skill registry
│   │   ├── skill_forge.py        # Skill installation
│   │   └── capabilities.py       # Live capability map
│   └── skills/                   # Skill implementations
│
├── frontend/                     # Streamlit UI
│   ├── streamlit_preview.py      # Main UI (7 pages + P3 sections)
│   ├── utils.py                  # APIClient (67 methods)
│   ├── styles.css                # WCAG 2.1 AA + responsive
│   ├── views/                    # Page renderers
│   │   ├── chat.py
│   │   ├── agent.py
│   │   ├── memory_inspector.py
│   │   ├── tools_registry.py
│   │   ├── project_awareness.py
│   │   └── body_health.py
│   └── run_streamlit.py
│
├── body/                         # Persistent memory
│   ├── alpha_wolf_body.py        # Body wrapper (FK fix in R33)
│   ├── init_body.py              # Schema bootstrap
│   ├── knowledge_graph/          # ChromaDB + NetworkX
│   └── memory/                   # state.db (SQLite)
│
├── docs/                         # Documentation
│   ├── DATA_MINDMAP.html         # Body architecture (moved R23)
│   └── ...
│
├── data/                         # Configuration (modelf)
│   ├── Alpha_Wolf_Modelfile      # Ollama template
│   └── training_data/            # Generated training JSONL
│
├── mcp_agent_tester/             # MCP test suite (13 tests)
│
├── scripts/                      # Development scripts
│   ├── train_v*.py               # LoRA training scripts
│   ├── merge_v*.py               # Merge attempts
│   ├── eval_v*.py                # Evaluation
│   └── ...
│
├── Alpha_Wolf_Launcher.bat        # One-click desktop launcher (CRLF fixed)
├── Alpha_Wolf_Stop.bat            # Graceful stop
│
├── logs/                         # Runtime logs + review reports
│   └── review_2026-10-06/        # 55-scenario review
│
├── CHANGELOG.md                  # Round-by-round changelog (NEW)
├── MINDMAP.md                    # This file (NEW)
├── README.md                     # Project overview (likely exists)
├── .gitignore                    # Python + logs + .bak ignored (NEW)
└── .gitattributes                # CRLF for .bat files (NEW)
```

---

## 🧠 Knowledge Map

### Wolf Identity
- **Name:** Alpha Wolf Agent
- **Traits (7):** mistake_hunting, goal_persistence, tenacity, deep_thinking, resourceful, self_aware, reinforcement_learning
- **Creator:** القائد هشام
- **Base:** Llama-3.1-8B-Instruct
- **Adapter:** v8_wolf (rank=16, 582 examples, 164 MB)

### Training Data
- **v0_identity** → v8_wolf progression (582 → 582 → ... → final)
- **Quality:** Acceptable (Wolf is not solid under adversarial — needs expansion to 200+)

### Tools Current
- **Total:** 29+ tools
- **Categories:** compute (3), file (3), web (2), perception (1), knowledge (3), memory (3+4), planning (3), self_extension (4), self_repair (1), self_awareness (4)

---

## 🎯 Active Goals (recurring)

### Phase 36: Training Expansion
- **Description:** Add 50+ adversarial identity-preservation training pairs
- **Goal:** Grade B → A
- **Status:** Pending القائد approval
- **Estimated effort:** 1 day

### Phase 37: Arabic Fine-tuning
- **Description:** Improve Arabic grammar in outputs
- **Goal:** Arabic conversational fluency
- **Status:** Pending القائد approval
- **Estimated effort:** 2 days

### Phase 38: Performance Tuning
- **Description:** Latency < 3s for typical prompts
- **Goal:** Speed
- **Status:** Pending القائد approval
- **Estimated effort:** 1 day

### Long-term: Body KB Expansion
- **Description:** Add more knowledge to the body (books, papers, conversations)
- **Goal:** Richer context
- **Status:** Continuous

---

## 📊 Quality Metrics (Latest)

| Metric | Value | Date |
|---|---|---|
| Frontend integration | 98.63% | 2026-10-06 |
| Wolf v8 grade | B (3/4 quick fixes) | 2026-10-06 |
| Self-tests | 25/25 PASS | 2026-09-28 |
| MCP test suite | 21/21 PASS | 2026-09-27 |
| Frontend WCAG | 2.1 AA | 2026-10-06 |
| Total endpoints | 73 | 2026-10-06 |
| Active tools | 29+ | 2026-10-06 |

---

## 🔗 External References

- **TRACK_LOG.md** (full round-by-round log): `C:\Users\Hesham\.config\opencode\skills\alpha-wolf-tracker\TRACK_LOG.md`
- **PROJECT_LOG.md** (project changes log): `E:\Projects...\Alpha Wolf Agent\PROJECT_LOG.md`
- **PROJECT_PLAN.md** (long-term plan): `E:\Projects...\Alpha Wolf Agent\PROJECT_PLAN.md`

---

## 📦 Git Status (2026-10-06)

- **Repo:** Initialized on `master` branch
- **Remote:** `https://github.com/hesham-hamouda/alpha-wolf-agent.git`
- **Existing commits:** 8 (before this commit batch)
- **Working tree changes:** 170 files (modified/deleted/new)
- **Strategy:** Atomic commits grouped by Round (R32 → R35 + docs)