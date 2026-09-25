#!/usr/bin/env python3
"""
Resume V2_Tools training from checkpoint-500 to ~step 1000.

Per Quхائd directive (500-step batch verification).
Per Iron Law #46: Base model cached, zero download.
Per Iron Law #45: Training log maintained.
Per Iron Law #15: Verified xformers fix in this version.
"""

import os
os.environ["XFORMERS_DISABLED"] = "1"
os.environ["UNSLOTH_DISABLE_XFORMERS"] = "1"

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
RESUME_FROM_CHECKPOINT = "/workspace/v2_tools/checkpoint-500"  # Use this as starting point
OUTPUT_DIR = "/workspace/v2_tools_resumed"

DATASET_PATH = "/workspace/glaive_20k.jsonl"
TARGET_EXAMPLES = 20000
MAX_SEQ_FILTER = 12288

MAX_SEQ_LENGTH = 4096
LORA_R = 16
LORA_ALPHA = 32
LEARNING_RATE = 2e-4
NUM_EPOCHS = 2
BATCH_SIZE = 2
GRAD_ACCUM = 4
SAVE_STEPS = 500

WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""


def load_glaive(path, n_examples):
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if len(examples) >= n_examples:
                break
            try:
                ex = json.loads(line)
                msgs = ex.get("messages", [])
                total_len = sum(len(m.get("content", "")) for m in msgs)
                if total_len > MAX_SEQ_FILTER or total_len < 100:
                    continue
                if not any(m["role"] == "user" for m in msgs):
                    continue
                if not any(m["role"] == "assistant" for m in msgs):
                    continue
                examples.append({"messages": msgs})
            except Exception:
                continue
    return examples


def train():
    print("=" * 70)
    print("V2_TOOLS RESUMED — Continue from checkpoint-500")
    print("=" * 70)

    print(f"\n[1/5] Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    print(f"\n[2/5] Base model (CACHED) + Load checkpoint-500 as trainable...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    # Load checkpoint-500 adapter (CONTINUE from step 500)
    model = PeftModel.from_pretrained(
        model, RESUME_FROM_CHECKPOINT, is_trainable=True
    )
    print(f"  [OK] Loaded checkpoint-500 as trainable. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    print(f"\n[3/5] Dataset (same as before)...")
    raw = load_glaive(DATASET_PATH, TARGET_EXAMPLES)
    dataset = Dataset.from_list(raw)

    def apply_template(ex):
        text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": text}
    dataset = dataset.map(apply_template, remove_columns=["messages"])

    print(f"\n[4/5] Setting up training with resume_from_checkpoint...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=dataset,
        dataset_text_field="text", max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=0,  # Skip warmup (already trained 500 steps)
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

    print(f"\n[5/5] Training (resume from step 500, target ~1000)...")
    start = time.time()
    # Resume: trainer reads checkpoint-500 state, starts from step 500
    try:
        train_result = trainer.train(resume_from_checkpoint=True)
        elapsed = time.time() - start
        print(f"\n[OK] Done in {elapsed:.1f}s | Final loss: {train_result.training_loss:.4f}")
    except Exception as e:
        print(f"\n[WARN] Resume failed: {e}")
        print("  Falling back to continue training without optimizer state...")
        # Reset just optimizer
        del trainer
        torch.cuda.empty_cache()
        train_result = trainer.train()
        elapsed = time.time() - start
        print(f"\n[OK] Continue-trained in {elapsed:.1f}s | Final loss: {train_result.training_loss:.4f}")

    # Save adapter
    print(f"\nSaving adapter...")
    adapter_out = f"{OUTPUT_DIR}/adapter_step1000"
    os.makedirs(adapter_out, exist_ok=True)
    model.save_pretrained(adapter_out)
    tokenizer.save_pretrained(adapter_out)
    print(f"  [OK] Saved to {adapter_out}")

    del trainer, model
    torch.cuda.empty_cache()
    return train_result.training_loss, elapsed


if __name__ == "__main__":
    try:
        loss, t = train()
        print(f"\nFinal: loss={loss:.4f}, time={t:.1f}s")
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
