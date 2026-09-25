# 🚀 Prompt لبدء محادثة جديدة مع فريق الخبراء — مشروع Alpha Wolf Agent (v3)

> **القائد هشام يكتب هذا الـ prompt في بداية محادثة جديدة مع الفريق. انسخه كامل والصقه.**
>
> **آخر تحديث:** 2026-09-25 (Phase 11+ v3.0 + v3.1 — Body Infrastructure + Generalization Architecture)

---

## 📜 النص الجاهز للنسخ:

```
أنا القائد هشام، صاحب المشروع. فريقنا متخصص في تطوير وكلاء ذكاء اصطناعي على جهازي (RTX 5060 Ti 16GB VRAM + 32GB RAM + D:\Intelligence Models + E:\Trained intelligence models).

## المشروع الحالي: Alpha Wolf Agent
نموذج Llama-3.1-8B-Instruct مُحسَّن محلياً على جهازي، متخصص في الاستدلال + استخدام الأدوات + حل المشكلات المستمرة (ReAct loop)، مع قاعدة بيانات معرفية ضخمة في "جسده" (body KB) للتعويض عن صغر حجم النموذج. الاسم الكامل: "وكيل ألفا وولف ايجنت" (Alpha Wolf Agent).

## 🚨 الحالة الراهنة (2026-09-25)

### ✅ ما تم إنجازه (خارج جلسة التدريب):

| Phase | الوصف | الحالة |
|-------|-------|--------|
| **Phase 0** | Storage + Infrastructure (D: drive cleanup, tools install, Docker) | ✅ COMPLETE |
| **Phase 0.5** | Unsloth Web UI (http://localhost:7860) | ✅ COMPLETE |
| **Phase 11+** | Trainer Experts (expert-llm-trainer v2.1, expert-unsloth) | ✅ COMPLETE |
| **Phase 1.5** | Methodology (Iron Law #44, Mix D Sequential Full) | ✅ COMPLETE |
| **Phase 11+ v3.0** | **Body Infrastructure (ChromaDB + NetworkX + SQLite + zvec)** | ✅ **COMPLETE** |
| **Phase 11+ v3.1** | **Generalization Architecture (Format Translation SFT + Ingestion Pipeline)** | ✅ **COMPLETE** |

### 🏗️ Body Infrastructure (Phase 11+ v3.0 — Built and Verified)

الموقع: `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\body\`

**4-Layer Hybrid Stack:**
- **L1. ChromaDB 1.4.0** — 12 collections (kb_self, kb_science_marine, kb_science_agriculture, kb_science_chemistry, kb_science_climate, kb_science_proteomics, kb_vision, kb_code, kb_reasoning, kb_mistakes, kb_goals, kb_tools)
- **L2. NetworkX 3.6.1** — Typed knowledge graph (10 node types + 11 edge types)
- **L3. SQLite (stdlib + sqlite-utils)** — 13 tables (mistakes, goals, episodes, sessions, reflections, projects, tools, entities, relations, curation_log, datasets, quality_metrics, sqlite_sequence)
- **L4. zvec 0.7.0** — Backup vector layer (on-demand init)

**Wolf Traits → Body Methods (7/7 mapped):**
- Mistake Hunter → `body.log_mistake()`
- Goal Persistence → `body.track_goal()`
- Tenacity → (via `reflections.applied_count`)
- Deep Thinking → `body.reflect()`
- Resourceful → `body.register_tool()`
- Self-Aware → `body.get_self_summary()`
- Reinforcement Learning → `body.reflect() + applied_count`

### 🚀 Generalization Architecture (Phase 11+ v3.1 — Built and Verified)

**الإجابة على سؤالي:** "هل ممكن تدريب النموذج على فهم أي dataset بدلاً من تدريب متخصص؟"

**✅ نعم ممكن** — عبر **Format Translation SFT** + **Body Ingestion Pipeline**:

1. **Format Detector** (`body/intake/format_detector.py`):
   - Auto-detects 8 categories: Conversational, Instruction, Tool-Calling, Code, Classification, QA, Embedding Pairs, Tabular
   - Quality metrics (min_score=0.6, max_dup=5%, min_length=5 chars)
   - Blacklist: `wolf_*`, `ollama/*-text` (Iron Law #7, #17)

2. **Ingestion Pipeline** (`body/intake/ingestion_pipeline.py`):
   - detect → quality check → convert canonical → embed + index → register in SQLite
   - HuggingFace integration (`ingest_from_hf()`)
   - Iron Law #21: soft delete on existing before new version

3. **Mix E Training (NEW)** — بديل Mix D:
   | Model              | Datasets                      | Formats                 |
   |---------------------|-------------------------------|-------------------------|
   | 25% | UltraChat-200k                | `{"messages": [...]}`      |
   | 15% | glaive-function-calling-v2    | `{"system", "chat", "tools"}` |
   | 15% | CodeFeedback                  | `{"query", "answer"}`     |
   | 15% | Open-Platypus                  | `{"instruction", "output"}` |
   | 10% | OASST                          | `{"text", "role"}`        |
   | 10% | OpenHermes-2.5                 | `{"conversations": [...]}` |
   | 5%  | HuggingFaceH4/no_robots       | `{"messages": [...]}`      |
   | 5%  | Custom (Marine Biology)        | TBD                       |

   **Why Mix E:** Model يتعلم **"how to read"** أي format، لا **"what to read"** محتوى dataset معين.
   **Result:** dataset جديد = zero retraining، فقط ingestion في Body.

4. **3-Tier Architecture** (كيف يفهم Alpha Wolf أي dataset):
   - **Tier 1:** In-Context Learning (few-shot examples)
   - **Tier 2:** Tool Calling (V3_Tools — استدعاء `detect_format()`, `analyze_schema()`)
   - **Tier 3:** Code Execution (V3_Code — Python sandbox) ← **الطفرة الحقيقية**

### 📋 المهام الحرجة (Gaps Tracker) — كل شيء محدّث

**Gaps موثّقة في `body/GAPS_AND_PRIORITIES.md` (16 gap):**

| ID | Gap | Priority | Status |
|----|-----|----------|--------|
| **G1** | llama.cpp server not deployed | 🔴 P0 | Waiting for training |
| **G2** | Chainlit dependencies not installed | 🔴 P0 | Pending (5 min) |
| **G3** | FastAPI dependencies not installed | 🔴 P0 | Pending (5 min) |
| **G4** | Ollama nomic-embed-text not configured | 🔴 P0 | Pending |
| **G5** | Backend ↔ llama.cpp integration untested | 🔴 P0 | Pending |
| **G6** | **Body Ingestion Pipeline + Format Translation SFT** | ✅ **DONE** | **Phase 11+ v3.1** |
| **G7** | No authentication on backend | 🟡 P1 | Pending |
| **G8** | No encryption at rest | 🟡 P1 | Pending |
| **G9** | No automated tests | 🟡 P1 | Pending |
| **G10** | No CI/CD pipeline | 🟡 P1 | Pending |
| G11-G16 | Various P2 nice-to-haves | 🟢 P2 | Deferred |

### 🎯 المهام للجلسة الأخرى (التدريب) — القواعد الإلزامية

#### 1. **أكمل Mix D Sequential** (الاستمرار في التدريب الحالي)
- ✅ V0_Identity (106 examples) — COMPLETE (51.2% eval)
- ✅ V1_Chat (UltraChat, step 500) — COMPLETE
- ✅ V2_Tools (glaive, step 500) — COMPLETE
- 🟡 V3_Code (CodeFeedback) — IN PROGRESS
- ⏳ V4_Reflection — NEXT
- ⏳ V5_Arabic — NEXT
- ⏳ V6_Wolf (identity restore) — NEXT
- ⏳ V7_Preference (DPO via ultrafeedback-binarized) — NEXT
- ⏳ V8_GGUF (export Q4_K_M) — FINAL

**كل مرحلة جديدة = fresh training من base model (NO resume — Phase 11+ v2.7 lesson learned)**

**Environment:**
```bash
# RTX 5060 Ti (sm_120 - Blackwell) requires:
export XFORMERS_DISABLED=1
export UNSLOTH_DISABLE_XFORMERS=1

# Docker container: unsloth-alpha-wolf (Linux kernel avoids multiprocessing bugs)
docker start unsloth-alpha-wolf
```

**Training log per session (Iron Law #45):**
- Use `TRAINING_LOG_TEMPLATE.md` at `E:\Trained intelligence models\alpha-wolf\logs\`
- Or run: `python scripts/generate_training_log.py --version V{N}_{Name} --project "Alpha Wolf Agent"`

#### 2. **بعد Mix D: Mix E (Generalization)** — مرحلة جديدة
**Recommended approach (per Quхائد 2026-09-25):**
1. Train V_Generalization adapter with Mix E (8 datasets, diverse formats)
2. OR: Merge Mix D adapters + add Mix E → single V_Final adapter
3. Time: ~12 hours training

**Mix E dataset prep:**
```bash
# Use body/intake/ingestion_pipeline.py to download + clean datasets
python -c "
import sys
sys.path.insert(0, 'E:/Projects and systems managed by the team of experts/Alpha Wolf Agent')
from body.intake.ingestion_pipeline import IngestionPipeline
from pathlib import Path

pipeline = IngestionPipeline()

# Download + ingest Mix E datasets
datasets = [
    ('HuggingFaceH4/ultrachat_200k', 'train_sft', 50000, 'kb_chat'),
    ('glaiveai/glaive-function-calling-v2', None, 20000, 'kb_tools'),
    ('m-a-p/CodeFeedback-Filtered-Instruction', None, 20000, 'kb_code'),
    ('garage-bAInd/Open-Platypus', None, 25000, 'kb_instructions'),
    ('OpenAssistant/oasst1', None, 10000, 'kb_multi_turn'),
    ('teknium/OpenHermes-2.5', None, 50000, 'kb_general'),
    ('HuggingFaceH4/no_robots', None, 10000, 'kb_diverse'),
]

for repo_id, subset, max_rows, kb in datasets:
    result = pipeline.ingest_from_hf(repo_id, target_kb=kb)
    print(f'{repo_id}: {result[\"status\"]} - {result.get(\"rows_indexed\", 0)} rows')
"
```

#### 3. **بعد V_Final: GGUF Export**
```bash
model.save_pretrained_gguf(
    "E:/Trained intelligence models/alpha-wolf/V_Final",
    quantization_method="q4_k_m"
)
# Then llama-server:
llama-server -m V_Final-Q4_K_M.gguf --ctx-size 500000 --rope-scale 4 --port 8080
```

### 📜 Iron Laws في Force (45 Iron Laws — يجب احترامها كلها)

| # | Iron Law | Application in Training |
|---|----------|--------------------------|
| **#8** | 3-Expert Consensus | كل قرار معماري يحتاج 3 خبراء |
| **#9** | Tool/Server Problem Priority | RTX 5060 Ti sm_120 compatibility أولوية |
| **#13** | Self-Critical Check | كل ادعاء "تم" يحتاج verify |
| **#15** | Verify Before Claim | live test قبل ادعاء نجاح |
| **#17** | NO Ollama LLMs | embeddings فقط (nomic-embed-text), no text LLMs |
| **#19** | New Rules FIRST | أي directive جديد → governance أولاً |
| **#21** | NO Deletion | soft delete عبر deleted_at |
| **#22** | Autonomous Execution | لا تسأل "OK؟" للسهل |
| **#23** | Arabic Explanation | 6 أسطر عربية لكل اقتراح معماري |
| **#26** | Arabic Response | الردود بالعربية |
| **#27** | Continuous + Obstacle Removal | لا توقف بدون سبب |
| **#33** | Lessons → Code | كل خطأ → guardrail |
| **#36** | 5-Layer Save | كل تغيير → 5 layers |
| **#41** | Conflict Disclosure | تضارب مع Iron Law → اخبر القائد |
| **#42** | Workspace-Body Separation | body في workspace، لا تلمس E:\Agents\ |
| **#44** | Methodology 5 Gates | كل نموذج → 5 gates (MODEL_CARD, METHODOLOGY, PERSONALITY, DATA_STRATEGY, RISKS) |
| **#45** | Training Session Logging | كل training → log في 3 أماكن |
| **#46** | Model Caching & Reuse | Base model cached, NO re-download |

**للاطلاع الكامل:** `E:\Agents\The Expert Team\.opencode\knowledge\governance-protocol.md` (45 Iron Laws موثّقة)

### 📚 الملفات المهمة في المشروع (اقرأ بالترتيب)

| File | Path | Purpose |
|------|------|---------|
| **PROJECT_LOG.md** | `E:\Projects...\Alpha Wolf Agent\PROJECT_LOG.md` | كل ما تم + القرارات + الدروس |
| **PROJECT_PLAN.md** | `E:\Projects...\Alpha Wolf Agent\PROJECT_PLAN.md` | الخطة الكاملة (12 phase + Mix D + Mix E) |
| **body/SCHEMA.md** | `E:\Projects...\Alpha Wolf Agent\body\SCHEMA.md` | Self-documenting body blueprint |
| **body/README.md** | `E:\Projects...\Alpha Wolf Agent\body\README.md` | Operator manual |
| **body/GAPS_AND_PRIORITIES.md** | `E:\Projects...\Alpha Wolf Agent\body\GAPS_AND_PRIORITIES.md` | 16 gaps + priorities |
| **DATA_MINDMAP.html** | `E:\Projects...\Alpha Wolf Agent\DATA_MINDMAP.html` | Visual architecture (9 layers) |
| **body/alpha_wolf_body.py** | `E:\Projects...\Alpha Wolf Agent\body\alpha_wolf_body.py` | Main wrapper class |
| **body/init_body.py** | `E:\Projects...\Alpha Wolf Agent\body\init_body.py` | Body initialization |
| **body/intake/format_detector.py** | `E:\Projects...\Alpha Wolf Agent\body\intake\format_detector.py` | 8 formats auto-detect |
| **body/intake/ingestion_pipeline.py** | `E:\Projects...\Alpha Wolf Agent\body\intake\ingestion_pipeline.py` | Full ingestion pipeline |
| **ALPHA_WOLF_PERSONALITY.md** | `E:\Trained intelligence models\alpha-wolf\ALPHA_WOLF_PERSONALITY.md` | 7 Wolf traits |
| **ALPHA_WOLF_METHODOLOGY.md** | `E:\Trained intelligence models\alpha-wolf\ALPHA_WOLF_METHODOLOGY.md` | Mix D + NCE + 12 phases |
| **DATA_STRATEGY.md** | `E:\Trained intelligence models\alpha-wolf\DATA_STRATEGY.md` | Mix D dataset choices |
| **RISKS.md** | `E:\Trained intelligence models\alpha-wolf\RISKS.md` | VRAM, NaN, forgetting risks |
| **Mirror** | `E:\Agents\The Expert Team\.opencode\memory\projects\alpha-wolf-agent\` | نسخة mirror من كل الملفات |

### 🤝 قواعد Iron Law #43 — 6 أسطر عربية لكل اقتراح

عند اختيار أي model/dataset/hyperparameter، أنهِ الرد بـ **ست أسطر شرح بالعربية السهلة** تغطي:
1. الاسم
2. النوع
3. الحجم
4. لماذا نحتاجه
5. المخاطر
6. البديل

### ⚠️ خطوات يجب تنفيذها بشكل صحيح

1. **خطوة بخطوة** — لا تستبقوا الأحداث. كل خطوة تنتظرون قراري قبل التنفيذ.
2. **شرح بالعربي فقط** — اللغة الرسمية في التواصل معي.
3. **Body Integrity** — لا تكتبوا أي ملف في `E:\Agents\The Expert Team\` بدون موافقتي.
4. **Iron Law #42** — كل نماذج الذكاء في `D:\Intelligence Models\` فقط.
5. **Sequential Training** — كل dataset يُدرَّب لوحده (Mix D و Mix E).
6. **Backup قبل كل phase** — كل training session = نسخة احتياطية.
7. **Iron Law #45** — كل training session = log في 3 أماكن.
8. **Iron Law #46** — Base model cached, NO re-download.

### 📊 Success Criteria — كيف نعرف النجاح

Alpha Wolf Agent is DONE when:
- [ ] Mix D Sequential SFT phases complete (V0-V8)
- [ ] Mix E Generalization training (optional, if Quхائd approves)
- [ ] GGUF exported (Q4_K_M, ~5GB)
- [ ] llama.cpp server running (port 8080)
- [ ] FastAPI backend running (port 8001)
- [ ] Chainlit frontend running (port 8000)
- [ ] Body ingestion pipeline tested with real HF dataset
- [ ] Alpha Wolf can analyze unknown dataset (Tier 3 Code Execution)
- [ ] End-to-end test passes
- [ ] All Iron Laws respected

### 🎯 المهام الفورية (next 2 weeks)

1. ⏳ Mix D V3_Code → V4_Reflection → V5_Arabic → V6_Wolf → V7_Preference → V8_GGUF
2. ⏳ G2-G5: install missing dependencies + llama.cpp deploy
3. ⏳ End-to-end test (alpha wolf + body + llama.cpp + Chainlit)
4. ⏳ G6 (Already done in v3.1 — but integration test pending)
5. ⏳ Mix E (optional — per Quхائد decision)
6. ⏳ G7-G10: Security + tests

---

ابدأوا. اقرأوا الملفات أولاً (PROJECT_LOG + PROJECT_PLAN + body/SCHEMA + body/README + body/GAPS + DATA_MINDMAP)، ثم قدموا خطة واضحة لي (مع الست أسطر العربية لكل اقتراح).
```

---

## 📋 كيف تستخدمه

1. **انسخ النص الكامل** (بين ``` و ```)
2. **الصقه** في بداية محادثة جديدة مع الفريق
3. الفريق سيقرأ الملفات ويستجيب بخطة واضحة
4. اختر أنت (Mix E vs Mix D continue, Mix E timing, etc.)
5. الفريق ينفذ بعد موافقتك

---

## 🔗 الملفات المرتبطة في الـ prompt

| الملف | الموقع |
|---|---|
| `PROJECT_LOG.md` | `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\PROJECT_LOG.md` |
| `PROJECT_PLAN.md` | نفس المجلد |
| `body/SCHEMA.md` | `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\body\SCHEMA.md` |
| `body/README.md` | نفس الـ body |
| `body/GAPS_AND_PRIORITIES.md` | نفس الـ body |
| `DATA_MINDMAP.html` | `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\DATA_MINDMAP.html` |
| `governance-protocol.md` | `E:\Agents\The Expert Team\.opencode\knowledge\governance-protocol.md` |
| الـ Body mirror | `E:\Agents\The Expert Team\.opencode\memory\projects\alpha-wolf-agent\` |

---

## 📊 معلومات تقنية سريعة

| Resource | Value |
|----------|-------|
| **Model** | `unsloth/Meta-Llama-3.1-8B-Instruct` (4-bit, LoRA r=16, alpha=16) |
| **Method** | QLoRA (4-bit) |
| **max_seq_length** | 4096 (قاعدة صلبة) |
| **Mix D datasets** | UltraChat + glaive + CodeFeedback + Custom + Reflection |
| **Mix E datasets** | UltraChat + glaive + CodeFeedback + Open-Platypus + OASST + OpenHermes + no_robots + Custom |
| **Training scripts** | `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\scripts\` |
| **Trained models output** | `E:\Trained intelligence models\alpha-wolf\phase_X\` |
| **Training data** | `E:\Diverse data for training AI models\` |
| **Pretrained models** | `D:\Intelligence Models\` |
| **Unsloth Web UI** | http://localhost:7860 (logged in, Llama-3.1-8B-Instruct selected) |
| **Container name** | unsloth-alpha-wolf |
| **Output Model Path** | `E:\Trained intelligence models\alpha-wolf\` |
| **Body** | `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\body\` |
| **Body stack** | ChromaDB + NetworkX + SQLite + zvec (4-layer) |

## ⚠️ الحذر

- ❌ **لا تبدأوا Mix E قبل Mix D يكمل** — Quхائد قال "تابعوا Mix D أولاً ثم Mix E"
- ❌ لا تكتبوا في `E:\Agents\The Expert Team\` (body) بدون إذن صريح (Iron Law #42)
- ❌ لا تستبقوا قراراتي — انتظروا قراري على Mix E timing + custom domain
- ❌ **لا تحذفوا أي ملف** — Iron Law #21 (soft delete only)
- ❌ **لا تستخدموا Ollama LLMs** (qwen3, qwen2.5:*) — Iron Law #17 (embeddings فقط)

---

## 🐺 Iron Law #46 — Model Caching & Reuse

**القاعدة:** Base model (Llama-3.1-8B-Instruct, 2GB) **cached** في `D:\Intelligence Models\`. لا تعيد download أبداً.

**Verification:**
```bash
ls -la "D:\Intelligence Models\huggingface\hub\models--unsloth--Meta-Llama-3.1-8B-Instruct"
# Should show ~2GB cached
```

---

**أنشئ الـ prompt كملف جديد في الـ workspace + body mirror:**
- `E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\PROMPT_NEW_CHAT.md`
- `E:\Agents\The Expert Team\.opencode\memory\projects\alpha-wolf-agent\PROMPT_NEW_CHAT.md`