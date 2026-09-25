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

---

**Last updated:** 2026-09-25 (per Quхандд directive)

**Iron Laws Active:** 48 (#1-#48)
**Per Iron Law #47:** All English terms have Arabic explanations in parentheses
**Per Iron Law #48:** All phases are separated (مستقلة), not mixed (مختلطة)
