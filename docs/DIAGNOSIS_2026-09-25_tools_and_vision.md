# تشخيص مشاكل Alpha Wolf Agent — 2026-09-25 (Diagnosis — أدوات + رؤية)

> **الحالة:** تم الفحص المباشر (Live Verification) — Iron Law #15
> **النتيجة:** أدوات Alpha Wolf سليمة 100% — مشكلة الـ Vision من اختيار الموديل في الجلسة

## 1. الأدوات (Tools) — سليمة ✅

### فحص مباشر بتاريخ 2026-09-25:
- `GET /v1/body/health` → **200 OK**
  - chromadb: ok (13 collections)
  - sqlite: ok (16 tables, integrity ok, 0.26 MB)
  - zvec: ok
  - body size: 3.87 MB
- `GET /v1/tools` → **200 OK** — **9 tools تعمل:**
  1. read_file (filesystem)
  2. write_file (filesystem)
  3. list_directory (filesystem)
  4. execute_python (compute)
  5. search_files (filesystem)
  6. web_search (network)
  7. grep_in_files (filesystem)
  8. query_body_kb (knowledge)
  9. index_project (knowledge)
- `backend_start.log` → Tools injected + RAG injected + Ollama 200 OK + chat/completions 200 OK
- `frontend_test_screenshot.png` → الشات يعمل: "What is your name?" → "I am Alpha Wolf Agent..."

### ملاحظة عن `frontend_test.log`:
- الملف يحتوي سطر واحد: `NO_SEND_BUTTON` — هذا log قديم (Stale) من اختبار سابق
- الـ Screenshot الحديث يثبت أن زر الإرسال والشات يعملان الآن
- **لا حاجة لإصلاح Frontend** — يعمل فعلياً

## 2. خطأ الصورة (Vision Error) — سبب وحل ⚠️

### الخطأ:
```
ERROR: Cannot read "image.png" (this model does not support image input)
```

### السبب الجذري (Root Cause):
- الجلسة الحالية تستخدم: `opencode/muse-spark-1.3-contributor-free`
- هذا الموديل: `attachment: false` + `modalities.input: ["text"]` — **نص فقط، لا يفهم الصور**
- OpenCode يرفض الصورة قبل ما توصل لأي خبير (Runtime Rejection)

### الموديلات التي تفهم الصور (Vision-Capable — مؤكدة في opencode.json):
| الموديل | النوع | التكلفة |
|---------|-------|---------|
| `minimax-330/minimax-M3` | PAID PRIMARY (attachment:true + image) | مدفوع |
| `minimax-330/minimax-text-01` | PAID vision (138 API calls verified) | مدفوع |
| `ollama/qwen2.5vl:7b` | LOCAL vision | مجاني محلي |
| `ollama/gemma4:latest` | LOCAL vision heavy | مجاني محلي |
| `google/gemini-2.5-flash` | FREE cloud vision | مجاني سحابي |
| `openrouter/meta-llama/llama-3.2-90b-vision-instruct:free` | FREE vision | مجاني |

### الحل (خطوة واحدة — من القائد):
1. في واجهة OpenCode — افتح قائمة الموديلات (Dropdown)
2. اختر `minimax-330/minimax-M3` (أو أي موديل من الجدول أعلاه)
3. أعد إرسال الصورة — ستعمل بدون خطأ
4. ملاحظة: يجب **إعادة التشغيل الكامل** لـ OpenCode بعد تغيير الموديل (Session Cache)

## 3. Rate Limit للخبراء (Subagents Too Many Requests)
- استدعاء `expert-analyst` فشل بـ `Too Many Requests` — MiniMax quota مؤقت
- تم التفعيل البديل per Iron Law #18/#27: تحليل Inline + فحص Disk مباشر
- لا تأثير على Alpha Wolf — هذا يخص فريق الخبراء فقط

## 4. الخلاصة
- ✅ Alpha Wolf Backend: يعمل (9 tools + RAG + Ollama + ChromaDB)
- ✅ Alpha Wolf Frontend: يعمل (Screenshot يثبت)
- ⚠️ Vision Error: غيّر الموديل من القائمة — ليس عطل في المشروع
- ⚠️ Expert Subagents: Rate Limit مؤقت — سيعود تلقائياً

---
*بواسطة فريق الخبراء — Specialist Inline (بسبب Rate Limit) — Iron Laws #13/#15/#22/#26/#42*
*Body Boundary: هذا الملف في Workspace (مسموح) — لم يُمس Body الفريق*
