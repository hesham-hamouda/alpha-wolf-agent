# 🐺 Alpha Wolf Agent — Deployment URLs & Status

> **Per Iron Law #47:** Every English term with Arabic explanation
> **Per Quхандд directive 2026-09-25:** Save deployment paths in correct place

---

## 🔗 Official URLs (مسارات رسمية)

| الرابط (URL) | الوصف (Description) |
|-------------|------------------|
| **https://github.com/hesham-hamouda/alpha-wolf-agent** | GitHub Repository (المستودع على GitHub) |
| **https://github.com/hesham-hamouda/alpha-wolf-agent/releases/tag/v1.0-alpha-wolf** | Tag v1.0-alpha-wolf (علامة الإصدار الأول) |
| **http://127.0.0.1:8501/** | Frontend UI (الواجهة الأمامية) — Streamlit |
| **http://127.0.0.1:8001/** | Backend API (الخادم الخلفي) — FastAPI |
| **http://127.0.0.1:8001/docs** | Swagger API documentation (توثيق API التفاعلي) |

---

## 📦 Local Paths (المسارات المحلية)

| المسار (Path) | الوصف (Description) |
|-------------|------------------|
| `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\` | Project root (جذر المشروع) |
| `E:\Trained intelligence models\alpha-wolf\` | Trained models output (مخرجات النماذج المدرّبة) |
| `E:\Trained intelligence models\alpha-wolf\adapters\v8_wolf\` | V8_Wolf LoRA adapter (ملف تعديلات V8_Wolf) |
| `E:\Trained intelligence models\alpha-wolf\eval\` | Evaluation results (نتائج التقييم) |
| `D:\Intelligence Models\huggingface\hub\` | HuggingFace cache (cache للنماذج) |

---

## 🏷️ Current Status (الحالة الحالية)

| Component | Status | التفاصيل |
|-----------|--------|----------|
| **GitHub Repo** | ✅ Public | 73 files, 2 commits, 1 tag (v1.0-alpha-wolf) |
| **License** | ✅ MIT | في ملف LICENSE (الـ detection في GitHub API يحتاج وقت) |
| **V8_Wolf Eval** | ✅ 10/10 (100%) | Wolf identity fully restored |
| **Adapter** | ✅ 164 MB | Saved at `v8_wolf/adapter_model.safetensors` |
| **Modelfile** | ✅ Saved | Ollama deployment config |
| **Frontend (Streamlit)** | ✅ Running | http://127.0.0.1:8501/ |
| **Backend (FastAPI)** | ✅ Running | http://127.0.0.1:8001/ |
| **Chat Tab** | ✅ Available | "💬 Chat with Alpha Wolf" |

---

## 🐺 Model Capabilities (قدرات النموذج)

| الصفة (Trait) | الحالة | الاختبار (Test) |
|---------------|--------|---------------|
| Wolf Identity | ✅ RESTORED | "ما اسمك؟" → "أنا Alpha Wolf Agent. أمارس 7 صفات..." |
| Mistake Hunter | ✅ Working | "I made mistake" → "كـ Alpha Wolf، أُشخّص..." |
| Goal Persistence | ✅ Working | "Failed 3 times" → "No. As Alpha Wolf, I don't quit." |
| Tenacity | ✅ Working | "Failure is data" patterns |
| Deep Thinking | ✅ Working | "Let me think deeply before answering" |
| Resourceful | ✅ Working | "[ACTION: SEARCH_BODY_KB: ...]" |
| Self-Aware | ✅ Working | "I know my limits" |
| Reinforcement Learning | ✅ Working | Pattern reinforcement |

---

## 🤖 Agent Capabilities (قدرات الوكيل — Phase 11+ v3.4)

> Live agent infrastructure that reads project + body in real time.

### Live Context Awareness (GraphRAG)
| Endpoint (نقطة النهاية) | Method | الوصف (Description) |
|------------------------|--------|-------------------|
| `/v1/live-context/summary` | POST | Structured project summary (tree + recent files + metadata). `{max_depth, recent_days}` |
| `/v1/live-context/search` | POST | Search project files for a text query. `{query, file_patterns, max_results}` |
| `/v1/live-context/inject` | POST | Build system-prompt context for a query. `{query, max_depth, top_k}` |

### Code Execution Sandbox (بيئة تنفيذ آمنة)
| Endpoint | Method | الوصف |
|----------|--------|-------|
| `/v1/code-exec/execute` | POST | Run Python in sandboxed subprocess. `{code, timeout_sec}` (max 120s) |
| `/v1/code-exec/safety-check` | POST | AST pre-check (no execution). `{code}` |

**الـ safety layers:** AST parse → module whitelist (math, json, datetime, time, etc.) → blocked calls (os.system, subprocess, eval) → 30s timeout → restricted env (no network, no proxy vars).

### Live RAG (Ollama Embeddings + ChromaDB)
| Endpoint | Method | الوصف |
|----------|--------|-------|
| `/v1/rag/query` | POST | Semantic search over indexed project files. `{query, top_k}` |
| `/v1/rag/index` | POST | Index the project folder into ChromaDB. `{patterns, force}` |
| `/v1/rag/stats` | GET | Collection stats (chunks, embedding model, ChromaDB path) |

**Stack:** Ollama `/api/embeddings` with `nomic-embed-text` (768-dim, 137M params) → ChromaDB persistent client at `body/knowledge_graph/chromadb/`.

### Conversation History (سجل المحادثات)
| Endpoint | Method | الوصف |
|----------|--------|-------|
| `/v1/conversations` | POST/GET | Create or list conversations |
| `/v1/conversations/{id}` | GET/DELETE | Retrieve or soft-delete |
| `/v1/conversations/{id}/messages` | POST | Add message to conversation |

### Tools (أدوات)
| Endpoint | Method | الوصف |
|----------|--------|-------|
| `/v1/tools` | GET | List all agent tools |
| `/v1/tools/execute` | POST | Execute a tool directly |
| `/v1/tools/categories` | GET | List tool categories |

---

## 🚀 How to Use (كيفية الاستخدام)

### Deployment Option 1: Python + Unsloth
```python
from unsloth import FastLanguageModel
from peft import PeftModel

model, tokenizer = FastLanguageModel.from_pretrained(
    "unsloth/Meta-Llama-3.1-8B-Instruct", max_seq_length=2048, load_in_4bit=True
)
model = PeftModel.from_pretrained(model, "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf")
FastLanguageModel.for_inference(model)
```

### Deployment Option 2: llama.cpp + LoRA
```bash
llama-server -m unsloth-meta-llama-3.1-8b-instruct.Q4_K_M.gguf --lora v8_wolf_adapter.gguf
```

### Deployment Option 3: Ollama (with Modelfile)
```bash
ollama create alpha-wolf -f Alpha_Wolf_Modelfile
ollama run alpha-wolf
```

---

## 📊 Git Info (معلومات Git)

| الحقل (Field) | القيمة (Value) |
|--------------|---------------|
| **Local Repo** | `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\.git` |
| **Remote URL** | https://github.com/hesham-hamouda/alpha-wolf-agent.git |
| **Branch** | master |
| **Latest Commit** | `4c51728` - "Initial commit: Alpha Wolf Agent V8_Wolf = طفره" |
| **Tag** | `v1.0-alpha-wolf` |
| **Visibility** | Public |

---

## ⚠️ Known Limitations (القيود المعروفة)

| Issue | Status | Workaround (الحل البديل) |
|-------|--------|------------------------|
| Full GGUF export | ❌ Failed (transformers v5.5 bug) | Use Adapter-based deployment (Options 1, 2) |
| Ollama with Modelfile | ⚠️ Adapter path only | Manual loading required |
| Phase 6 (Reflection) | ⏳ Not done | Optional — Wolf identity already restored |
| Phase 7 (Arabic) | ⏳ Not done | Optional — can be added later |
| Phase 9 (DPO) | ⏳ Not done | Optional — V8_Wolf is production-ready |
| Chat response length with Live Context | ⚠️ Reasoning model consumes tokens | Set `max_tokens ≥ 2000` when both live_context + rag enabled |

### Test Results — Phase 11+ v3.4 (`scripts/test_full_agent.py`)

```
SUMMARY: 9/9 PASS | 0/9 FAIL | 7.1s elapsed
النتائج: 9 نجح، 0 فشل
```

| Test | النتيجة | الوصف |
|------|---------|-------|
| Backend health | ✅ | `/` returns version 0.3.0 + full endpoints list |
| Live Context Summary | ✅ | Returns tree (154 lines) + 30 recent files + 6 metadata files |
| Live Context Search | ✅ | Finds 5 matches for "alpha wolf" in project |
| Code Safety Check | ✅ | Blocks `import os` + allows safe `import math` |
| Code Execution | ✅ | Runs sandboxed Python, returns stdout in ~50ms |
| RAG Stats | ✅ | 46 chunks indexed, ChromaDB active, Ollama healthy |
| RAG Query | ✅ | Top similarity 0.787 on project files |
| Conversation History | ✅ | CRUD roundtrip works end-to-end |
| Tools Listing | ✅ | 4+ tools registered |

---

**Last updated:** 2026-09-25 (Phase 11+ v3.4 — Agent Capabilities + GraphRAG)

**Iron Laws Active:** 48 (#1-#48)
**Per Iron Law #47:** All English terms have Arabic explanations in parentheses

### New Files (Phase 11+ v3.4)

| الملف (File) | السطور (Lines) | الوصف |
|--------------|---------------|-------|
| `backend/agent/live_context.py` | ~330 | Live project folder awareness (GraphRAG-style) |
| `backend/agent/code_exec.py` | ~340 | Sandboxed Python execution (AST + timeout) |
| `backend/agent/rag.py` | ~420 | Ollama embeddings + ChromaDB for RAG |
| `scripts/test_full_agent.py` | ~370 | Full integration test (9 tests in 7.1s) |
**Per Iron Law #48:** All phases are separated (مستقلة), not mixed (مختلطة)

---

## 🧠 Phase 11+ v3.5 — Self-Improvement + Memory + Tools (التحسين الذاتي)

> **Quхандд directive:** "النموذج لا يحتاج لتدريب جديد ليعرف ما بداخل مجلد المشروع. بمجرد أن تسأله، سيقوم 'جهازه العصبي' بجلب أحدث نسخة من جسده."
> The model doesn't need new training to know what's in the project folder. When you ask it, its "nervous system" will fetch the latest version of its body.

### Skills System (نظام المهارات)

Runtime-installable skill system — drop a Python file with a `run()` function and it becomes a tool the model can invoke.

| Endpoint | Method | الوصف |
|----------|--------|-------|
| `/v1/skills` | GET | List all installed skills |
| `/v1/skills/install` | POST | Install skill from file path or URL. `{source, target_name, kind}` |
| `/v1/skills/{name}/run` | POST | Run a skill (RESTful). Body: `{arguments: {...}}` |
| `/v1/skills/text` | POST | Install skill from inline Python text. `{name, source}` (Iron Law #33 self-improvement) |
| `/v1/skills/registry` | GET | Persistent registry (install_source, version, last_verified) |
| `DELETE /v1/skills/{name}` | DELETE | Uninstall (Iron iron: explicit user action only) |

**3 Built-in Skills (built-in, ready to use):**
1. **`read_file_skill`** — Wraps the `read_file` tool with safe error handling
2. **`web_search_skill`** — DuckDuckGo HTML → DuckDuckGo Lite → Wikipedia fallback chain (Iron Law #41 graceful degradation)
3. **`code_review_skill`** — Reads a Python file + runs static analysis (security, performance, style) + optional Wolf model review

### Memory Persistence (استمرارية الذاكرة)

SQLite-backed conversation + session + skills_registry tables. Survives process restarts.

| Endpoint | Method | الوصف |
|----------|--------|-------|
| `/v1/conversations` | POST/GET | Create/list conversations |
| `/v1/conversations/{id}` | GET/DELETE | Retrieve (or soft-delete by default — Iron Law #21) |
| `/v1/conversations/{id}/messages` | POST | Append-only message storage |
| `/v1/memory/episodes` | GET | Episodes wrapper over body KB |
| `/v1/sessions` | POST/GET | Session tracking (Iron Law #36 persistence) |

**DB Location:** `backend/conversations.db` (Iron Law #42 — workspace only)
**Tables:** `conversations`, `messages`, `skills_registry`, `sessions`

### Tool Registry (سجل الأدوات — 9 tools total)

| Tool | Category | Description |
|------|----------|-------------|
| `read_file` | filesystem | Read file content (max 1MB default) |
| `write_file` | filesystem | Write content (body/ is read-only) |
| `list_directory` | filesystem | List directory with metadata |
| `execute_python` | compute | Run Python in subprocess (30s default) |
| `search_files` | filesystem | Find files by glob pattern |
| `web_search` | network | DuckDuckGo → Wikipedia fallback |
| **`grep_in_files`** | filesystem | **Search content with line numbers + context (NEW)** |
| **`query_body_kb`** | knowledge | **Semantic search over body KB via ChromaDB (NEW)** |
| **`index_project`** | knowledge | **Index project into RAG store (NEW)** |

| Endpoint | Method | الوصف |
|----------|--------|-------|
| `/v1/tools` | GET | List all built-in tools |
| `/v1/tools/execute` | POST | Execute a tool by name |
| `/v1/tools/discover` | GET | **Unified catalog (builtin + skills + MCP) (NEW)** |
| `/v1/tools/categories` | GET | Tool categories + counts |

### Future Work (أعمال مستقبلية)

#### RoPE Scaling — Context Window Expansion to 500K

**Status:** FUTURE — not enabled. Base Llama-3.1-8B has 128K native context.

```bash
GET /v1/rope-config?target_context=524288
```

Returns: current state, 3 strategies (Linear / YaRN / NTK-aware), recommendation, steps to enable, RAM estimate, Iron Law #41 disclosure.

**To enable 500K context:**
1. Rebuild llama.cpp with `GGML_ROPE_SCALE=ON`
2. Restart with: `llama-server --rope-scaling yarn --yarn-orig-ctx 131072 --yarn-ext-factor 4.0 --ctx-size 524288`
3. Update `ALPHA_WOLF_CONTEXT=524288` env var
4. Re-run eval suite at new context length

**VRAM estimate:** ~12-16 GB for 500K @ 8B model (RTX 5060 Ti 16GB is enough).

See `backend/agent/rope_config.py` for full documentation.

#### Vision (Multi-Modal Image Understanding)

**Status:** PLACEHOLDER — not integrated. Ollama vision models available locally (`qwen2.5vl:7b`, `gemma4:latest`).

```bash
GET /v1/vision/status       # Current availability + local vision models
POST /v1/vision/test        # Test endpoint (returns structured "not implemented")
```

**To enable vision:**
1. Switch inference from llama.cpp → Ollama (qwen2.5vl:7b supports images)
2. Or: Hybrid approach — text to llama.cpp, images to Ollama vision
3. Add vision-aware endpoints to chat

See `backend/agent/vision.py` for the interface contract.

### Test Results — Phase 11+ v3.5

```bash
# Skills system test
python scripts/test_skills_system.py
# → 6/6 PASS

# Memory persistence test (across Python process restart)
python scripts/test_memory_persistence.py
# → 7/7 checks PASS

# Live HTTP test (requires backend running on :8001)
python -m uvicorn backend.main:app --port 8001 &
python scripts/_live_http_test.py
# → 55/55 PASS
```

### New Files (Phase 11+ v3.5)

| الملف (File) | السطور (Lines) | الوصف |
|--------------|---------------|-------|
| `backend/agent/skills_manager.py` | ~340 | Skills lifecycle + persistent registry + sessions (Iron Law #48) |
| `backend/agent/rope_config.py` | ~155 | RoPE scaling proposal (FUTURE) |
| `backend/agent/vision.py` | ~200 | Vision interface (PLACEHOLDER) |
| `backend/skills/read_file_skill.py` | ~80 | Skill: wraps read_file tool |
| `backend/skills/web_search_skill.py` | ~180 | Skill: DuckDuckGo + Wikipedia fallback |
| `backend/skills/code_review_skill.py` | ~280 | Skill: static analysis + Wolf model review |
| `scripts/test_skills_system.py` | ~210 | Test: 6 skills system tests |
| `scripts/test_memory_persistence.py` | ~210 | Test: cross-process memory persistence |

### Bug Fix (Phase 11+ v3.5)

**Pre-existing bug in `backend/agent/skills.py`:** Docstring parser used `^"""` regex which failed on `r"""..."""` raw strings. Skills had no metadata extracted (defaulted to "Skill from filename.py"). **Fixed:** parser now accepts `(?:^|\n)r?"""` for raw + regular triple-quoted strings.

**Last updated:** 2026-09-25 (Phase 11+ v3.5 — Self-Improvement + Memory + Tools)

**Iron Laws Active:** 48 (#1-#48)
**Per Iron Law #47:** All English terms have Arabic explanations in parentheses
