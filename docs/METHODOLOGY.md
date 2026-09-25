# 🐺 Alpha Wolf Agent — Training Methodology (Gate 2 of Iron Law #44)

> **⚠️ DEPRECATED TERMINOLOGY (2026-09-25):** "Mix D" (الخطة المختلطة) is deprecated. Use **Separated Phases Plan** (خطة المراحل المستقلة) per Iron Law #48. Each phase is SEPARATED (مستقل)، not MIXED (مختلط).
>
> **📖 Bilingual Glossary (قاموس ثنائي اللغة — Iron Law #47):**
> - **LoRA (ملف صغير لتعديل النموذج)** — Low-Rank Adaptation, trains small delta weights (تكيف منخفض الرتبة، يدرّب فروق صغيرة في الأوزان)
> - **Adapter (نفس LoRA - ملف التعديلات)** — saved fine-tuned delta weights (الأوزان المعدّلة المحفوظة)
> - **QLoRA (LoRA مع التكميم 4-bit)** — quantized base model + LoRA adapters (نموذج أساسي مكمّم + ملفات LoRA)
> - **Base Model (النموذج الأساسي)** — pre-trained model we fine-tune (النموذج المسبق التدريب الذي نعدّله)
> - **Training Phase (مرحلة تدريب)** — SEPARATED execution of one dataset (تنفيذ مستقل لمجموعة بيانات واحدة)
> - **Fresh Training (تدريب من الصفر)** — new LoRA from base model (ملف LoRA جديد من النموذج الأساسي)
> - **Catastrophic Forgetting (النسيان الكارثي)** — model loses old knowledge when learning new (النموذج ينسى معلومات قديمة عند تعلم جديدة)
> - **QLoRA 4-bit (تكميم 4-بت)** — reduce memory by ~75% with minor quality loss (تقليل الذاكرة ~75% مع فقد جودة بسيط)
> - **Unsloth (إطار عمل تدريب مُحسَّن)** — optimized fine-tuning library (مكتبة ضبط مُحسَّنة)

> **Owner:** Quхائد هشام + expert-llm-trainer
> **Source:** Quхائd approval 2026-09-23: **Mix D (Sequential Full)** ⭐
> **Goal:** Document the complete training methodology BEFORE first training run
> **Base Model:** `unsloth/Meta-Llama-3.1-8B-Instruct` (QLoRA 4-bit)

---

## 🎯 Iron Law #44 — Gate 2: Methodology Definition

This file **MUST exist** before any SFT/DPO training.
It documents: methodology choice, hyperparameter rationale, sequencing, validation.

---

## 📋 Recommended Mix: **Mix D (Sequential Full)** ⭐

Quхائd-approved 2026-09-23: **40% UltraChat + 20% glaive + 20% CodeFeedback + 10% Custom + 10% Reflection**

### All Mix Options Considered (per Iron Law #41 — full disclosure)

| Mix | Composition | Pros | Cons | Risk Level |
|-----|-------------|------|------|-----------|
| **A** | 30% Reasoning + 20% Tool + 20% Self-Correct + 20% Multi-Turn + 10% Custom | Covers all capabilities | ⚠️ Mixed in single pass → catastrophic forgetting | 🟠 Medium |
| **B** | 50% UltraChat + 25% glaive + 15% CodeFeedback + 10% Custom | Safer (3 datasets) | Missing reflection, identity training | 🟡 Low |
| **C** | 50% UltraChat + 30% glaive + 20% Custom | Fast MVP | 🚫 Weak capabilities | 🟢 Low (limited) |
| **D ⭐** | 40% UltraChat + 20% glaive + 20% CodeFeedback + 10% Custom (Marine) + 10% Reflection | **Sequential + Identity-first + Custom + Reflection = complete** | ⏱️ Time 14-18hr | 🟢 LOWEST (sequenced) |

**Quхائd's choice 2026-09-23:** Mix D ✅
**Why Mix D wins (Self-Critical Analysis per Iron Law #13)**:
- Covers **chat + tools + code + custom domain + reflection** = 5 capability layers
- Custom (Marine Biology) fits Quхائd's available collection
- Reflection dataset (= self-correction) matches Wolf trait #3 (Tenacity)
- Sequential (not mixed) prevents catastrophic forgetting

---

## 🧬 Neural Curriculum Evolution (NCE) — The Methodology

> **"نمتد من الحجم بصغر البيانات الذكية"**
> We compensate for small model size with smart data, not brute force.

### The 12 Sequential Phases (Mix D)

```
PHASE 0: Verify Unsloth Works (smoke test, 10min)
    ↓
PHASE 1: Identity (V0_Identity — Wolf personality, 30min)
    ↓
PHASE 2: Chat Baseline (V1_Chat — UltraChat 200k sub-50k, 2-3hr)
    ↓
PHASE 3: Tool Calling (V2_Tools — glaive-function-calling-v2, 1-2hr)
    ↓
PHASE 4: Code (V3_Code — CodeFeedback sub-30k, 2-3hr)
    ↓
PHASE 5: Reasoning (V4_Reason — Bespoke-Stratos optional, 2-3hr)
    ↓
PHASE 6: Reflection (V5_Reflection — synthetic self-correction, 1hr)
    ↓
PHASE 7: Arabic (V6_Arabic — Arabic SFT data, 2-3hr)
    ↓
PHASE 8: Wolf Personality Fine-tune (V7_Wolf — wolf-specific, 1hr)
    ↓
PHASE 9: DPO Preference (V8_Preference — ultrafeedback-binarized, 2-3hr)
    ↓
PHASE 10: Behavior DPO (V9_Behavior — custom pairs, 1hr)
    ↓
PHASE 11: GGUF Export + Deploy (V10_Production, 30min)
```

**Total estimated time:** 14-18 hours (modular — can spread across days)

### TEA Loop (Train → Evaluate → Augment) — Between Phases

```python
def tea_loop(model, eval_set, current_phase):
    """
    Critical: every phase has TEA loop to target failures.
    Quхائd: target failures, not blind repetition.
    """
    # 1. EVAL — 20 custom Alpha Wolf prompts
    failures = []
    for prompt, expected in eval_set:
        output = model.generate(prompt)
        score = evaluate(output, expected)
        if score < 0.7:  # failure threshold
            failures.append({"prompt": prompt, "output": output, "expected": expected})

    # 2. AUGMENT — generate 100-500 examples for failures
    if failures:
        augmented_data = generate_targeted_examples(
            failures=failures,
            count=200,
            generation_method="ollama_local_llama3.1"
        )
        jsonl_path = f"v{current_phase}_augmented.jsonl"
        write_jsonl(jsonl_path, augmented_data)
        log_action(f"Created {jsonl_path} with {len(augmented_data)} targeted examples")

    # 3. NEXT PHASE — load augmented set
    return load_training_set(f"v{current_phase}_augmented.jsonl")
```

**Why TEA > Pure Training:**
- Catches "blind spots" in dataset
- Continuous improvement
- No overfitting on same data

---

## 📊 Hyperparameter Recommendations

### Standard Mix D Defaults (Llama-3.1-8B-Instruct + QLoRA)

| Hyperparameter | Recommended Value | Rationale |
|----------------|-------------------|-----------|
| **LoRA r** | 16 | Sweet spot for 8B (not too aggressive, not too weak) |
| **LoRA alpha** | 32 (= 2×r) | Unsloth's recommended 2:1 ratio |
| **LoRA dropout** | 0.05 | Light regularization (some datasets need 0.1) |
| **Target modules** | q, k, v, o + gate, up, down (7/7) | Full coverage for deep adaptation |
| **Learning rate** | 2e-4 | Unsloth QLoRA default for new models |
| **LR scheduler** | cosine | Stabilizes final training |
| **Batch size** | 2 (per device) | 4-bit enables 2 in 16GB VRAM |
| **Gradient accumulation** | 4 | Effective batch = 8 |
| **Max seq length** | 4096 (hard rule) | Per Quхائd |
| **Epochs** | 2 (large datasets) / 3 (small) | Standard; 4+ risks over-fit |
| **Warmup ratio** | 0.03 | Stable start |
| **Weight decay** | 0.01 | Light regularization |
| **Quantization** | 4-bit QLoRA | Required for 16GB VRAM |
| **Optimizer** | adamw_8bit | Memory-efficient |

### Per-Phase Adjustments

| Phase | Adjustment | Reason |
|-------|------------|--------|
| **Identity (Phase 1)** | Epochs 4-5 (small dataset) | Need reinforcement of identity |
| **Chat (Phase 2)** | Epochs 2 (UltraChat is large) | Avoid overfit |
| **Tools (Phase 3)** | Epochs 3, learning rate 1e-4 | Slow learning for tool format |
| **Code (Phase 4)** | Epochs 2-3 | Code is structure-heavy |
| **Arabic (Phase 7)** | Epochs 3, learning rate 3e-4 (slightly higher) | Language learning needs more |

---

## 🌍 Data Strategy (Gate 4 of Iron Law #44)

See `DATA_STRATEGY.md` for full details.

**Summary:**
- **Chat**: UltraChat 200k (sub-50k)
- **Tools**: glaive-function-calling-v2
- **Code**: CodeFeedback (sub-30k)
- **Custom**: Marine biology (Quхائд's collection)
- **Arabic**: Mixed Arabic SFT (3-5k examples)
- **Reflection**: Synthetic self-correction
- **Identity**: 7 Wolf traits (200-500 examples per `ALPHA_WOLF_PERSONALITY.md`)
- **DPO**: ultrafeedback-binarized-cleaned

---

## ⚠️ Risks (Gate 5 of Iron Law #44)

See `RISKS.md` for full details.

**Top 3 Risks for Mix D:**

| # | Risk | Likelihood | Mitigation |
|---|------|-----------|-------------|
| 1 | **Catastrophic forgetting between phases** (sequential risk) | Medium | TEA loop catches; backup V_N before V_N+1 |
| 2 | **VRAM overflow during backprop** | Low | 4-bit QLoRA = ~10GB peak (safe under 16GB) |
| 3 | **Arabic regression** (English over-fits Arabic) | Medium | Mix Arabic with English examples; bounded LR |

---

## 📂 File Structure (Mix D Output)

```
E:\Trained intelligence models\alpha-wolf\
├── ALPHA_WOLF_PERSONALITY.md        # ← exists (Wolf 7 traits)
├── ALPHA_WOLF_METHODOLOGY.md         # ← THIS FILE (Mix D + NCE)
├── MODEL_CARD.md                     # Llama-3.1-8B-Instruct capabilities
├── DATA_STRATEGY.md                  # Mix D composition + Arabic
├── RISKS.md                          # VRAM, NaN, forgetting
│
├── adapters/                         # LoRA adapters (one per phase)
│   ├── v0_identity/                  # Wolf personality
│   ├── v1_chat/
│   ├── v2_tools/
│   ├── v3_code/
│   ├── v4_reason/                    # optional
│   ├── v5_reflection/
│   ├── v6_arabic/
│   ├── v7_wolf/
│   ├── v8_preference/                # DPO
│   └── v9_behavior/                  # DPO
│
├── models/                           # GGUF output (full model)
│   ├── v1_chat/
│   ├── v2_tools/
│   └── ...
│
├── checkpoints/                      # Training checkpoints (every 500 steps)
├── logs/                             # Training logs (loss curves)
├── augmented_data/                   # TEA-generated data per phase
│   ├── v1_chat_augmented.jsonl
│   └── ...
└── eval/                             # Phase evaluation results
    ├── v1_chat_results.json
    └── ...
```

---

## ✅ Quality Gates Per Phase

| Gate | Check | If Fails |
|------|-------|----------|
| **Loss Convergence** | Training loss < 1.0 within 80% of max_steps | Lower LR or more epochs |
| **Eval Score** | 20-prompt eval ≥ 70% accuracy | TEA augmentation |
| **Bilingual** | Arabic accuracy ≥ 50% after Phase 7 | More Arabic data |
| **Wolf Trait Presence** | Test 7 traits in chat — each returns wolf response | More identity data |

---

## 🔗 Related Files

- `ALPHA_WOLF_PERSONALITY.md` — 7 wolf traits + identity data structure
- `MODEL_CARD.md` (to be created) — Llama-3.1-8B-Instruct analysis
- `DATA_STRATEGY.md` (to be created) — Mix D dataset choices
- `RISKS.md` (to be created) — full risk register

---

**Last updated:** 2026-09-23 — Phase 11+ Mix D approved by Quхائd
**Next step:** Create `MODEL_CARD.md` (Gate 1) + `DATA_STRATEGY.md` (Gate 4) + `RISKS.md` (Gate 5)
**Status:** Methodology approved; 3 of 5 gates documented; awaiting Phase 2 (Identity Training) user approval
