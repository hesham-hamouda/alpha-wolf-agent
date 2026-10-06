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

## 🗺️ Next Phases

### Phase 36: Training Expansion (50+ adversarial identity examples)
- **Goal:** Grade B → A
- **Effort:** ~1 day (GPU training + merge + deploy)
- **Risk:** Medium

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