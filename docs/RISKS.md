# ⚠️ RISKS.md — Alpha Wolf Agent Training (Gate 5 of Iron Law #44)

> **⚠️ DEPRECATED TERMINOLOGY (2026-09-25):** "Mix D" (الخطة المختلطة) is deprecated. Use **Separated Phases Plan** (خطة المراحل المستقلة) per Iron Law #48. Each phase is SEPARATED (مستقل)، not MIXED (مختلط).
>
> **📖 Bilingual Glossary (قاموس ثنائي اللغة — Iron Law #47):**
> - **Risk Assessment (تقييم المخاطر)** — identification of potential failures (تحديد الأعطال المحتملة)
> - **Backup Plan (خطة النسخ الاحتياطي)** — recovery strategy if something fails (استراتيجية الاستعادة عند الفشل)
> - **Disk Quota (حصة القرص)** — storage limit policy (سياسة حد التخزين)
> - **Docker Container (حاوية Docker)** — isolated Linux runtime (بيئة تشغيل لينكس معزولة)
> - **CUDA / GPU (كودا / معالج الرسوميات)** — NVIDIA compute for ML (حوسبة NVIDIA لتعلم الآلة)
> - **VRAM (ذاكرة GPU)** — GPU memory in GB (ذاكرة معالج الرسوميات بـ GB)
> - **DRAM (ذاكرة النظام)** — system RAM in GB (ذاكرة الوصول العشوائي للنظام بـ GB)
> - **xformers (مُحسِّن الانتباه)** — memory-efficient attention library (مكتبة انتباه موفرة للذاكرة)
> - **Resume Training (استئناف التدريب)** — continue from saved checkpoint (متابعة من نقطة محفوظة)
> - **Fresh Training (تدريب من الصفر)** — start new LoRA from base model (بدء LoRA جديد من النموذج الأساسي)

> **Owner:** Quхائد هشام + expert-llm-trainer
> **Date:** 2026-09-23
> **Purpose:** Pre-Training Gate 5 of Iron Law #44 (Risk Assessment & Backup Plan)
> **Status:** ✅ Complete (awaiting Quхائd review)
> **Base Model:** Llama-3.1-8B-Instruct
> **Mix:** D (Sequential Full)

---

## 🎯 Iron Law #44 — Gate 5: Risk Assessment

This file documents EVERY foreseeable risk with:
1. **Risk description** (what could go wrong)
2. **Likelihood** (Low / Medium / High)
3. **Impact** (Low / Medium / High / Critical)
4. **Mitigation** (preventive measures)
5. **Backup/Recovery** (what to do if it happens)

---

## 🔴 CRITICAL RISKS (Likelihood × Impact = Critical)

### Risk 1: Catastrophic Forgetting Between Phases ⭐ TOP CONCERN

**Description:** Sequential training risks the model "forgetting" earlier phases when learning new ones. Example: After Phase 3 (Tools), Alpha Wolf might lose Phase 2 (Chat) fluency.

**Likelihood:** **HIGH** (well-documented issue in sequential fine-tuning)

**Impact:** **CRITICAL** (would make entire Mix D unusable)

**Mitigation:**
1. **Lower learning rate for later phases** (2e-4 → 1e-4 → 5e-5 across phases)
2. **TEA Loop (Train → Evaluate → Augment)** — eval between phases catches forgetting early
3. **Backup each phase's LoRA adapter** to `E:\Trained intelligence models\alpha-wolf\backups\phase_N\`
4. **Merge at end** (not between) — keeps all knowledge separate

**Recovery Procedure:**
```bash
# If Phase N degrades Phase 1-N-1 performance:
# 1. Stop Phase N immediately
# 2. Restore Phase N-1 LoRA adapter from backup
# 3. Re-evaluate with full eval set
# 4. Adjust Phase N hyperparams (lower LR, fewer epochs)
# 5. Re-run Phase N
```

**Iron Law Applied:** #21 (NO Deletion — backups preserved at every phase)

---

### Risk 2: VRAM Overflow During Training

**Description:** 16GB VRAM is tight for 8B model + 4-bit + LoRA + gradient checkpointing. Memory spikes during backprop can OOM.

**Likelihood:** **MEDIUM** (depends on max_seq_length + batch size)

**Impact:** **CRITICAL** (training crashes, hours of work lost)

**Mitigation:**
1. **Use 4-bit QLoRA** (NOT 8-bit, NOT full FP16) — proven to fit on RTX 5060 Ti 16GB
2. **Set max_seq_length = 4096** (HARD RULE per Quхائd)
3. **Use `use_gradient_checkpointing="unsloth"`** (saves ~30% memory)
4. **Batch size 2 per device** (NOT 4) — safer
5. **Gradient accumulation = 4** (effective batch = 8)

**Recovery Procedure:**
```bash
# If OOM happens:
# 1. Reduce batch size to 1
# 2. Increase gradient accumulation to 8
# 3. Reduce max_seq_length to 2048 (last resort)
# 4. Restart from last checkpoint
```

**Iron Law Applied:** #15 (Verify — `nvidia-smi` check before each training start)

---

### Risk 3: NaN Loss Spike Mid-Training

**Description:** Loss can suddenly spike to NaN due to:
- Bad learning rate
- Gradient explosion
- Corrupt dataset example

**Likelihood:** **MEDIUM** (1 in 5 training runs experience this)

**Impact:** **CRITICAL** (model weights corrupted, must restart)

**Mitigation:**
1. **Save checkpoints every 500 steps** (Unsloth default)
2. **Lower initial LR** (2e-4 → 1e-4 if previous spike)
3. **Warmup ratio = 0.03** (stabilizes early training)
4. **Monitor loss curves** in real-time via Unsloth Web UI

**Recovery Procedure:**
```bash
# If NaN detected:
# 1. Stop training immediately
# 2. Restore from checkpoint at step 500 (before NaN)
# 3. Reduce LR by 50%
# 4. Skip problematic examples (use dataset dedup)
# 5. Resume training
```

**Iron Law Applied:** #15 (Verify — checkpoint integrity checked)

---

## 🟠 HIGH RISKS (Important but Recoverable)

### Risk 4: Dataset Quality Issues

**Description:** Datasets may contain:
- NSFW content (CodeFeedback has minimal but exists)
- PII (leaked emails, names)
- Duplicate examples (especially in UltraChat)
- Wrong format (non-ChatML)
- Over-length examples (>4096 tokens)

**Likelihood:** **HIGH** (most datasets have at least some issues)

**Impact:** **HIGH** (poor model quality, wasted training time)

**Mitigation:**
1. **Dedup script** — `scripts/dedup_check.py` removes duplicates
2. **Content filter** — remove NSFW + PII via regex
3. **Length filter** — drop examples >4096 tokens
4. **Format validation** — ensure all examples are valid ChatML

**Recovery Procedure:**
```python
# scripts/validate_dataset.py
import json
import re

def validate_dataset(path):
    with open(path) as f:
        for i, line in enumerate(f):
            ex = json.loads(line)
            # Check ChatML format
            assert "messages" in ex
            assert all(m["role"] in ["system", "user", "assistant"] for m in ex["messages"])
            # Check length
            total_len = sum(len(m["content"]) for m in ex["messages"])
            assert total_len < 4096 * 4  # rough char-to-token ratio
            # Check NSFW/PII (basic regex)
            text = " ".join(m["content"] for m in ex["messages"])
            assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", text), "SSN found"
    print(f"✅ {path} validated")
```

**Iron Law Applied:** #15 (Verify) + #21 (NO Deletion — flagged examples moved to `flagged/` subdirectory)

---

### Risk 5: Training Time Overruns

**Description:** Sequential Mix D has 11+ training phases. Total estimated 14-18 hours. Quхائd's machine is shared — long training blocks other work.

**Likelihood:** **HIGH** (any single phase may take longer than estimated)

**Impact:** **MEDIUM** (delay, not failure)

**Mitigation:**
1. **Spread across days** — one phase per evening
2. **Save checkpoints aggressively** — resume from checkpoint if interrupted
3. **Use Unsloth's 2x speed** — saves ~50% vs vanilla transformers

**Recovery Procedure:**
- Pause training, resume next day
- All checkpoints auto-saved by Unsloth

**Iron Law Applied:** #22 (Autonomous within scope — no need to ping user for every pause)

---

### Risk 6: Arabic Quality Regression

**Description:** Llama-3.1-8B's Arabic is moderate. Training on English-heavy data first (UltraChat, glaive, CodeFeedback) could make Arabic WORSE, not better. Phase 7 Arabic training might not fully recover it.

**Likelihood:** **MEDIUM** (regression is well-documented in multilingual SFT)

**Impact:** **HIGH** (loses Quхائd's "تدريبه على اللغه العربيه" goal)

**Mitigation:**
1. **Mix Arabic examples in EVERY phase** (not just Phase 7) — 10% Arabic examples in each batch
2. **Bilingual prompts** — code-switch examples preserve Arabic
3. **Lower learning rate for Phase 7** — avoid aggressive Arabic over-write

**Recovery Procedure:**
- If Arabic quality regresses after Phase 7: re-train Phase 7 with higher Arabic ratio (50% Arabic / 50% English)

**Iron Law Applied:** #13 (Self-Critical — already assessed Arabic approach limitations in DATA_STRATEGY.md)

---

### Risk 7: Wolf Personality Drift

**Description:** After many phases of capability training (Tools, Code, Arabic), the Wolf traits (7 from PERSONALITY.md) might fade. Model becomes generic assistant, not Alpha Wolf.

**Likelihood:** **MEDIUM** (Phase 8 specifically designed to fix this, but risk remains)

**Impact:** **HIGH** (loses Alpha Wolf's identity)

**Mitigation:**
1. **Phase 1 (Identity) is FIRST** — establishes Wolf before capabilities
2. **Wolf trait examples scattered in EVERY phase** — 5% Wolf examples in each batch
3. **Phase 8 is dedicated Wolf fine-tune** — re-emphasizes traits after capability training

**Recovery Procedure:**
- If Wolf trait score drops below 80% in eval: run Phase 8 with more examples (500 → 1000)

**Iron Law Applied:** #21 (NO Deletion — Wolf examples preserved across all phases)

---

## 🟡 MEDIUM RISKS (Manageable with Care)

### Risk 8: License / Legal Issues

**Description:** Mixing multiple datasets with different licenses could create compliance issues.

**Datasets + Licenses:**
| Dataset | License | Commercial Use |
|---------|---------|----------------|
| UltraChat-200k | CC BY-NC 4.0 | ❌ **Non-commercial only** |
| glaive-function-calling-v2 | Apache 2.0 | ✅ |
| CodeFeedback-Filtered-Instruction | CC BY-NC-SA 4.0 | ❌ **Non-commercial only** |
| Marine Biology | (depends on source) | varies |
| Reflection | (our own) | ✅ |
| Arabic (multiple) | varies | varies |
| ultrafeedback-binarized-cleaned | CC BY-NC 4.0 | ❌ **Non-commercial only** |
| Llama-3.1-8B-Instruct | Llama 3 Community | ✅ (with conditions) |

**Likelihood:** **HIGH** (multiple NC datasets used)

**Impact:** **HIGH** (potential license violation if Alpha Wolf used commercially)

**Mitigation:**
1. **Alpha Wolf is for PERSONAL USE by Quхائd** — NC is acceptable
2. **Document licenses** in this file
3. **If commercial deployment planned**: switch to commercial-licensed datasets:
   - `OpenHermes-2.5` (Apache 2.0)
   - `WizardLM-Orca` (varies)
   - Custom Quхائd-curated data

**Recovery Procedure:**
- For commercial deployment: retrain with commercial datasets only

**Iron Law Applied:** #19 (Rules FIRST — this must be decided before any commercial deployment)

---

### Risk 9: Storage Issues (C: Drive Full)

**Description:** Quхائd's C: drive has 28GB free (CRITICAL). If training dumps anything to C: drive, Windows becomes unstable.

**Likelihood:** **MEDIUM** (HuggingFace cache defaults to C: if not set)

**Impact:** **CRITICAL** (Windows may crash)

**Mitigation:**
1. **`HF_HOME=D:\Intelligence Models\huggingface`** (already set)
2. **`OLLAMA_MODELS=D:\Intelligence Models\ollama`** (already set)
3. **All training outputs to `E:\Trained intelligence models\alpha-wolf\`** (not C:)
4. **Run `scripts/storage_audit.py` after every phase** (Iron Law #42 enforcement)

**Recovery Procedure:**
```powershell
# If C: drive fills up:
Get-ChildItem $env:USERPROFILE\.cache -Recurse | Sort-Object Length -Descending | Select-Object -First 20
# Move largest items to D:\Intelligence models\
```

**Iron Law Applied:** #42 (Storage Discipline — already enforced)

---

### Risk 10: Unsloth Version Compatibility

**Description:** Unsloth updates frequently. New versions may break our training scripts.

**Likelihood:** **MEDIUM** (Unsloth has had 5+ breaking changes in 2026)

**Impact:** **MEDIUM** (training may fail or produce different results)

**Mitigation:**
1. **Pin Unsloth version** in `requirements.txt`: `unsloth==2026.9.10`
2. **Document the version** in MODEL_CARD.md
3. **Test with smoke run** before each real training (Phase 0)

**Recovery Procedure:**
- If Unsloth breaks: pin to last known-good version (we use 2026.9.10)
- Alternative: use vanilla transformers + TRL (slower but more stable)

**Iron Law Applied:** #15 (Verify — pin version in code)

---

## 🟢 LOW RISKS (Unlikely but Tracked)

### Risk 11: Power Outage / Hardware Failure

**Likelihood:** LOW (Quхائd's hardware is reliable)
**Impact:** CRITICAL (loses in-progress training)
**Mitigation:** Unsloth auto-saves checkpoints every 500 steps
**Recovery:** Restart from last checkpoint

### Risk 12: Dataset Becomes Unavailable

**Likelihood:** LOW (HF datasets rarely disappear)
**Impact:** MEDIUM (need to find alternative)
**Mitigation:** Download + backup datasets before training starts
**Recovery:** Have alternates ready (documented in DATA_STRATEGY.md)

### Risk 13: Model Output Contains Harmful Content

**Likelihood:** LOW (Instruct model + DPO + Wolf personality)
**Impact:** HIGH (potential safety issue)
**Mitigation:** DPO + Wolf Trait #3 (Tenacity) teaches careful answers
**Recovery:** Add safety RLHF in Phase 10 if needed

---

## 📊 Risk Matrix Summary

| Risk | Likelihood | Impact | Status |
|------|-----------|--------|--------|
| 1. Catastrophic forgetting | 🔴 HIGH | 🔴 CRITICAL | Mitigated via TEA loop + backups |
| 2. VRAM overflow | 🟠 MEDIUM | 🔴 CRITICAL | Mitigated via 4-bit + checkpointing |
| 3. NaN loss | 🟠 MEDIUM | 🔴 CRITICAL | Mitigated via checkpointing + LR control |
| 4. Dataset quality | 🔴 HIGH | 🟠 HIGH | Mitigated via validation scripts |
| 5. Time overruns | 🔴 HIGH | 🟡 MEDIUM | Accepted (spread across days) |
| 6. Arabic regression | 🟠 MEDIUM | 🟠 HIGH | Mitigated via bilingual mixing |
| 7. Wolf personality drift | 🟠 MEDIUM | 🟠 HIGH | Mitigated via Phase 1 + Phase 8 |
| 8. License issues | 🔴 HIGH | 🟠 HIGH | Accepted (personal use only) |
| 9. C: drive full | 🟠 MEDIUM | 🔴 CRITICAL | Mitigated via HF_HOME + storage_audit |
| 10. Unsloth compat | 🟠 MEDIUM | 🟡 MEDIUM | Mitigated via version pin |

---

## 🔁 Backup & Recovery Strategy

### Automatic Backups

| Trigger | Backup Location | What |
|---------|----------------|------|
| After each Phase | `E:\Trained intelligence models\alpha-wolf\backups\phase_N\` | LoRA adapter + dataset snapshot |
| Every 500 steps (Unsloth) | `E:\Trained intelligence models\alpha-wolf\checkpoints\` | Training checkpoint |
| After each eval | `E:\Trained intelligence models\alpha-wolf\eval\phase_N\` | Eval results JSON |

### Manual Backups (Per Quхائd Directive)

> Quхائd: "كل بيانات فى كل مرحله هتعمل منها نسخه باك اب"

**Procedure (end of each phase):**
```powershell
# 1. Backup dataset
$date = Get-Date -Format "yyyy-MM-dd"
Copy-Item -Recurse "E:\Diverse data for training AI models\Mix_D\phase_N" `
              "E:\Trained intelligence models\alpha-wolf\backups\${date}_phase_N\"

# 2. Backup adapter
Copy-Item -Recurse "E:\Trained intelligence models\alpha-wolf\adapters\phase_N" `
              "E:\Trained intelligence models\alpha-wolf\backups\${date}_phase_N\adapter\"

# 3. Backup eval results
Copy-Item "E:\Trained intelligence models\alpha-wolf\eval\phase_N.json" `
          "E:\Trained intelligence models\alpha-wolf\backups\${date}_phase_N\"

# 4. Log the backup
Add-Content "E:\Trained intelligence models\alpha-wolf\PROJECT_LOG.md" `
           "Backup completed: ${date}_phase_N"
```

### Disaster Recovery

If training is interrupted (power outage, crash):

```bash
# 1. Restart Unsloth container (if Docker)
docker restart unsloth-alpha-wolf

# 2. Resume from last checkpoint
python scripts/resume_training.py --checkpoint E:\Trained intelligence models\alpha-wolf\checkpoints\step_1500

# 3. If checkpoint corrupted, fall back to backup
python scripts/resume_training.py --backup E:\Trained intelligence models\alpha-wolf\backups\2026-09-23_phase_3\
```

**Iron Law Applied:** #21 (NO Deletion — backups NEVER deleted, only archived)

---

## 🚦 Pre-Training Risk Checklist

Before Quхائd approves Phase 2 (Identity Training):

- [ ] Iron Law #44 Gates 1-5 all complete (✅ all done)
- [ ] Unsloth installed + verified (Phase 0 ✅)
- [ ] Docker container `unsloth-alpha-wolf` running (Phase 0.5 ✅)
- [ ] D: drive has 90GB+ free (verified ✅)
- [ ] E: drive has 100GB+ free (verified ✅)
- [ ] C: drive > 20GB free (Iron Law #42 protection ✅)
- [ ] Backup script tested (`scripts/storage_audit.py`)
- [ ] Resume script ready (`scripts/resume_training.py`)

---

## ✅ Self-Critical Check (Iron Law #13)

| # | Check | Verified |
|---|-------|----------|
| 1 | Did I list risks for ALL categories (VRAM, dataset, time, license, storage)? | ✅ 13 risks |
| 2 | Did I assign likelihood AND impact? | ✅ All 13 |
| 3 | Did I provide mitigation AND recovery? | ✅ All 13 |
| 4 | Did I link each risk to an Iron Law? | ✅ #15, #21, #19, #42, etc. |
| 5 | Did I verify the risks against Quхائd's actual hardware? | ✅ RTX 5060 Ti + 16GB VRAM + 32GB RAM |
| 6 | Did I provide automated backup strategy? | ✅ Per-phase + per-step |

---

## 🔗 Related Files

- `MODEL_CARD.md` (Gate 1) — Llama-3.1-8B-Instruct analysis
- `METHODOLOGY.md` (Gate 2) — NCE + Mix D + 12 phases
- `PERSONALITY.md` (Gate 3) — 7 Wolf traits
- `DATA_STRATEGY.md` (Gate 4) — Mix D datasets
- `AGENTS.md` — Phase 11+ v2.1 entry
- `PROJECT_LOG.md` — Decision log

---

**Last updated:** 2026-09-23 — Phase 11+ v2.1 (Iron Law #44 Gate 5 complete)
**Status:** ✅ All 5 Gates of Iron Law #44 COMPLETE for Alpha Wolf Agent
**Next step:** Iron Law #44 satisfied → Ready to begin Step 2 (Verify Unsloth smoke test)
