# 🐺 Alpha Wolf Agent — Master Plan (Phase 0.1 — 2026-09-23)

> **Status:** Awaiting Quهائd approval | **Owner:** القائد هشام | **Architect:** Expert Team (Orchestrator synthesis)
> **Path:** `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\`
> **Hard rule:** Single agent — Not a team. Model + Body = unified entity (per Quهائd directive 2026-09-23)

---

## 📜 0. Quهائd's Verbatim Directives (Source of Truth)

> **Vision:** "ده نموذج ذكاء بننشئه اه ولكن هايكون طفره. فكرته انه متكامل مع جسد الوكيل الذى يعيش فيه وياخذ نفس اسمه. الفرق بينه وبين نماذج الذكاء العاديه ان نموذج الذكاء الاساسى حجمه ليس كبير ولكن امتداده قواعد البيانانات والذاكره وخلافه التى ستكون داخل المجلد الذى سيعيش فيه."

> **AGORA-inspired body:** "الاستفاده من اغلب التقنيات الموجوده فى نظام فريق الوكلاء زى اجورا... [https://github.com/yifanzhang-pro/agora]... كشبكه عصبيه ومتنوعه من قواعد البيانات والعلوم المختلفه"

> **No n8n:** "مش عاوز N8N لانه اطار ضعيف للهواه. نحن من هذه اللحظه سنبدا فى استخدام ادوات المحترفين"

> **Storage:** "هذا هو المكان الذى نحتفظ فيه بنماذج الذكاء والمكتبات الكبيره: D:\Intelligence models. ممنوع تجميل نماذج الذكاء او المكتبات الكبيره خارجه"

---

## 🎯 1. Executive Summary (One paragraph)

**Alpha Wolf Agent** = single-agent AI system where:
- **Small base model** (Llama-3.1-8B-Instruct, ~5GB after Q4_K_M) = the neural network core
- **Body folder** (Alpha Wolf Agent folder) = the agent's complete environment
- **Inside the body:** AGORA-inspired network of specialized databases (vector DB + science KBs) forming the agent's long-term memory
- **Knowledge extension** comes from training on already-curated datasets in `D:\Intelligence models` (which contains 60+ specialized models across marine biology, agriculture, chemistry, vision, etc.)
- **No separation** between "agent" and "its knowledge" — model queries body databases as one cognitive organism

This is **not** multi-agent orchestration, **not** LangChain/LlamaIndex RAG-as-service, **not** AGI claim. It's a single LLM that has been trained to **think like a specialist** across multiple scientific domains, **act** through tools (filesystem, vector DBs, APIs), and **persist** across sessions via body-resident databases.

---

## 🧬 2. Philosophy (Why This Design)

| Principle | Implication |
|-----------|-------------|
| **Single agent** | No LangGraph multi-node graphs. No CrewAI role-based teams. No AutoGen speaker chains. |
| **Body-resident knowledge** | Knowledge lives in the same folder as the model binary (AGENTS+model = واحد). |
| **AGORA-inspired network** | Multiple specialized vector DBs (one per scientific domain) connected via knowledge graph edges. |
| **Self-curation** | Alpha Wolf can `UPDATE_BODY_KB` action: query Hugging Face, vet, embed, store — saving into its own body. |
| **Storage discipline** | All models + big libs in `D:\Intelligence models` only. No C: drive pollution. |
| **Professional tooling** | FastAPI, LangServe, uv/poetry, Git, pre-commit. NOT n8n, Zapier-style automation. |

---

## 🏛️ 3. Architecture (Layered View)

```
┌──────────────────────────────────────────────────────────────────────┐
│  Alpha Wolf Agent — Unified Entity  (E:\Projects...\Alpha Wolf Agent) │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  [Layer 0] Model Core                                               │
│    model: Llama-3.1-8B-Instruct-Q4_K_M.gguf        (~5 GB)         │
│    path:  body/model/llama-server.exe                                │
│    serve: http://localhost:8080  (OpenAI-compatible API)             │
│    ctx-size: 500,000  (via RoPE scale 4)                              │
│                                                                       │
│  [Layer 1] Reasoning Engine (Always-on)                             │
│    - <<think>> chain-of-thought                                       │
│    - Persistent memory calls  (UPDATE_BODY_KB, RECALL_BODY_KB)        │
│    - Tool orchestration  (Function Calling format)                    │
│    - Long-horizon ReAct Loop  (Reason → Act → Observe)                │
│                                                                       │
│  [Layer 2] AGORA-Inspired Body (Multi-Vector-DB Network)             │
│    ┌────────────────────────────────────────────────────────────────┐ │
│    │  body/knowledge_graph/chroma_db/                              │ │
│    │   ├── kb_science_marine/    (oysters, algae, coral, fish)    │ │
│    │   ├── kb_science_agriculture/ (crops, yield, fertilizers)    │ │
│    │   ├── kb_science_chemistry/  (molecules, drugs, reactions)   │ │
│    │   ├── kb_science_proteomics/ (ESM2, ProtBERT, DNABERT)       │ │
│    │   ├── kb_science_climate/    (ClimateBERT, time-series)      │ │
│    │   ├── kb_vision/             (Florence-2, BiomedCLIP, SAM)    │ │
│    │   ├── kb_code/               (CodeAlpaca-20k distilled)      │ │
│    │   ├── kb_reasoning/          (Bespoke-Stratos style)         │ │
│    │   ├── kb_self/               (Alpha Wolf's own MEMORIES)    │ │
│    │   └── edges.json              (Knowledge graph edges)        │ │
│    └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  [Layer 3] Self-Curation Pipeline                                    │
│    - Hugging Face fetcher  (when model issues FETCH_AND_LEARN)        │
│    - Local intake  (PDF/CSV drag-in to body/ingestion/)               │
│    - Embedding  (nomic-embed-text or bge-m3 via Ollama)               │
│    - Quality filter  (dedup, relevance scoring)                       │
│    - Auto-embed into proper KB subdirectory                           │
│                                                                       │
│  [Layer 4] Orchestrator  (Replaces n8n — Professional Tools Only)     │
│    - FastAPI server  (uvicorn or granian for production)              │
│    - LangServe (optional, for serving model with FastAPI integration)│
│    - Webhook endpoints: github, gmail, cron-trigger                   │
│    - Action registry: Send email / open PR / deploy / save to KB      │
│    - PG/SQLite for task state (replaces n8n's state machine)          │
│                                                                       │
│  [Layer 5] Long-Horizon Loop                                          │
│    - ReAct cycle: Reason → Act → Observe → Reason → ...               │
│    - Context summarizer at 90% capacity (auto-compact)               │
│    - Death-loop preventer: ESCALATE_TO_HUMAN after 3 consecutive fails│
│    - Sleep mode: idle until next webhook                               │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 4. Verified Hardware & Storage State (Live Read)

| Component | Current State | Notes |
|-----------|---------------|-------|
| **GPU** | RTX 5060 Ti 16GB VRAM | Confirmed (C: would be impossible to fit 11B; 8B is the sweet spot) |
| **RAM** | 32GB available | Will cap WSL2 at 12GB; reserve 20GB for Windows |
| **VRAM usage now** | Verify needed | Likely small; will measure before training |
| **C: drive** | **28.3GB free of 222GB (87% used)** | Critical — protect Windows |
| **D: drive** | 51.5GB free of 465GB (89% used) | Holds D:\Intelligence models; D: is the user's "AI brain" |
| **E: drive** | 110.5GB free of 118GB (7% used) | Workspace target; Alpha Wolf body lives here |
| **F: drive** | 25.4GB free (likely external) | Backup candidate |

### 4.1 Existing D:\Intelligence models\ (Snapshot — 338GB total)

```
D:\Intelligence models\
├── huggingface\    (311.91 GB)
│   ├── datasets\                            (87 GB cached)
│   │   ├── lmms-lab___vq_av2/              (113 GB)  ← VQA dataset
│   │   ├── mandarjoshi___trivia_qa/         (15 GB)  ← Text QA — for reasoning training
│   │   └── merve___vqav2-small/            (3 GB)
│   ├── hub\                                  (87 GB)
│   │   ├── models--Lightricks--LTX-Video/   (25 GB)
│   │   ├── models--Tongyi-MAI--Z-Image-Turbo/  (30 GB)
│   │   └── ... (60+ models)
│   └── models--*\                              (~120 GB)
│       ├── Qwen2.5-0.5B/1.5B-Math/Coder variants
│       ├── SmolLM2-1.7B-Instruct/
│       ├── facebook/esm2_t30, t12, t6 variants (proteins)
│       ├── scibert_scivocab, ClimateBERT, BioBERT, ChemBERTa
│       └── ~50 specialized models (marine, agriculture, vision, OCR, etc.)
├── ollama\                                 (19.46 GB)
│   └── Qwen2.5-0.5B, Qwen2.5-1.5B × 2, Qwen2.5-Coder, Qwen3-4B,
│       qwen2.5vl-7B, gemma4-9.6GB, bge-m3,
│       wolf1-brain, wolf-router           ← !!! duplicates + Anti-Contamination violations
├── torch\                                  (4.11 GB)
├── whisper\                                (2.01 GB)
├── tts\                                    (0.38 GB)  Supertonic 3
└── embeddings_flat\                        (0.53 GB)
```

### 4.2 ⚠️ Found Issues Per Quهائd's Storage Discipline

| # | Issue | Location | Action |
|---|-------|----------|--------|
| 1 | **wolf1-brain:latest (9.6GB) duplicated** | `D:\Intelligence models\ollama\` | **DELETE** (Wolf_Agent pollution — doesn't belong to Alpha Wolf) |
| 2 | **wolf-router:latest (2.5GB) duplicated** | `D:\Intelligence models\ollama\` | **DELETE** (same reason) |
| 3 | **qwen2.5:1.5b + qwen2.5:1.5b-local** | Both in Ollama | **KEEP both** (1.5b-local is Jev Engine customized — intentional, not a duplicate to delete) |
| 4 | Docker daemon NOT running | System service | **START** in Phase 0.1 |
| 5 | Local Ollama cache exists at `C:\Users\Hesham\AppData\Local\Ollama` (0.01GB) | C: drive | **VERIFY** if any models are there — relocate if found |

---

## 🛠️ 5. Stack & Tools (What We Install)

### 5.1 Pre-Installed (verified)
✅ Python 3.12.8 | ✅ Docker 29.4.1 | ✅ Ollama 0.x | ✅ WSL2 10.0 | ✅ Git 2.52 | ✅ Node 24.11

### 5.2 To Install (Phase 0.2)

| Tool | Purpose | Install Method | Justification |
|------|---------|----------------|---------------|
| **uv** (Astral) | Python package manager (replaces pip + venv) | `pip install uv` | 10x faster than pip, atomic lock files, modern standard |
| **Git LFS** | Large file storage (model weights) | `git lfs install` | For GGUF files (>100MB), better than git binaries |
| **VS Code + Python ext** | IDE (if not installed) | `winget install vscode` | Best Python development environment |
| **Windows Terminal** | Better than cmd for PowerShell scripting | `winget install Microsoft.WindowsTerminal` | Tab support, Unicode |
| **ripgrep (rg)** | Fast search (for codebase navigation) | `winget install BurntSushi.ripgrep` | Used by AI tools heavily |

### 5.3 To Install (Phase 1 — Training)

| Tool | Purpose | Install |
|------|---------|---------|
| **NVIDIA CUDA Toolkit 12.x** | GPU compute | `winget install Nvidia.CUDA` |
| **PyTorch with CUDA** | Deep learning (Unsloth depends on this) | `pip install torch --index-url https://download.pytorch.org/whl/cu121` |
| **Unsloth** | Local LLM fine-tuner | Docker pull (skip pip install complexity) |
| **llama.cpp** | Inference engine (RoPE scaling + KV quant) | Build from source or use pre-built Windows binaries |
| **ChromaDB** | Vector database for body knowledge | `pip install chromadb` |
| **LanceDB** | Alternative vector DB (faster for large scale) | `pip install lancedb` |
| **FastAPI** | Web framework for orchestrator | `pip install fastapi uvicorn` |
| **LangChain/LlamaIndex** | Tool orchestration SDKs (optional, use carefully) | `pip install langchain llama-index` |

---

## 📋 6. Storage Discipline (Quهائd's Hard Rules — Non-Negotiable)

### 6.1 Rules (From Quهائd's Directive)

| Rule | Implementation |
|------|----------------|
| **All AI models in `D:\Intelligence models\` only** | Symlinks + WSL2 env var `HF_HOME=D:\Intelligence models\huggingface`, `OLLAMA_MODELS=D:\Intelligence models\ollama` |
| **No big libraries on C:** | `pip install --target=D:\Intelligence models\python_libs <pkg>` for heavy libs |
| **C: cleanup if discovered** | `cleanup_storage.py` script (audits + relocates) runs in Phase 0.2 |
| **Duplicate detection** | `duplicates_audit.py` finds duplicate Ollama/HF models, deletes with Quهائd's explicit go-ahead |
| **Wolf_Agent pollution** | `wolf1-brain` + `wolf-router` flagged for removal (NOT USER FAVORITE — separate system) |

### 6.2 Cleanup Script (Phase 0.2 deliverable)

```python
# scripts/storage_audit.py — runs first to confirm scope
def audit_drive(root: Path) -> list[ModelLocation]:
    """Find all AI models on the machine + categorize."""
    # Walks C:\, D:\, E:\, F:\
    # Categorizes: in-correct-location / duplicate / outside-D / wolf-pollution
    # Returns list[ModelLocation] for review
```

---

## 🚀 7. Phased Roadmap (12 Phases — Each Independently Verifiable)

> **Verification principle:** Each phase ends with a smoke test. No "trust me" — only "I saw it work."

### Phase 0 — Environment Setup (THIS WEEK)
- **0.1** Storage audit + cleanup (delete wolf1-brain, wolf-router)
- **0.2** Move `~/.cache/huggingface` symlink to D:\
- **0.3** Move Ollama models location to D:\
- **0.4** Start Docker daemon (Windows service: `services.msc → Docker Desktop`)
- **0.5** Install uv, Git LFS, ripgrep, Windows Terminal
- **0.6** Verify: `python -c "import torch; print(torch.cuda.is_available())"` → True
- **Deliverable:** `scripts/storage_audit.py` + clean C:\ drive

### Phase 1 — Training Data Curation
- **1.1** Inventory existing D:\Intelligence models\huggingface\datasets
- **1.2** From training chat: extract Bespoke-Stratos-17k, glaive-function-calling-v2, CodeFeedback, UltraChat-200k JSONL samples (sub-set, ~7500 examples target)
- **1.3** Synthetic Data Factory: use Ollama local Llama-3.1-8B (or local Qwen) to convert Quهائd's domain PDFs/CSVs into ChatML examples
- **1.4** Add Quهائd's domain expertise corpus (marine biology, agriculture, chemistry) — pre-curated in D:\
- **1.5** Generate final `body/training/omni_training_data.jsonl` (ChatML format, ≤4096 tokens/line)
- **Deliverable:** Verified JSONL with 7,500 examples + domain augmentation

### Phase 2 — Unsloth Installation
- **2.1** Pull Unsloth Docker: `docker pull unsloth/unsloth:latest-jupyter`
- **2.2** Configure WSL2 memory cap: `C:\Users\Hesham\.wslconfig` → `[wsl2]\nmemory=12GB`
- **2.3** Run container with NVIDIA GPU: `docker run --gpus all -v ${PWD}:/workspace -p 8888:8888 unsloth/unsloth`
- **2.4** Open JupyterLab → verify GPU access → smoke test with 100 examples
- **Deliverable:** Working Unsloth container with Python env

### Phase 3 — SFT Training (Phase 1 per training chat)
- **3.1** Load Llama-3.1-8B-Instruct 4-bit via `FastLanguageModel.from_pretrained()`
- **3.2** Configure LoRA: r=16, alpha=16, target_modules (q,k,v,o,gate,up,down)
- **3.3** Configure SFT trainer with max_seq_length=4096 (per chat hard rule)
- **3.4** Train: ~7,500 examples × 2 epochs ≈ 4-6 hours
- **3.5** Export: `model.save_pretrained_gguf("V1_Super_Base", quantization_method="q4_k_m")`
- **3.6** Backup V1 to `body/models_ready/`
- **Deliverable:** V1_Super_Base.gguf (~5GB) + smoke test on 5 tasks

### Phase 4 — DPO Training (Phase 2 per training chat)
- **4.1** Generate preference pairs: chosen vs rejected from Quهائd's code review samples OR use argilla/ultrafeedback-binarized
- **4.2** Re-load V1_Super_Base + apply DPO config
- **4.3** Train DPO with same hardware, ~2-3 hours
- **4.4** Export V2_Super_Astra.gguf
- **4.5** A/B test V1 vs V2 on 10 coding tasks (regression test)
- **4.6** If V2 better: promote. If V2 worse: keep V1.
- **Deliverable:** V2_Super_Astra.gguf (or fallback to V1) + A/B report

### Phase 5 — llama.cpp Deployment (RoPE + KV Quant)
- **5.1** Build llama.cpp for Windows OR download pre-built
- **5.2** Copy V2 model to `body/model/`
- **5.3** Launch: `llama-server.exe -m model.gguf --ctx-size 500000 --rope-scale 4 --cache-type q4_0 -ngl 99 --port 8080 -t 8`
- **5.4** OpenAI-compatible API at `http://localhost:8080/v1/`
- **5.5** Smoke test: send 400k-token request → verify KV cache compression
- **Deliverable:** Running local inference server (zero cloud dependency)

### Phase 6 — Body Knowledge Setup (AGORA-inspired)
- **6.1** Initialize ChromaDB: `body/knowledge_graph/chroma_db/`
- **6.2** Pre-populate from curated D:\Intelligence models knowledge
- **6.3** Build knowledge graph edges (JSON file): KB-to-KB semantic relationships
- **6.4** Tool definitions: `RECALL_BODY_KB(query, kb_filter)`, `UPDATE_BODY_KB(content, target_kb)`
- **6.5** Self-test: retrieve from each KB, verify embeddings work
- **Deliverable:** Body knowledge functional with ≥8 specialized KBs

### Phase 7 — Orchestrator (Custom FastAPI — replaces n8n)
- **7.1** `body/orchestrator/main.py` (FastAPI app)
- **7.2** Endpoints: `/webhook/github`, `/webhook/gmail`, `/webhook/cron`, `/v1/chat/completions` proxy
- **7.3** Task state DB: SQLite at `body/orchestrator/state.db`
- **7.4** Tool registry: Send email, open GitHub PR, save to KB, schedule task
- **7.5** Deploy as Windows service: `python -m pywin32_service`
- **Deliverable:** Production orchestrator replacing n8n

### Phase 8 — Long-Horizon Agent Loop
- **8.1** ReAct training data: 200-300 examples of Tool Observation → Thought → Action flow
- **8.2** LoRA fine-tune V2 on ReAct patterns (light, ~1 hour)
- **8.3** Context summarizer: detect >90% capacity → trigger SUMMARIZE_AND_FLUSH
- **8.4** Death-loop preventer: track consecutive failures → trigger ESCALATE_TO_HUMAN at 3
- **8.5** Sleep mode handler: when idle, send to waiting state (Wake on webhook)
- **Deliverable:** Alpha Wolf Agent running autonomously for days (smoke test: 24hr continuous run)

### Phase 9 — Auto-Self-Curation (Unique Capability)
- **9.1** Action: `FETCH_AND_LEARN(source: "huggingface"|"url", topic, quality_filter)`
- **9.2** Pipeline: download → dedup → quality score → embed → store in appropriate KB
- **9.3** Tool registry: model can issue FETCH commands during ReAct loop
- **9.4** Audit: `body/curation_log.jsonl` records every fetch
- **Deliverable:** Alpha Wolf can grow its own body over time

### Phase 10 — A/B Hardening
- **10.1** Long-term load test (72-hour continuous run)
- **10.2** Failure injection: simulate Docker crashes, OOMs, network outages
- **10.3** Rollback procedure: documented + tested
- **10.4** Backup scripts: `backup_body.py` (compress + version-tagged snapshot)
- **Deliverable:** Production-grade Alpha Wolf with recovery procedures

### Phase 11 — Final Integration & Documentation
- **11.1** Write `body/README.md` (operator manual)
- **11.2** Write `body/PROJECT_PLAN.md` ← THIS FILE's evolved version
- **11.3** Update `mind_map.html` with production architecture
- **11.4** Record training data lineage: which Quهائd directive led to which choice
- **11.5** Git commit (with git LFS for models)
- **Deliverable:** Production-ready Alpha Wolf with full documentation

---

## ⚠️ 8. Risks + Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| **Unsloth Docker fails to load on RTX 5060 Ti** | Medium | High (blocks training) | Pre-test in Phase 2 with smoke run (100 examples); fallback = manual pip install + train outside Docker |
| **Context corruption at 500k tokens with RoPE 4** | Medium | High | Gradual scale-up: 131k → 250k → 500k; test each step |
| **KV cache OOM at 500k tokens** | Medium | Medium | Adaptive: `--cache-type q8_0` if q4_0 OOMs |
| **Vector DB corruption (ChromaDB)** | Low | Medium | Daily `body/knowledge_graph/backup/` snapshot |
| **C: drive runs out during training** | Medium | High | Monitoring alert at <10GB free; auto-pause training |
| **Wolf_Agent pollution if not cleaned** | High (already present) | Medium | Phase 0.1 explicit cleanup task |
| **User can't find anything (no docs)** | High if not done | Medium | Phase 11.1 README + this PLAN.md |
| **DPO fails or V2 is worse than V1** | Medium | Low (we keep V1) | Iron Law #21 — V1 always preserved |
| **GPU driver crash mid-training** | Low | Medium (lose up to 6hr work) | Unsloth auto-checkpoints every 500 steps |
| **Body KB fragmentation (millions of unrelated docs)** | Medium | Medium (slow retrieval) | Daily curation + dedup script |

---

## 📝 9. Decision Log (Why We Chose What We Chose)

| Decision | Choice | Reason | Quهائd's Directive Source |
|----------|--------|--------|---------------------------|
| **Base model** | Llama-3.1-8B-Instruct | Verified 24% jailbreak success rate vs Qwen's 60-76% | File "تدريب نماذج الذكاء فاين تيوننج.txt" lines 314-326 |
| **Training platform** | Unsloth (Docker) | 4-bit quant + LoRA + 16GB VRAM fit | File lines 7-19 |
| **Training data mixture** | 30/20/20/20/10 | Discussed as "Golden Cocktail" | File lines 167-173 |
| **Output format** | GGUF Q4_K_M | llama.cpp compatibility + 5GB size | File line 263 |
| **Context extension** | RoPE scale 4 (131k → 500k) | Memory without retraining | File lines 588-591 |
| **KV cache** | Q4_0 | Compresses 70% of cache | File lines 589-591 |
| **Long-term memory** | ChromaDB + JSON graph (AGORA-inspired) | Quهائd's vision of unified body | This plan + AGORA paper |
| **Version control** | V1 + V2 kept (Iron Law #21) | Quهائd's SRE discipline | File lines 274-308 |
| **Orchestrator** | Custom FastAPI (no n8n) | Quهائd's "professional tools only" | This session |
| **Storage discipline** | D:\Intelligence models only | Quهائd's hard rule | This session |
| **AGORA pattern** | Multiple specialized vector DBs as graph | Quهائd's vision | Link in chat |
| **LLM ops** | Ollama local + llama.cpp inference | Avoid cloud lock-in | This plan |

---

## 🔗 10. References

### 10.1 Source Documents
- `Alpha Wolf Agent\تدريب نماذج الذكاء فاين تيوننج.txt` — Quهائd's training chat (704 lines)
- `Alpha Wolf Agent\mind_map.html` — Interactive architecture (this Phase 0.1)
- `E:\Agents\The Expert Team\.opencode\knowledge\governance-protocol.md` — Iron Laws body context

### 10.2 External Repos
- [Unsloth GitHub](https://github.com/unslothai/unsloth)
- [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp)
- [ChromaDB GitHub](https://github.com/chroma-core/chroma)
- [AGORA Paper (NeurIPS 2025)](https://github.com/yifanzhang-pro/agora) — Reference for body design
- [Llama-3.1-8B-Instruct (Hugging Face)](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)
- [Bespoke-Stratos-17k](https://huggingface.co/datasets/HuggingFaceH4/Bespoke-Stratos-17k)
- [glaive-function-calling-v2](https://huggingface.co/datasets/glaiveai/glaive-function-calling-v2)
- [m-a-p/CodeFeedback-Filtered-Instruction](https://huggingface.co/datasets/m-a-p/CodeFeedback-Filtered-Instruction)
- [UltraChat-200k](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k)
- [argilla/ultrafeedback-binarized-cleaned](https://huggingface.co/datasets/argilla/ultrafeedback-binarized-preferences-cleaned)

### 10.3 Iron Laws Applied (Body — for context)
- **#42** Body Contamination Prevention (Alpha Wolf lives in workspace, not body)
- **#36** 5-Layer Save (this plan = Layer 1+3)
- **#22** Autonomous (this plan executes without constant confirmation)
- **#15** Verify Before Claim (each phase ends with smoke test)
- **#13** Self-Critical Check (applied before this plan written)

---

## 🎯 11. Success Criteria (How We Know It Worked)

| Criterion | Phase | Verification |
|-----------|-------|--------------|
| **C: drive ≥20GB free** | 0.2 | `Get-PSDrive C \| Select Free` → ≥ 20 GB |
| **No AI models outside D:\Intelligence models** | 0.2 | `storage_audit.py` → 0 violations |
| **Alpha Wolf passes basic coding tasks** | 3.6 | 5/5 smoke tests pass |
| **Alpha Wolf uses tools correctly** | 4.5 | Tool-calling JSONL accuracy ≥90% |
| **500k context works without OOM** | 5.5 | Send 400k-token prompt → server responds |
| **Body KB retrieves domain knowledge** | 6.5 | Retrieve "oyster aquaculture" → relevant docs |
| **Autonomous loop runs ≥24 hours** | 10.1 | Continuous run without crash |
| **V2 quality ≥ V1** | 4.5 | A/B test: V2 wins ≥7 of 10 tasks |

When all criteria pass → **Alpha Wolf Agent = production-ready**.

---

## 📅 12. Timeline Estimate

| Phase | Effort | Cumulative |
|-------|--------|------------|
| 0 (Environment) | 2-4 hours | 1 day |
| 1 (Data Curation) | 6-10 hours | 3 days |
| 2 (Unsloth Install) | 1-2 hours | 3.5 days |
| 3 (SFT) | 6-12 hours | 5-6 days |
| 4 (DPO) | 3-6 hours | 6-7 days |
| 5 (llama.cpp) | 1-2 hours | 7-8 days |
| 6 (Body KB) | 4-6 hours | 8-9 days |
| 7 (Orchestrator) | 8-16 hours | 10-12 days |
| 8 (Long-Horizon) | 4-8 hours | 11-13 days |
| 9 (Self-Curation) | 4-8 hours | 12-14 days |
| 10 (A/B) | 8-16 hours (mostly waiting) | 13-16 days |
| 11 (Docs) | 2-4 hours | 14-17 days |

**Total: ~2-3 weeks** for fully production-ready Alpha Wolf Agent.

---

## 🚦 13. Next Actions (Awaiting Quهائd)

1. **Review this plan** + `mind_map.html` (interactive companion)
2. **Approve / modify / redirect** (Iron Law #41 Conflict Disclosure if conflict)
3. **If approved → Phase 0.1 starts immediately** (storage audit + cleanup)

---

> **Last updated:** 2026-09-23 — Phase 0.1 (Initial plan)
> **Author:** Orchestrator (Expert Team synthesis)
> **Status:** 🟡 Awaiting approval
