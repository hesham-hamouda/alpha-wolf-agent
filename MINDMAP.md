# 🧠 Alpha Wolf Agent — Project Mind Map

> خريطة ذهنية شاملة للمشروع — أين هو الآن، كيف وصلنا، إلى أين يتجه.
> آخر تحديث: 2026-10-13 (عصر الموجه التلقائي — 58 نموذجاً بالقائمة).

## 🎯 Project Mission

**Alpha Wolf Agent** = AI agent محلي يعمل ساعات طويلة، واعٍ بذاته، يبدّل نماذجه تلقائياً.
- **الغرض:** مساعد شخصي للقائد هشام، يعمل بدون إنترنت، يحتفظ بالذاكرة، يمكنه استخدام أدوات.
- **الفلسفة:** "wolf" = mistake_hunting, goal_persistence, tenacity, deep_thinking, resourceful, self_aware, reinforcement_learning.
- **العقل المخدوم (2026-10-12، TRAINING SUSPENDED):** سلسلة Ollama محلية — سبارك الأساسي (`maternion/spark-x2.5:4b-q4_K_M`)، لا تدريب ولا أوزان مدربة تُخدم.

---

## 🏗️ Current Architecture (October 2026)

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Streamlit)                       │
│  http://127.0.0.1:8501                                       │
│  - 7 pages: Chat, Agent, Memory, Tools, Projects, Health,     │
│    Inspector                                                 │
│  - Model picker: تلقائي (افتراضي) + 58 نموذجاً (حي من /v1/models) │
│  - WCAG 2.1 AA + Mobile Responsive                           │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP/SSE
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI :8001)                    │
│  - 29 tools + 39 skills (مهارة حقيقية لكل قسم، 16 جديدة)      │
│  - قائمة 58 نموذجاً: 6 أولاما مباشرة + 52 تخصصياً بمهاراتهم   │
│  - بديل شات تلقائي (7 مواقع + البث) + رؤية تلقائية + تقطير    │
│  - الجسر: backend/agent/model_router_bridge.py                │
│  - العداء المشترك: backend/agent/hf_runner.py                 │
└─────────────────────────────────────────────────────────────┘
                    │ HTTP                  │ Transformers/HF
                    ▼                       ▼  (D: أوزان أصلية)
┌────────────────────────┐  ┌──────────────────────────────────┐
│   OLLAMA (:11434)       │  │  63 نموذجاً / 21 قسماً (BUILD)   │
│  سبارك ⭐ الأساسي       │  │  شات/رؤية/OCR/صور/صوت/برمجة/      │
│  + بدائل+qwen2.5vl+     │  │  رياضيات/حيوي/أرضي/مناخ...       │
│  moondream + صغار       │  │  شاندرا أول OCR · توربو للصور    │
└────────────────────────┘  └──────────────────────────────────┘
                              │ ComfyUI :8188 (torbo int8 حي ✓)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    BODY (Knowledge Storage)                   │
│  - 4-layer memory: short-term, long-term, episodic, semantic │
│  - ChromaDB: 4905 chunks عبر 14 مجموعة (RAG حي)               │
│  - NetworkX: knowledge graph (17 nodes, 7 edges)              │
│  - SQLite: 16 tables + تقطير تلقائي لكل دور ناجح              │
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
│   │   ├── skills_manager.py     # Skill registry (39 مهارة حية)
│   │   ├── skill_forge.py        # Skill installation
│   │   ├── model_router_bridge.py # جسر التوجيه: بديل+أقسام+تقطير (2026-10-13)
│   │   ├── hf_runner.py          # عداء متخصصي HF المشترك (2026-10-13)
│   │   └── capabilities.py       # Live capability map
│   └── skills/                   # Skill implementations (39: 16 للأقسام 2026-10-13)
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
- **Base (2026-10-12):** سلسلة Ollama محلية — سبارك الأساسي (لا تدريب يُخدم)
- **Adapter:** لا يُخدم حالياً (أوزان LoRA على القرص فقط — TRAINING SUSPENDED)

### Models & Skills (2026-10-13)
- **قائمة الدردشة:** 58 نموذجاً (6 أولاما مباشرة + 52 تخصصياً بمهاراتهم) + وضع تلقائي
- **الأقسام:** 21 قسماً / 63 نموذجاً — مهارة حقيقية لكل قسم (39 مهارة مسجلة)
- **مثبت حياً:** توربو صور (منارة PNG)، حلقة صوتية (تفريغ مطابق)، بروتين (1.0)، رياضيات (396)
- **معلق بصدق:** عدّاء شاندرا (حارس 240s) + 9 بطاقات انتظار

### Training Data
- **الحالة:** مجمّدة (TRAINING SUSPENDED 2026-10-12) — الدولاب يصدّر ويُنقّي فقط

### Tools Current
- **Total:** 29 tools
- **Categories:** compute (3), file (3), web (2), perception (1), knowledge (3), memory (3+4), planning (3), self_extension (4), self_repair (1), self_awareness (4)

---

## 🎯 Active Goals (recurring)

### عصر الموجه التلقائي (مكتمل 2026-10-13)
- **المنجز:** 58 بالقائمة + 21 قسماً + 39 مهارة + بديل/رؤية/تقطير تلقائي + ComfyUI حي
- **Status:** يعمل — مثبت حياً (منارة، صوت مطابق، بروتين 1.0، رياضيات 396)

### المعلق بصدق
- **عدّاء شاندرا:** تحميل الأوزان يعلق بصمت (4 محاولات) — حارس 240s يمنع تعليق الدور
- **9 بطاقات انتظار:** توجه للبديل الجاهز (Florence/dinov2/sam/GOT/nougat/bf16/BiomedCLIP/video)
- **سياق سبارك:** محفوظ 8192 بأمر القائد — التكبير فقط بأمر صريح

### Long-term: Body KB Expansion
- **Description:** Add more knowledge to the body (books, papers, conversations)
- **Goal:** Richer context
- **Status:** Continuous (+ تقطير تلقائي لكل دور ناجح منذ 2026-10-13)

---

## 📊 Quality Metrics (Latest)

| Metric | Value | Date |
|---|---|---|
| Frontend integration | 98.63% | 2026-10-06 |
| Backend pytest (bridge+registry+sections) | 22/22 PASS | 2026-10-13 |
| Capability self-test | PASS (كان أحمر: طلب منفذاً متقاعداً) | 2026-10-13 |
| Quick checks | 8/9 (التكرار المزدوج بأولاما مؤجل بدليل) | 2026-10-13 |
| Engine tests (router+sections) | 52/52 PASS | 2026-10-13 |
| Skill self-tests | 14/14 PASS | 2026-10-13 |
| Chat-list models | 58 (6+52) | 2026-10-13 |
| Registered skills | 39 (16 للأقسام) | 2026-10-13 |
| RAG index | 4905 chunks / 14 collections | 2026-10-13 |
| Frontend WCAG | 2.1 AA | 2026-10-06 |
| Active tools | 29 | 2026-10-06 |

---

## 🔗 External References

- **TRACK_LOG.md** (full round-by-round log): `C:\Users\Hesham\.config\opencode\skills\alpha-wolf-tracker\TRACK_LOG.md`
- **PROJECT_LOG.md** (project changes log): `E:\Projects...\Alpha Wolf Agent\PROJECT_LOG.md`
- **PROJECT_PLAN.md** (long-term plan): `E:\Projects...\Alpha Wolf Agent\PROJECT_PLAN.md`

---

## 📦 Git Status (2026-10-13)

- **Repo:** Initialized on `master` branch
- **Remote:** `https://github.com/hesham-hamouda/alpha-wolf-agent.git`
- **Note:** شجرة العمل تحمل تعديلات متراكمة (قديمة + توصيل الموجه) — تُراجع قبل أي commit