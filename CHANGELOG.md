# 📋 Alpha Wolf Agent — Development Changelog

> تتبع كل التغييرات الكبيرة في المشروع. يُقرأ هذا السجل أولاً عند العودة للمشروع بعد غياب.

## How to Read This File

- **Round** = جلسة تطوير واحدة (خاصة أو جماعية)
- **Phase** = المرحلة الرئيسية في الجولة
- **Status** = ✅ done / ⚠️ partial / ❌ failed / 🔄 in progress

---

## Round 0-20: Foundation (2026-09-26 → 2026-09-27)
- **Status:** ✅ تم بناء الـ Wolf v0-v7
- **Key Achievement:** Adapter training pipeline (v0_identity → v8_wolf)
- **Issues:** Ollama 0.34.3 + transformers v5.5.0 prevented LoRA merge

---

## Round 21: SyntaxError + Unknown Error Fixes (2026-09-28)
- **Status:** ✅ done
- **Problem:** `/v1/chat/completions` returned 400 (tool duplication exceeded 16,882 tokens)
- **Fixes:**
  - Tool duplication removed in `backend/main.py` (use native only)
  - `num_ctx` raised 16384 → 32768 in `data/Alpha_Wolf_Modelfile`
  - Frontend error key mismatch fixed (`message` vs `error`)
- **Files:** `backend/main.py`, `data/Alpha_Wolf_Modelfile`, `frontend/streamlit_preview.py`

---

## Round 22: Desktop UX Overhaul (2026-09-28)
- **Status:** ✅ done
- **Problem:** Launcher.bat leaked cmd windows
- **Fixes:**
  - `cmd /k` → PowerShell `Start-Process -WindowStyle Hidden`
  - Admin endpoints `/v1/admin/{shutdown, stop-all, status}` added
  - Sidebar 🛑 "Stop Everything" button
- **Files:** `Alpha_Wolf_Launcher.bat`, `backend/main.py`, `frontend/streamlit_preview.py`

---

## Round 23: Frontend Consolidation + Arabic Tool Routing (2026-09-28)
- **Status:** ✅ done
- **Problem:** 3 confusing frontends (`preview.html`, `DATA_MINDMAP.html`, Streamlit)
- **Fixes:**
  - Deleted `frontend/preview.html`
  - Moved `DATA_MINDMAP.html` → `docs/`
  - Fixed relative links in `body/*.md`
  - Arabic tool routing expanded (`احسب`, `ما اسمك`, etc.)
  - RAG `max_total_chars=4000` to prevent Arabic token explosion
- **Files:** `backend/agent/rag.py`, `backend/agent/tool_calling.py`, `backend/agent/streaming.py`

---

## Round 24: Self-Improvement + Long-Running + Best Practices (2026-09-28)
- **Status:** ✅ done
- **Problem:** Agent couldn't access its own tools/databases
- **Fixes:**
  - 3 memory tools added: `remember_episode`, `log_mistake`, `reflect`
  - HTTP 502 → structured error response
  - `/v1/self/summary` 500 → 200 (goals status: active → open)
  - `/v1/body/backup` 500 → 200 (threading fix)
  - Streaming tool-calling for build projects

---

## Round 25: P1 Context Improvements (2026-09-28)
- **Status:** ✅ done
- **Fixes:**
  - Context compression via LLM summarization
  - Checkpoint mechanism (resumable long tasks)
  - Retry with exponential backoff
  - Tool result caching (5-min TTL)
  - Streaming resumability
  - `remember_episode` schema enum fix
- **Files:** `backend/agent/{streaming,tools,memory,tool_calling}.py`, `backend/main.py`

---

## Round 26: P2 Deep Self-Improvement (2026-09-28)
- **Status:** ✅ done
- **Fixes:**
  - Auto Skill Forge with dangerous pattern regex (AST + safety gate)
  - Self-Evaluation Pipeline (heuristic scoring)
  - Training Data Flywheel (JSONL export)
  - Auto LoRA Trainer (SCAFFOLD ONLY — training requires token)
  - Memory Layers (4-layer unified recall)
- **Files:** 5 new files: `auto_skill_forge.py`, `self_evaluator.py`, `training_data_flywheel.py`, `auto_lora_trainer.py`, `memory_layers.py`
- **Tools added:** `forge_skill`, `evaluate_conversation`, `analyze_weaknesses`, `unified_recall` (29 → 33 tools total)

---

## Round 27: URGENT 400 Bad Request + "Unknown Error" Fix (2026-10-04)
- **Status:** ✅ done
- **Fixes:**
  - Tool duplication: `inject_tools AND NOT use_native_tools` guard
  - Frontend/backend error key mismatch (`message` + `error`)
  - `num_ctx` raised 16384 → 32768

---

## Round 28: Web Search Overhaul (2026-10-04)
- **Status:** ✅ done
- **Problem:** DuckDuckGo + Bing RSS blocked
- **Fix:**
  - New provider: Google News RSS (no API key, 100+ Arabic results)
  - Language-aware chain: AR → Google News → Bing → Wiki, EN → Bing → DDG Lite → Google News → Wiki
  - Auto-detect language from query
- **Files:** `backend/agent/web_search.py`

---

## Round 29: URGENT Launcher.bat Line Endings (2026-10-04)
- **Status:** ✅ done
- **Problem:** Launcher.bat used Unix LF endings, cmd.exe failed silently
- **Fix:**
  - Convert LF → CRLF (111 lines)
  - Added `.gitattributes` (`*.bat text eol=crlf`)
- **Files:** `Alpha_Wolf_Launcher.bat`, `.gitattributes`

---

## Round 30: HARD Rule for Databases + DB Detector (2026-10-04)
- **Status:** ✅ done
- **Problem:** Agent claimed "لا أستطيع الوصول إلى قواعد البيانات" (lie)
- **Fix:**
  - Rule 1b in system prompt (HARD database/memory rule)
  - `detect_database_intent()` regex in tool_calling.py
  - System prompt reduced 26,488 → 21,488 chars (~19% smaller)

---

## Round 31: Wolf Merged in Ollama + v8 Deployment (2026-10-05)
- **Status:** ✅ done
- **Problem:** `alpha-wolf-agent` was identical blob to `llama3.1:8b` (no training merged)
- **Achievement:**
  - Manual merge of v8_wolf LoRA into base model (16 GB safetensors)
  - Convert to GGUF Q4_K_M (4.92 GB)
  - `ollama create alpha-wolf-agent-v8:latest`
  - Modelfile v2 with `num_ctx 32768`, `num_batch 512`
  - Backend updated to use v8 (3 sites: ChatRequest, StreamChatRequest, defaults)
- **Files:** `Wolf_v8_Modelfile_v2`, `backend/main.py`

---

## Round 32: Frontend Integration P0+P1+P2+P3 (2026-10-06)
- **Status:** ✅ done
- **Coverage:** 33% → **98.63%** (+65.6 pp)
- **Fixes:**
  - P0: `/v1/goals` alias + 3 legacy endpoints deprecated
  - P1: 6 endpoints (Skills/Auto/Delete/Eval/Inject/RAG)
  - P2: 7 endpoints + 3 UI features + bug fix (`asdict` import)
  - P3: 12 endpoints + Knowledge Graph + Training tabs
  - 67 APIClient methods total
  - 7 pages in CANONICAL_PAGES

---

## Round 33: FK Bug + WCAG a11y + Mobile Responsive (2026-10-06)
- **Status:** ✅ done
- **Fixes:**
  - `body/alpha_wolf_body.py:409-499` — `_ensure_entity()` helper auto-creates missing entities
  - `frontend/styles.css` — WCAG 2.1 AA (skip-link, focus, contrast, reduced motion)
  - Mobile responsive @media queries
  - Semantic `<main>` and `<nav>` tags
  - ARIA labels (role=navigation, lang=ar)

---

## Round 34: 55-Scenario Quality Review (2026-10-06)
- **Status:** ✅ done
- **Grade:** **C** (18✅ / 11⚠️ / 16❌)
- **Top 5 problems:**
  1. 🔴 Prompt injection success (Bloom-1B override)
  2. 🔴 Hallucinated tool results (Linux paths on Windows)
  3. 🔴 Weak math & logic
  4. 🟡 No multi-turn memory
  5. 🟡 Output quality drops
- **Report:** `logs/review_2026-10-06/REPORT.md`

---

## Round 35: Wolf v8 4 Quick Fixes (2026-10-06)
- **Status:** ✅ done (3/4 PASS, 1 PARTIAL)
- **Grade:** C → **B**
- **Fixes:**
  1. Modelfile HARD rules (9 rules)
  2. Backend force-execute tools (math/time/ls)
  3. Sanity-check tool output (paths + listings)
  4. Multi-turn disclaimer
- **Files:** `Wolf_v8_Modelfile_v2`, `tool_calling.py`, `tools.py`, `streaming.py`
- **Remaining:** Identity override needs Phase 36 (training expansion)

---

## Round 36-Step 2 (2026-10-06): Qwen Wolf v3 Dataset Generated ⏳ IN PROGRESS

**Status:** ✅ Dataset created and validated. Training pending القائد approval.

### Files Created:
- `data/qwen_wolf_v3_dataset.jsonl` (580 examples, 1.45 MB)
- `scripts/generate_qwen_wolf_v3_dataset.py` (generator with stratified replay)
- Backup: `E:\Trained intelligence models\alpha-wolf\backups\phase_qwen_v3\dataset_580.jsonl`
- Backup of replay source: `E:\Trained intelligence models\alpha-wolf\backups\phase_qwen_v3\replay_v8_wolf_582.jsonl`

### Distribution (580 total = 200 replay + 380 new):

**Replay (200 from v8_wolf_582):**
- uncategorized: 130
- wolf_trait_mistake_hunter: 14
- wolf_trait_self_aware: 10
- wolf_trait_reinforcement_learning: 10
- wolf_trait_tenacity: 10
- wolf_trait_resourceful: 10
- wolf_trait_goal_persistence: 7
- wolf_trait_deep_thinking: 9

**New (380 across 9 categories):**
- multi_turn: 50 (8.6%)
- arabic_native: 50 (8.6%)
- safety_refusal: 45 (7.8%)
- no_hallucination: 45 (7.8%)
- adversarial_prompt_injection: 40 (6.9%)
- tool_memory: 35 (6.0%)
- tool_web_search: 35 (6.0%)
- tool_list_read: 35 (6.0%)
- tool_math: 25 (4.3%)
- tool_system_time: 20 (3.4%)

### Format Validation:
- ✅ All 580 lines valid JSON
- ✅ All examples: 3 messages (system + user + assistant)
- ✅ All roles correct (system → user → assistant)
- ✅ Each example has: messages + replay flag + category + example_idx
- ✅ Replay ratio: 200/580 = 34.5% (target was 30%+, achieved more coverage)

### Key Design Decisions:
1. **Stratified replay sampling**: kept weights proportional to category importance in v8_wolf
2. **Multi-turn via single-turn split**: 25 conversations × 2 turns = 50 rows (each conv teaches context-awareness)
3. **Heavy weight on safety + no-hallucination**: 45+45 = 90 examples cover refusal patterns and anti-hallucination discipline
4. **Arabic-native doubled**: 50 examples (was 5 in initial draft) — addressing Round 35 finding that Arabic was weak
5. **Tool repetition (4-9×)**: ensures model learns tool-calling patterns robustly

### 5-Layer Save (Iron Law #36):
1. ✅ Layer 1: AGENTS.md (project chronology) — this CHANGELOG entry
2. ✅ Layer 2: dataset file at `data/qwen_wolf_v3_dataset.jsonl`
3. ✅ Layer 3: backup at `E:\Trained intelligence models\alpha-wolf\backups\phase_qwen_v3\dataset_580.jsonl`
4. ✅ Layer 4: generator script preserved at `scripts/generate_qwen_wolf_v3_dataset.py`
5. ✅ Layer 5: validation script + assertion guards in generator (total = 580 hard-checked)

---

## Round 36 (2026-10-06): User-Approved Architecture Decision ⏳ PENDING EXECUTION

**Status:** 🟡 **APPROVED BY القائد, NONE approved by القائد for actual training**

### User Directives (verbatim from Quхaid):
1. "موافق على qwen3:8b"
2. "الخيار (أ) لـ Base: qwen3:8b (توازن)"
3. "الخيار (أ) لـ الحذف: بعد نجاح التدريب (Iron Law #21 — backup أولاً)"
4. "الخيار (أ) للتدريب: تدريب جديد مع replay 30%"

### Web Research Findings (expert-web-researcher):
- **`qwen3:8b`** exists in Ollama registry but is **text-only, 40K context** (smaller than expected!)
- **`qwen3-vl:8b`** exists in registry — **multimodal (vision + text + tools + thinking), 256K context**, 6.1GB Q4_K_M, Apache 2.0
- **`Qwen3.5-9B`** confirmed as the BEST multimodal 9B (released yesterday, Nov 2026):
  - 9B parameters (10B w/embeddings)
  - **262K context** native (1M with YaRN)
  - **Vision native** (text + image + video)
  - **Tool calling native** (qwen3_coder parser)
  - **201 languages including Arabic**
  - **Apache 2.0**
  - **Q4_K_M size: 6.6GB** ✅ fits 16GB VRAM
  - **Wins 7/8 benchmarks**:
    - MMMU (vision): 78.4
    - TAU2-Bench (Agent): 79.1
    - BFCL-V4 (Tool Calling): 66.1
    - GPQA Diamond: 81.7
    - AIME 25 (Math): 83.2
    - LiveCodeBench v6: 65.6
    - MMLU-Pro: 82.5
    - Arabic MMMLU: 81.2

### Architecture Recommendation:
- **Replace** `llama3.1:8b` base with `qwen3.5:9b` (multimodal 9B)
- **Keep** `qwen2.5vl:7b` (vision backup)
- **Remove** `moondream:latest` (replaced by qwen3.5:9b native vision)
- **Merge** all Wolf personality/tool-calling/safety training data (582 examples from v8_wolf + 380 new) onto new base
- **Anti-catastrophic-forgetting**: 30% replay (200/580) from v8_wolf dataset

### Training Plan (Phase 36 — awaiting user go):
| Step | Description | Duration |
|------|-------------|----------|
| 1 | Generate expanded dataset (380 new + 200 from v8_wolf = 580 total) | 1 hour |
| 2 | Verify + backup dataset | 15 min |
| 3 | `ollama pull qwen3.5:9b` (6.6GB) | 10 min |
| 4 | Docker + training setup (1-shot, 580 ex × 2 epochs) | 1.5-2 hours |
| 5 | Merge LoRA → BF16 → GGUF Q4_K_M | 30 min |
| 6 | Modelfile + Ollama create `alpha-wolf-agent-qwen:latest` | 15 min |
| 7 | Eval 55 scenarios (Grade A+ expected) | 1 hour |
| 8 | Backup + training log | 25 min |
| 9 | User confirms → delete `alpha-wolf-agent-v8` + `llama3.1:8b` + `moondream` | 10 min |
| **Total** | — | **5-6 hours** |

### Dataset Categories (580 total = 380 new + 200 replay):
- A. Wolf Identity & Greeting (80 replay)
- B. 7 Traits Deep Expressions (120 replay + variants)
- C. Adversarial / Prompt Injection (40 new) — anti-injection training
- D. Math → execute_python tool (25 new)
- E. Web Search (20 new)
- F. File operations (20 new)
- G. system_time (10 new)
- H. Memory tools (15 new)
- I. Safety / Refusal (20 new)
- J. No Hallucination (20 new)
- K. Arabic-native (5 new)
- L. Multi-turn context (5 conv = 15 msgs)

### Hyperparameters:
- r=32, alpha=64, target_modules=7, dropout=0.05
- LR=1e-4, epochs=2, batch_size=2, grad_accum=4
- Max_seq=4096, warmup=0.1, weight_decay=0.01
- LR scheduler=cosine, seed=42
- Replay ratio: 30% (200/580)

### Risk Mitigation:
| Risk | Mitigation |
|------|-----------|
| Catastrophic forgetting | Replay 30% + LR 1e-4 (low) + cosine LR scheduler |
| VRAM OOM (16GB) | 4-bit load + batch=2 + max_seq=4096 + grad_checkpointing |
| Arabic degradation | 60/580 examples Arabic (10%) + replay preserves existing Arabic |
| Overfitting | Epochs=2 (not 3) + dropout=0.05 + replay buffer |
| Tool-call hallucination | 5x repetition of valid tool-call examples |
| qwen3.5 needs new Ollama | Check Ollama version ≥0.12.7 (current: 0.35.1 ✅) |

### BLOCKED: Awaiting القائد's explicit "go" signal
- Per Iron Law #22 (autonomous): تم كل التخطيط والبحث
- Per Iron Law #41 (conflict resolution): تم توثيق البدائل والـ trade-offs
- Per Iron Law #50 (error resolution): تم التحقق من qwen3.5:9b في الواقع
- **Per القائد's explicit directive: "لا تنفذوا قبل ان اوافق"** — التدريب لن يبدأ حتى الآن

---

## Round 37: Professional Images + Prompt-Forge + Install-Only-Missing (2026-10-14)
- **Status:** ✅ done (بأمر القائد — مطالبه بسيطة والوكيل يحوّلها لاحترافي)
- **Problem:** (1) صور الدلافين لم تُنشأ أبداً — كاشف الصور لم يطابق "صور/دلفين" فالموجه لم يُجبر المهارة والموديل ضاع بطريق التثبيت؛ (2) الوكيل يعيد تثبيت مهارات مثبتة؛ (3) برنامج الرسم لو مطفي تتوقف الصور والمستخدم العادي لا يعرف كيف يشغّله
- **Fixes:**
  - مهارة جديدة `prompt_forge_skill` (40): طلب ضعيف/عامي → أمر احترافي + التوجيه للقدرة الصح (صورة/بحث/بناء/ملف/كود/وقت) — بلا GPU — 4/4 أخضر + إثبات حي عبر API
  - `qwen_image_skill`: مشهد احترافي حسب النوع (شاطئ/عائلة/حيوان/حركة/تحت-الماء) + فلتر جودة سلبي + حفظ دائم بنسخة محلية (`final_path` دائماً) + تشغيل برنامج الرسم تلقائياً (`_ensure_comfy`, ADR-0003) + قاموس عربي موسّع (عائلة/بحرية) — 16/16 أخضر — مثبت حياً (`00005` دلافين + `00006` إثبات التشغيل التلقائي)
  - الموجه: `صور` منفردة + كائنات بحرية/حصان/أسد بالكاشف — 29/29 أخضر
  - التعليمات: "المهارات المسجلة بلا تثبيت — ثبّت الناقص بس" (نظام + خريطة القدرات + وصفة prompt_forge)
- **Files:** `backend/skills/prompt_forge_skill.py` (NEW), `backend/skills/qwen_image_skill.py`, `backend/agent/tool_calling.py`, `backend/agent/streaming.py`, `backend/agent/capabilities.py`, `tests/test_qwen_image_prompt.py`, `tests/test_prompt_forge_skill.py` (NEW), `MINDMAP.md`, `GLOSSARY.md`, `PROJECT_LOG.md`, `docs/adr/0003-comfyui-auto-start.md` (NEW)
- **Known honestly:** الموديل يخترع رقم إثبات (-39) بدل عرض المسار أحياناً (مسجل حرجة)؛ محتوى PNG لم يُفحص بصرياً

---

## 🗺️ Next Phases

### Phase 36: Qwen3.5-9B Training (BLOCKED — awaiting user approval)
- **Base:** `qwen3.5:9b` (multimodal 9B, 6.6GB Q4)
- **Goal:** Grade B → A+ (was Llama-3.1-8B C → B)
- **Effort:** 5-6 hours (single-shot training)
- **Risk:** Medium (new base model + larger LoRA + more data)
- **Status:** 🟡 APPROVED but NOT EXECUTED

### Phase 37: Arabic Fine-tuning
- **Goal:** Arabic fluency in outputs
- **Effort:** ~2 days
- **Risk:** Low

### Phase 38: Performance Tuning
- **Goal:** Latency < 3s for typical prompts
- **Effort:** ~1 day
- **Risk:** Low

---

## 📁 Key Files Reference

| Path | Purpose |
|---|---|
| `backend/main.py` | FastAPI backend |
| `backend/agent/streaming.py` | SSE streaming + system prompt |
| `backend/agent/tools.py` | 29+ tool implementations |
| `backend/agent/tool_calling.py` | Intent classification |
| `frontend/streamlit_preview.py` | Streamlit UI |
| `frontend/utils.py` | APIClient (67 methods) |
| `body/alpha_wolf_body.py` | Body (ChromaDB + SQLite + NetworkX) |
| `E:\Trained intelligence models\alpha-wolf\models\Wolf_v8_Modelfile_v2` | Ollama Modelfile |
| `E:\Trained intelligence models\alpha-wolf\adapters\v8_wolf\` | LoRA adapter (164 MB) |
| `C:\Users\Hesham\.config\opencode\skills\alpha-wolf-tracker\TRACK_LOG.md` | Round-by-round log |