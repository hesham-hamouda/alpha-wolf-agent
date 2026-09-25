#!/usr/bin/env python3
"""
Resume V1_Chat training from checkpoint-500 to step 1000.

Per Quхائد directive 2026-09-24: 500-step batch verification strategy.
Per Iron Law #46: Base model CACHED (zero download).
Per Iron Law #45: Training log auto-managed.
"""

import os
import sys
import json
import time
import torch
from datasets import Dataset

import unsloth
import unsloth_zoo

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments, AutoTokenizer
from peft import PeftModel

# Configuration
BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
RESUME_FROM_CHECKPOINT = "/workspace/v1_chat/checkpoint-500"  # Load this adapter
OUTPUT_DIR = "/workspace/v1_chat_resumed"

DATASET_PATH = "/workspace/ultrachat_50k.jsonl"
TARGET_EXAMPLES = 10000
MAX_SEQ_FILTER = 8192

MAX_SEQ_LENGTH = 4096
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LEARNING_RATE = 2e-4
NUM_EPOCHS = 2
BATCH_SIZE = 2
GRAD_ACCUM = 4
SAVE_STEPS = 500

WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""


def load_ultrachat(path, n_examples):
    """Load UltraChat JSONL."""
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if len(examples) >= n_examples:
                break
            try:
                ex = json.loads(line)
                msgs = ex.get("messages", [])
                total_len = sum(len(m.get("content", "")) for m in msgs)
                if total_len > MAX_SEQ_FILTER or total_len < 20:
                    continue

                new_msgs = [{"role": "system", "content": WOLF_SYSTEM}]
                for m in msgs:
                    role = m.get("role", "").lower()
                    content = m.get("content", "")
                    if role in ["user", "assistant"] and content:
                        new_msgs.append({"role": role, "content": content})
                if len(new_msgs) >= 3:
                    examples.append({"messages": new_msgs})
            except Exception:
                continue
    print(f"[OK] Loaded {len(examples)} examples")
    return examples


def train_resume():
    print("=" * 70)
    print("V1_CHAT RESUMED — Continue from checkpoint-500")
    print("=" * 70)

    # Tokenizer
    print(f"\n[1/4] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    # Load base + EXISTING adapter (from checkpoint-500)
    print(f"\n[2/4] Loading base model + adapter from {RESUME_FROM_CHECKPOINT}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    # Load EXISTING adapter (already trained 500 steps)
    model = PeftModel.from_pretrained(model, RESUME_FROM_CHECKPOINT, is_trainable=True)
    print(f"  [OK] Resumed from {RESUME_FROM_CHECKPOINT}. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    # Dataset (fresh - same as before)
    print(f"\n[3/4] Loading dataset (same as before, target {TARGET_EXAMPLES})...")
    raw = load_ultrachat(DATASET_PATH, TARGET_EXAMPLES)
    dataset = Dataset.from_list(raw)

    def apply_template(ex):
        text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": text}
    dataset = dataset.map(apply_template, remove_columns=["messages"])

    # Resume training
    print(f"\n[4/4] Resuming training (continue to step ~1000)...")
    print(f"  Note: Trainer will use existing optimizer state from checkpoint-500")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=dataset,
        dataset_text_field="text", max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=0,  # Skip warmup (already done)
            num_train_epochs=NUM_EPOCHS,
            learning_rate=LEARNING_RATE,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=20,
            weight_decay=0.01,
            output_dir=OUTPUT_DIR,
            save_strategy="steps",
            save_steps=SAVE_STEPS,
            report_to="none",
            save_total_limit=1,
            resume_from_checkpoint=True,  # KEY: Resume from checkpoint-500
        ),
    )

    start = time.time()
    train_result = trainer.train(resume_from_checkpoint=True)
    elapsed = time.time() - start

    print(f"\n[OK] Resumed training done in {elapsed:.1f}s")
    print(f"  Final loss: {train_result.training_loss:.4f}")
    print(f"  Peak VRAM: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")

    # Save resumed adapter
    print("\nSaving resumed adapter...")
    adapter_out = f"{OUTPUT_DIR}/adapter_at_1000"
    os.makedirs(adapter_out, exist_ok=True)
    model.save_pretrained(adapter_out)
    tokenizer.save_pretrained(adapter_out)
    print(f"  [OK] Saved to {adapter_out}")

    del trainer, model
    torch.cuda.empty_cache()

    return train_result.training_loss, elapsed


if __name__ == "__main__":
    try:
        loss, t = train_resume()
        print(f"\nFinal: loss={loss:.4f}, time={t:.1f}s")
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
