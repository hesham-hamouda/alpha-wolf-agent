#!/usr/bin/env python3
"""
Continue V2_Tools training (simpler approach):
- Load checkpoint-500 adapter weights (already trained 500 steps)
- Train 500 more steps on same LoRA layers (no optimizer resume)
- Per Iron Law #45: Save log after completion

This is "continue training" (not true resume) but achieves the same effect
since SFTTrainer supports is_trainable adapter.
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

BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
RESUME_FROM_CHECKPOINT = "/workspace/v2_tools/checkpoint-500"
OUTPUT_DIR = "/workspace/v2_tools_continue"

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


def main():
    print("=" * 70)
    print("V2_TOOLS CONTINUE — Same LoRA, no optimizer resume")
    print("=" * 70)

    print(f"\n[1/4] Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    print(f"\n[2/4] Base + checkpoint-500 adapter (continue training)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
        attn_implementation="eager",  # Force eager attention (avoid xformers sm_120 incompatibility)
    )
    # Load existing adapter (peft will keep it; we just train more)
    model = PeftModel.from_pretrained(model, RESUME_FROM_CHECKPOINT, is_trainable=True)
    print(f"  [OK] Resume point: step 500. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    print(f"\n[3/4] Dataset (same as before)...")
    raw = load_glaive(DATASET_PATH, TARGET_EXAMPLES)
    dataset = Dataset.from_list(raw)

    def apply_template(ex):
        text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": text}
    dataset = dataset.map(apply_template, remove_columns=["messages"])

    print(f"\n[4/4] Training (500 more steps to reach ~step 1000)...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Use max_steps instead of epochs to control exactly 500 steps
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=dataset,
        dataset_text_field="text", max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=0,
            max_steps=500,  # Train exactly 500 more steps
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
            optim="adamw_8bit",
        ),
    )

    start = time.time()
    train_result = trainer.train()
    elapsed = time.time() - start

    print(f"\n[OK] Trained 500 more steps in {elapsed:.1f}s | Final loss: {train_result.training_loss:.4f}")
    print(f"  Peak VRAM: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")

    # Save adapter
    adapter_out = f"{OUTPUT_DIR}/adapter_step1000"
    os.makedirs(adapter_out, exist_ok=True)
    model.save_pretrained(adapter_out)
    tokenizer.save_pretrained(adapter_out)
    print(f"  [OK] Final adapter saved to {adapter_out}")

    del trainer, model
    torch.cuda.empty_cache()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
