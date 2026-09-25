#!/usr/bin/env python3
"""
Auto-generate Training Log template for any training session.

Per Iron Law #45 (Training Session Logging Protocol).
This script auto-creates the log structure so training scripts don't forget.

Usage:
    python generate_training_log.py --version V1_Chat --project "Alpha Wolf Agent"
    python generate_training_log.py --version V1_Chat --project "Alpha Wolf Agent" --complete

The --complete flag generates a COMPLETED training log (filled with results).
Without it, generates a STARTER template.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path


def generate_training_log(version, project, complete=False, results=None):
    """Generate a training log file with timestamped name."""

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M")
    date_human = now.strftime("%Y-%m-%d %H:%M")

    run_id = f"{version}_{timestamp}"

    if complete and results:
        overall_score = results.get("overall_score", "X")
        tests_passed = results.get("tests_passed", "X")
        total_tests = results.get("total_tests", "X")
        status = "✅ COMPLETE"
        verdict_summary = f"Eval: {overall_score}% ({tests_passed}/{total_tests} tests passed)"
    else:
        status = "🔴 IN PROGRESS"
        verdict_summary = "[Will be filled after completion]"

    content = f"""# 📋 Training Session Log — {version}

> **Per Iron Law #45 (Training Session Logging Protocol)**
> **Owner:** expert-llm-trainer + Quхائд
> **Date Created:** {date_human}
> **Status:** {status}

---

## 📊 Training Summary

| Field | Value |
|-------|-------|
| **Project** | {project} |
| **Phase** | [PHASE_NUMBER]: [PHASE_NAME] |
| **Training Run ID** | `{run_id}` |
| **Date/Time** | {date_human} (start) → [END_TIME] (end) |
| **Duration** | [X] seconds (~[X] min) |
| **Status** | {status} |
| **Trained by** | expert-specialist |
| **Reviewed by** | Quхائд هشام |
| **Verdict** | {verdict_summary} |

---

## ⚙️ Configuration

### Base Model
| Field | Value |
|-------|-------|
| **Model** | `[org]/[model-name]` |
| **Size** | [X]B parameters |
| **Quantization** | 4-bit (bnb) / 8-bit / FP16 |
| **Context Window** | [X] (reduced for [TASK]) |
| **VRAM Required** | [X] GB |

### LoRA Adapter
| Field | Value | Rationale |
|-------|-------|-----------|
| **r** | 16 | Standard |
| **alpha** | 32 | 2×r (Unsloth recommendation) |
| **dropout** | 0.05 | Light regularization |
| **target_modules** | q,k,v,o + gate,up,down (7/7) | Full coverage |
| **Trainable Params** | [X] / [X] ([X]%) | |

### Training Hyperparameters
| Field | Value | Rationale |
|-------|-------|-----------|
| Epochs | [X] | [reason] |
| Batch Size | 2 | 4-bit enables 2 in 16GB |
| Gradient Accumulation | 4 | Effective batch = 8 |
| Learning Rate | 2e-4 | Unsloth QLoRA default |
| LR Scheduler | cosine | |
| Warmup Steps | 5 | |
| Weight Decay | 0.01 | |
| Max Seq Length | [X] | [reason] |
| Optimizer | adamw_8bit | |
| Gradient Checkpointing | "unsloth" | Saves ~30% memory |

### Dataset
| Field | Value |
|-------|-------|
| **Path** | [PATH] |
| **Format** | ChatML JSONL |
| **Total Examples** | [X] |
| **Length Range** | [X]-[X] chars |
| **Categories** | [list] |

### Training Environment
| Field | Value |
|-------|-------|
| **Container** | `[container-name]` (Docker) |
| **PyTorch** | [version] |
| **CUDA** | [version] |
| **GPU** | [model] |
| **Unsloth** | [version] |

---

## 📈 Training Progress

### Loss Curve

| Step | Epoch | Loss | Grad Norm | Learning Rate |
|------|-------|------|-----------|----------------|
| [FILL] | | | | |

### Loss Statistics
| Metric | Value |
|--------|-------|
| Initial loss | [X] |
| Final loss | **[X]** |
| **Loss decrease** | **[X]%** |
| **No NaN spikes** | ✅ / ❌ |
| Monotonic decrease | ✅ / ⚠️ / ❌ |

### Performance Metrics
| Metric | Value |
|--------|-------|
| Total steps | [X] |
| Train samples/sec | [X] |
| Peak VRAM | [X] GB |
| Final loss (avg) | [X] |

---

## 💾 Output Files

### Adapter (Saved)
| File | Size |
|------|------|
| `adapter_model.safetensors` | [X] MB |
| `adapter_config.json` | [X] KB |
| `tokenizer.json` | [X] MB |
| `tokenizer_config.json` | [X] KB |
| `chat_template.jinja` | [X] KB |

**Locations:**
- Container: `/workspace/[path]`
- Local: `[LOCAL_PATH]`

### GGUF Export
| Status | ✅ Done / ⚠️ Skipped / ❌ Failed |
|--------|------|
| Reason (if skipped) | [reason] |

### Evaluation Results
| Field | Value |
|-------|-------|
| **Overall Score** | **[X]% ([X]/[X])** |

| Trait | Score |
|-------|-------|
| [trait 1] | **[X]%** ✅ / ⚠️ |
| [trait 2] | **[X]%** ✅ / ⚠️ |

---

## ❌ Mistakes Encountered (Anti-Patterns to Avoid)

### Mistake N: [Title]

**What happened:**
[Description]

**Lesson:**
- ❌ [What NOT to do]
- ✅ [What to do instead]

**Prevention:**
- [Action item]

---

## 💡 Lessons Learned (For Future Training)

1. [Lesson 1]
2. [Lesson 2]
3. [Lesson 3]

---

## 🎯 Recommended Next Steps

### Short-Term
1. [Next step 1]
2. [Next step 2]

### Medium-Term
3. [Step 3]

### Long-Term
4. [Step 4]

---

## 📂 Files Created

| File | Status |
|------|--------|
| `[script]` | ✅ Created |
| `[adapter]` | ✅ Saved |
| `[results]` | ✅ Saved |
| `logs/TRAINING_LOG_{version}.md` | ✅ THIS FILE |

---

## 🏆 Verdict

**Iron Law #15 (Verify Before Claim): [PASS/FAIL]**

- [X] evaluation tests run
- [X] of [X] passed ([X]%)
- Loss decreased [X]% ([X] → [X])
- No NaN spikes
- Adapter saved successfully

**Iron Law #44 (Methodology): [PASS/PARTIAL]**

- [notes]

**Iron Law #45 (Training Log): [PASS]**

- This log created before/during/after training
- Saved in 3 locations: project logs/ + PROJECT_LOG.md + expert-llm-trainer.md memory

**Iron Law #22 (Autonomous): [PASS]**

- [notes]

---

**Last updated:** {date_human}
**Next training session:** TBD (Quхائд decision)

## Training Session ID
{run_id}
"""

    # Output path
    project_safe = project.replace(" ", "_").replace("/", "_")
    filename = f"TRAINING_LOG_{version}_{timestamp}.md"

    # Try to find project logs directory (with case-insensitive matching)
    possible_paths = [
        Path(f"E:\\Trained intelligence models\\alpha-wolf\\logs"),  # Known Alpha Wolf location (FIRST!)
        Path(f"E:\\Trained intelligence models\\{project_safe}\\logs"),
        Path(f"E:\\Projects and systems managed by the team of experts\\{project}\\logs"),
        Path(f"E:\\Projects and systems managed by the team of experts\\Alpha Wolf Agent\\logs"),
    ]

    output_dir = None
    for path in possible_paths:
        try:
            path.mkdir(parents=True, exist_ok=True)
            output_dir = path
            break
        except (OSError, PermissionError):
            continue

    if not output_dir:
        # Fallback: current working directory
        output_dir = Path.cwd() / "logs"
        output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate training log template (Iron Law #45)")
    parser.add_argument("--version", required=True, help="Model version (e.g., V0_Identity, V1_Chat)")
    parser.add_argument("--project", required=True, help="Project name (e.g., 'Alpha Wolf Agent')")
    parser.add_argument("--complete", action="store_true", help="Mark as complete (add results)")
    parser.add_argument("--overall-score", help="Overall eval score (with --complete)")
    parser.add_argument("--tests-passed", help="Tests passed count (with --complete)")
    parser.add_argument("--total-tests", help="Total tests count (with --complete)")

    args = parser.parse_args()

    results = None
    if args.complete:
        results = {
            "overall_score": args.overall_score or "X",
            "tests_passed": args.tests_passed or "X",
            "total_tests": args.total_tests or "X"
        }

    output_path = generate_training_log(args.version, args.project, args.complete, results)

    print(f"[OK] Training log created: {output_path}")
    print(f"[INFO] Fill in the [FILL] / [X] placeholders as training progresses")
    print(f"[INFO] Per Iron Law #45, save in 3 locations:")
    print(f"  1. Project logs/ (this file)")
    print(f"  2. PROJECT_LOG.md (entry)")
    print(f"  3. expert-llm-trainer.md memory (lessons learned)")


if __name__ == "__main__":
    main()
