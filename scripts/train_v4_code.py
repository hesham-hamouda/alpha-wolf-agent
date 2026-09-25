#!/usr/bin/env python3
"""
V4_Code Training — Mix D Phase 4 — Code Specialization
FRESH from base (no resume — per lesson learned).
Uses CodeFeedback-Filtered-Instruction (30k examples).

Per Iron Law #46: Base model CACHED (no download).
Per Iron Law #45: Training log maintained.
Per Iron Law #33 (lesson learned): Fresh training only, no PeftModel loading.
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


BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
DATASET_PATH = "/workspace/codefeedback_30k.jsonl"
OUTPUT_DIR = "/workspace/v4_code"
ADAPTER_DIR = f"{OUTPUT_DIR}/adapter"

MAX_SEQ_LENGTH = 4096
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LEARNING_RATE = 2e-4
NUM_EPOCHS = 2
BATCH_SIZE = 2
GRAD_ACCUM = 4
SAVE_STEPS = 500


def load_codefeedback(path, n_examples):
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if len(examples) >= n_examples:
                break
            try:
                ex = json.loads(line)
                msgs = ex.get("messages", [])
                if not msgs:
                    continue
                examples.append({"messages": msgs})
            except Exception:
                continue
    return examples


def train():
    print("=" * 70)
    print("V4_CODE TRAINING — Mix D Phase 4 (Code)")
    print("FRESH from base (lesson learned — no resume)")
    print("=" * 70)

    print(f"\n[1/4] Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    print(f"\n[2/4] Base model + new LoRA (FRESH)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
    )
    print(f"  [OK] VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    print(f"\n[3/4] Dataset (30k CodeFeedback examples)...")
    raw = load_codefeedback(DATASET_PATH, 30000)
    dataset = Dataset.from_list(raw)

    def apply_template(ex):
        text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": text}
    dataset = dataset.map(apply_template, remove_columns=["messages"])
    print(f"  [OK] {len(dataset)} examples ready")

    print(f"\n[4/4] Training ({NUM_EPOCHS} epochs, ~{len(dataset)//(BATCH_SIZE*GRAD_ACCUM)*NUM_EPOCHS} steps)...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=dataset,
        dataset_text_field="text", max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=10,
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
        ),
    )

    start = time.time()
    train_result = trainer.train()
    elapsed = time.time() - start

    print(f"\n[OK] Done in {elapsed:.1f}s | Final loss: {train_result.training_loss:.4f} | Peak VRAM: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")

    # Save adapter
    os.makedirs(ADAPTER_DIR, exist_ok=True)
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    print(f"  [OK] Saved to {ADAPTER_DIR}")

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
