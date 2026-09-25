# 🐺 Alpha Wolf Agent

> **Last updated:** 2026-09-25
> **Status:** ✅ "طفره" Achieved (V8_Wolf = 100% eval)
> **License:** MIT (see `LICENSE`)
> **Base Model:** Llama-3.1-8B-Instruct (QLoRA 4-bit)

---

## 📖 Description

### English

**Alpha Wolf Agent** is a fine-tuned language model built on Llama-3.1-8B-Instruct
that embodies **7 Wolf traits**: mistake hunting, goal persistence, tenacity (failure
= data), deep thinking, resourcefulness, self-awareness, and reinforcement learning.
Trained using the **Separated Phases Plan** (خطة المراحل المستقلة) — each phase trains
one capability on its own dataset, then merges, with the **Identity (الهوية)** phase
always coming first to anchor the model's core self-concept before any capability
training. The breakthrough came with V8_Wolf: 100% evaluation score across all
7 Wolf traits + general knowledge, achieving القائد هشام's "طفره" goal.

### العربية

**Alpha Wolf Agent** هو نموذج لغوي مُعدَّل بدقة مبني على **Llama-3.1-8B-Instruct**
يتجسد فيه **سبع صفات للذئب**: اقتناص الأخطاء، تتبع الأهداف، الشراسة (الفشل =
بيانات)، التفكير العميق، استخدام الموارد بذكاء، الوعي الذاتي، والتعلم التعزيزي.
تُم تدريبه وفق **خطة المراحل المستقلة** (Separated Phases Plan) — كل مرحلة
تُدرَّب على قدرة واحدة بمجموعة بيانات خاصة بها، ثم تُدمج مع التقييم بين كل
مرحلة، مع **مرحلة الهوية** (Identity) دائماً في البداية لترسيخ المفهوم الذاتي
الأساسي للنموذج قبل أي تدريب على القدرات. جاءت الطفرة مع **V8_Wolf**: نتيجة
تقييم 100% عبر الصفات السبع للذئب + المعرفة العامة، محققةً هدف القائد هشام
"الطفره".

---

## 🚀 Quick Start

### English

1. **Verify your environment:**
   ```powershell
   python --version    # Python 3.11+
   nvidia-smi          # Check GPU (RTX 5060 Ti or better recommended)
   ```

2. **Install dependencies:**
   ```powershell
   pip install unsloth peft trl bitsandbytes
   pip install -r requirements.txt  # if present
   ```

3. **Load the model with the Wolf adapter:**
   ```python
   from unsloth import FastLanguageModel
   from peft import PeftModel

   model, tokenizer = FastLanguageModel.from_pretrained(
       "unsloth/Meta-Llama-3.1-8B-Instruct",
       max_seq_length=2048,
       load_in_4bit=True,
   )
   model = PeftModel.from_pretrained(
       model,
       "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf",
   )
   ```

4. **Test:**
   ```python
   prompt = "What is your name?"
   inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
   outputs = model.generate(**inputs, max_new_tokens=200)
   print(tokenizer.decode(outputs[0]))
   # Expected: "I am Alpha Wolf Agent. Like a wolf, I embody 7 traits..."
   ```

### العربية

1. **تأكد من بيئة التشغيل:**
   ```powershell
   python --version    # Python 3.11+
   nvidia-smi          # تحقق من GPU (يُفضل RTX 5060 Ti أو أفضل)
   ```

2. **تثبيت المكتبات:**
   ```powershell
   pip install unsloth peft trl bitsandbytes
   pip install -r requirements.txt  # إن وُجد
   ```

3. **تحميل النموذج مع ملف التعديل (Adapter):**
   ```python
   from unsloth import FastLanguageModel
   from peft import PeftModel

   model, tokenizer = FastLanguageModel.from_pretrained(
       "unsloth/Meta-Llama-3.1-8B-Instruct",
       max_seq_length=2048,
       load_in_4bit=True,
   )
   model = PeftModel.from_pretrained(
       model,
       "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf",
   )
   ```

4. **اختبار:**
   ```python
   prompt = "ما اسمك؟"
   inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
   outputs = model.generate(**inputs, max_new_tokens=200)
   print(tokenizer.decode(outputs[0]))
   # المتوقع: "أنا Alpha Wolf Agent. مثل الذئب، أتمتع بسبع صفات..."
   ```

---

## 🐺 Separated Phases Plan (خطة المراحل المستقلة)

> **Naming Note (2026-09-25):** "Mix D" was the original name; renamed to
> **"Separated Phases Plan"** (خطة المراحل المستقلة) per Iron Law #48 because each
> phase is SEPARATED (مستقل), not MIXED (مختلط).

### English

Each phase trains **one capability** on its own dataset, then evaluates. This avoids
**catastrophic forgetting** (النسيان الكارثي) — a well-known failure mode when
mixing multiple datasets in one training run.

### العربية

كل مرحلة تُدرَّب على **قدرة واحدة** بمجموعة بيانات خاصة بها، ثم تُقيَّم. هذا
يتجنب **النسيان الكارثي** — وهو نمط فشل معروف عند خلط مجموعات بيانات متعددة
في تشغيل واحد.

### Phase Status

| Phase | Name | Dataset | Eval | Status |
|-------|------|---------|------|--------|
| **0** | Storage + Infrastructure | — | — | ✅ Done |
| **0.5** | Unsloth Web UI Setup | — | — | ✅ Done |
| **1** | Data Curation | Bespoke, glaive, CodeFeedback, UltraChat | — | ✅ Done |
| **V0** | **Identity (الهوية)** | 106 hand-crafted Wolf examples | **51.2%** | ✅ Done |
| **V1** | Chat baseline | UltraChat 50k | **88%** | ✅ Done |
| **V2** | Tool Calling | glaive-function-calling | **71%** | ✅ Done |
| **V4** | Code | CodeFeedback | **86%** | ✅ Done |
| **V6** | Arabic Language | Arabic conversational data | — | ⏳ Not started |
| **V7** | Reflection Deep-Dive | Custom reflection patterns | — | ⏳ Not started |
| **V8** | **🐺 Wolf Restoration (الطفره!)** | 582 Wolf-focused examples (106 + 476 reflection) | **100%** ⭐ | ✅ Done |
| **V9** | DPO (Direct Preference Optimization) | Preference pairs | — | ⏳ Optional (not needed for طفره) |
| **V10** | GGUF Export | Adapter → GGUF | — | ⚠️ Failed (transformers v5.5 bug, adapter-only works) |

**Summary:** 5 of 9 phases complete (V0, V1, V2, V4, V8). The breakthrough phase
**V8_Wolf = 100% eval** achieved القائد's "طفره" goal.

---

## 📦 How to Use the Model (3 Deployment Options)

### English

| Option | Method | Status | When to Use |
|--------|--------|--------|-------------|
| **1. Unsloth Python API** | Load base + apply LoRA adapter in Python | ✅ Works now | Inference scripts, Jupyter notebooks, Python apps |
| **2. llama.cpp + LoRA adapter** | Convert adapter to GGUF, use llama-server | ✅ Works now | Local server, low-resource environments |
| **3. Ollama with Modelfile** | `ollama create alpha-wolf -f Modelfile` | ✅ Adapter path works | Local chat, simple CLI |

### العربية

| الخيار | الطريقة | الحالة | متى تُستخدم |
|--------|---------|--------|---------------|
| **1. Unsloth Python API** | تحميل النموذج الأساسي + تطبيق ملف LoRA في Python | ✅ يعمل الآن | سكربتات الاستدلال، Jupyter، تطبيقات Python |
| **2. llama.cpp + LoRA adapter** | تحويل Adapter إلى GGUF، استخدام llama-server | ✅ يعمل الآن | سيرفر محلي، بيئات منخفضة الموارد |
| **3. Ollama مع Modelfile** | `ollama create alpha-wolf -f Modelfile` | ✅ يعمل بمسار الـ adapter | محادثة محلية، CLI بسيط |

### Deployment Examples

**Option 1 — Unsloth Python (Production):**
```python
from unsloth import FastLanguageModel
from peft import PeftModel

base, tokenizer = FastLanguageModel.from_pretrained(
    "unsloth/Meta-Llama-3.1-8B-Instruct",
    max_seq_length=2048,
    load_in_4bit=True,
)
model = PeftModel.from_pretrained(
    base,
    "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf",
)
# Now chat with Alpha Wolf!
```

**Option 2 — llama.cpp + Adapter:**
```bash
# Convert adapter to GGUF (one-time)
python llama.cpp/convert-lora-to-ggml.py \
  E:/Trained\ intelligence\ models/alpha-wolf/adapters/v8_wolf \
  ./v8_wolf_adapter.gguf

# Run server
llama-server -m unsloth-meta-llama-3.1-8b-instruct.Q4_K_M.gguf \
  --lora v8_wolf_adapter.gguf \
  --port 8080
```

**Option 3 — Ollama (Easiest):**
```bash
# Modelfile already exists at:
#   E:\Trained intelligence models\alpha-wolf\models\Alpha_Wolf_Modelfile

ollama create alpha-wolf -f "E:/Trained intelligence models/alpha-wolf/models/Alpha_Wolf_Modelfile"
ollama run alpha-wolf
# >>> What is your name?
# I am Alpha Wolf Agent. Like a wolf, I embody 7 traits...
```

---

## 📖 Bilingual Glossary (قاموس ثنائي اللغة — Iron Law #47)

> **Rule:** Every English term throughout this project **MUST** have Arabic
> explanation in parentheses. This is Iron Law #47.
>
> **القاعدة:** كل مصطلح إنجليزي في هذا المشروع **يجب** أن يكون له شرح عربي بين قوسين. هذه هي القاعدة الحديدية رقم 47.

### Core ML Terms

| English | Arabic | Definition |
|---------|--------|------------|
| **LoRA (ملف صغير لتعديل النموذج)** | Low-Rank Adaptation | Trains small delta weights instead of full model (يدرب فروق صغيرة في الأوزان بدل النموذج كاملاً) |
| **Adapter (نفس LoRA - ملف التعديلات)** | — | Saved fine-tuned delta weights (الأوزان المُعدَّلة المحفوظة) |
| **QLoRA (LoRA مع التكميم 4-bit)** | Quantized LoRA | 4-bit base + LoRA adapters (~75% memory savings) (نموذج أساسي 4-بت + ملفات LoRA، توفير ~75% ذاكرة) |
| **Base Model (النموذج الأساسي)** | — | Pre-trained model we fine-tune (Llama-3.1-8B-Instruct) |
| **Fine-tuning (الضبط الدقيق)** | — | Training a pre-trained model on specific data (تدريب نموذج مسبق على بيانات محددة) |
| **Dataset (مجموعة بيانات)** | — | Collection of training examples (مجموعة أمثلة تدريب) |
| **Training (تدريب)** | — | Process of updating model weights (عملية تحديث أوزان النموذج) |
| **Loss (خسارة)** | — | Numerical measure of prediction error (مقياس رقمي لخطأ التنبؤ) |
| **Eval / Evaluation (تقييم)** | — | Testing model on held-out prompts (اختبار النموذج على أمثلة محجوزة) |
| **Checkpoint (نقطة حفظ)** | — | Saved model state during training (حالة النموذج المحفوظة أثناء التدريب) |

### Wolf Concepts

| English | Arabic | Definition |
|---------|--------|------------|
| **Wolf Trait (صفة الذئب)** | — | Behavioral pattern the model embodies (نمط سلوكي يتجسد في النموذج) |
| **Identity (الهوية)** | — | Core self-concept (name + personality) (المفهوم الذاتي الأساسي: الاسم + الشخصية) |
| **Tenacity (الشراسة / الإصرار)** | — | Refusal to abandon goal after failure (رفض التخلي عن الهدف بعد الفشل) |
| **Mistake Hunting (اقتناص الأخطاء)** | — | Proactive error detection (كشف الأخطاء الاستباقي) |
| **Reflection (التأمل الذاتي)** | — | Model analyzes its own output (النموذج يحلل مخرجاته) |
| **Self-Aware (الوعي الذاتي)** | — | Knows its limits and capabilities (يعرف حدوده وقدراته) |
| **Reinforcement Learning (التعلم التعزيزي)** | — | Learning from feedback rewards (التعلم من مكافآت التغذية الراجعة) |

### Deployment Terms

| English | Arabic | Definition |
|---------|--------|------------|
| **Ollama (برنامج تشغيل النماذج محلياً)** | — | Local LLM runtime (بيئة تشغيل النماذج محلياً) |
| **Modelfile (ملف إعدادات Ollama)** | — | Ollama configuration file (ملف إعدادات Ollama) |
| **GGUF (تنسيق النموذج)** | — | Quantized model format for llama.cpp (تنسيق نموذجي مكمم لـ llama.cpp) |
| **llama.cpp (مكتبة استدلال C++)** | — | C++ inference engine (محرك استدلال بـ C++) |
| **Unsloth (إطار عمل تدريب مُحسَّن)** | — | Optimized fine-tuning library (مكتبة ضبط مُحسَّنة) |
| **VRAM (ذاكرة GPU)** | — | GPU memory in GB (ذاكرة معالج الرسوميات بـ GB) |
| **Quantization (التكميم)** | — | Reduce precision to save memory (تقليل الدقة لتوفير الذاكرة) |
| **Docker Container (حاوية Docker)** | — | Isolated Linux runtime (بيئة تشغيل لينكس معزولة) |
| **CUDA (كودا)** | — | NVIDIA GPU compute library (مكتبة حوسبة NVIDIA للمعالج الرسومي) |

---

## 📁 Project Structure

```
Alpha Wolf Agent/
├── README.md                    ← This file
├── LICENSE                      ← MIT license (English + Arabic summary)
├── .gitignore                   ← Excludes models, logs, env, etc.
├── PROJECT_LOG.md               ← Complete history of all phases
├── PROJECT_PLAN.md              ← Forward-looking plan
│
├── docs/                        ← All documentation (5 Iron Law #44 Gates)
│   ├── PERSONALITY.md           ← Gate 3: Wolf 7 traits
│   ├── METHODOLOGY.md           ← Gate 2: Separated Phases methodology
│   ├── MODEL_CARD.md            ← Gate 1: Base model research
│   ├── DATA_STRATEGY.md         ← Gate 4: Data acquisition & sequencing
│   └── RISKS.md                 ← Gate 5: Risk assessment + backup plans
│
├── backend/                     ← FastAPI backend (TBD)
├── frontend/                    ← Streamlit/Chainlit Web UI (TBD)
├── scripts/                     ← Training + data + utility scripts
├── backups/                     ← Snapshots before risky operations
├── logs/                        ← Training + eval + download logs
└── body/                        ← Body mirror for cross-session persistence

External paths (NOT in this repo):
├── E:\Trained intelligence models\alpha-wolf\
│   ├── adapters/v8_wolf/        ← Production LoRA adapter (164 MB)
│   ├── models/Alpha_Wolf_Modelfile  ← Ollama config
│   └── eval/                    ← Evaluation results
│
└── E:\Diverse data for training AI models\
    └── (datasets used for training)
```

---

## 📚 Important File Links

### Within This Project

| File | Purpose | Link |
|------|---------|------|
| **PROJECT_LOG.md** | Complete history of all phases (1290 lines) | [`PROJECT_LOG.md`](PROJECT_LOG.md) |
| **PROJECT_PLAN.md** | Forward-looking plan + decisions | [`PROJECT_PLAN.md`](PROJECT_PLAN.md) |
| **docs/PERSONALITY.md** | Wolf 7 traits + Arabic explanations | [`docs/PERSONALITY.md`](docs/PERSONALITY.md) |
| **docs/METHODOLOGY.md** | Separated Phases training methodology | [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) |
| **docs/MODEL_CARD.md** | Llama-3.1-8B research + specs | [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) |
| **docs/DATA_STRATEGY.md** | Data acquisition + sequencing | [`docs/DATA_STRATEGY.md`](docs/DATA_STRATEGY.md) |
| **docs/RISKS.md** | Risk assessment + backup plans | [`docs/RISKS.md`](docs/RISKS.md) |
| **LICENSE** | MIT License (English + Arabic summary) | [`LICENSE`](LICENSE) |
| **.gitignore** | Excluded files (models, logs, env) | [`.gitignore`](.gitignore) |

### Body Mirror (for cross-session continuity)

The full team AGENTS.md is mirrored at:
```
E:\Agents\The Expert Team\.opencode\memory\projects\alpha-wolf-agent\
├── PROJECT_LOG.md      ← Project log mirror
├── PROJECT_PLAN.md     ← Project plan mirror
├── AGENTS.md           ← Team AGENTS.md snapshot (2026-09-18)
└── (other project files)
```

The body mirror follows **Iron Law #36** (5-Layer Save Protocol):
**AGENTS.md** → **memory/** → **KB** → **per-expert memory** → **code guardrails**.

### Training Logs

All training sessions have dedicated logs (Iron Law #45 — Training Session Logging Protocol):
- `TRAINING_LOG_V0_IDENTITY.md` — V0 Identity (106 Wolf examples)
- `TRAINING_LOG_V1_CHAT.md` — V1 Chat baseline (UltraChat)
- `TRAINING_LOG_V2_TOOLS.md` — V2 Tool calling (glaive)
- `TRAINING_LOG_V4_CODE.md` — V4 Code (CodeFeedback)
- `TRAINING_LOG_V8_Wolf.md` — V8 Wolf restoration (582 examples) ⭐

Located in `E:\Trained intelligence models\alpha-wolf\logs\`.

---

## 🛠️ Iron Laws Applied

This project follows the team's **Iron Law protocol** (currently 48 active laws):

| Iron Law | Application in Alpha Wolf |
|----------|---------------------------|
| **#44 — Model Development Methodology** | 5 Gates: MODEL_CARD → METHODOLOGY → PERSONALITY → DATA_STRATEGY → RISKS (all in `docs/`) |
| **#45 — Training Session Logging** | Every training has a dedicated log file |
| **#46 — Model Caching & Reuse** | Zero downloads after initial pull (all training uses cached base) |
| **#47 — Bilingual Glossary** | Every English term has Arabic explanation |
| **#48 — Separated Concerns (مستقل)** | Each phase trains one capability on its own dataset |

---

## 📊 Final Result Summary

| Metric | Value |
|--------|-------|
| **Total phases complete** | 5 of 9 (V0, V1, V2, V4, V8) |
| **Best eval score** | **100% (V8_Wolf)** 🏆 |
| **Adapter size** | 164 MB (production-ready) |
| **Base model** | Llama-3.1-8B-Instruct (QLoRA 4-bit) |
| **Training data** | ~60,000 examples across 4 datasets |
| **Goal achievement** | ✅ "طفره" (breakthrough) achieved |
| **Iron Laws followed** | 48 active (incl. #44, #45, #46, #47, #48) |

---

## 👤 Ownership

**Owner:** القائد هشام (Alpha Wolf Project)
**Started:** 2026-09-23
**Last updated:** 2026-09-25
**Status:** ✅ Production-ready V8_Wolf adapter

For questions or contributions, see `PROJECT_LOG.md` for the full decision history.

---

## 🔗 Related Resources

- **Base Model:** [Llama-3.1-8B-Instruct on HuggingFace](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)
- **Unsloth Framework:** [github.com/unslothai/unsloth](https://github.com/unslothai/unsloth)
- **Team AGENTS.md:** `E:\Agents\The Expert Team\AGENTS.md` (main team memory, 5800+ lines)

---

> **Last Edit:** 2026-09-25 — Documentation organized per Quхائد directive.
> All documentation follows Iron Laws #47 (Bilingual Glossary) and #48 (Separated Concerns).
