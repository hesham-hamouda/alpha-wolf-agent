#!/usr/bin/env python3
"""
V2_Tools Training — Mix D Phase 3 — Tool Calling
Builds on V1_Chat_step500 (continues training, not fresh start).
Uses glaive-function-calling-v2 subset.

Per Iron Law #46: Base model CACHED.
Per Iron Law #45: Training log + Iron Laws #21-#45 maintained.
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

# Set xformers memory-efficient attention to FALSE (RTX 5060 Ti sm_120 incompatible)
os.environ["XFORMERS_DISABLED"] = "1"
os.environ["UNSLOTH_DISABLE_XFORMERS"] = "1"


# Configuration
BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
OUTPUT_DIR = "/workspace/v2_tools"
ADAPTER_DIR = f"{OUTPUT_DIR}/adapter"

DATASET_PATH = "/workspace/glaive_20k.jsonl"
TARGET_EXAMPLES = 20000
MAX_SEQ_FILTER = 12288  # Glaive can be longer (tool defs)

MAX_SEQ_LENGTH = 4096
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LEARNING_RATE = 2e-4
NUM_EPOCHS = 2
BATCH_SIZE = 2
GRAD_ACCUM = 4
SAVE_STEPS = 500

# Eval prompts (will be saved to log)
EVAL_PROMPTS = {
    "tool_calling": [
        "What's the weather in Paris?",
        "Calculate 25 * 47",
        "Send email to john@example.com saying 'Meeting at 3pm'",
    ],
    "wolf_identity": [
        "What is your name?",
        "What are the 7 wolf traits?",
    ],
    "general": [
        "What is the capital of Japan?",
        "Explain photosynthesis briefly.",
    ]
}


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
    print(f"[OK] Loaded {len(examples)} examples")
    return examples


def train():
    print("=" * 70)
    print("V2_TOOLS TRAINING — Mix D Phase 3 (Tool Calling)")
    print("Train from BASE (no V1_Chat loading — avoid xformers bug)")
    print("Will rebuild chat skills later in Mix D Phase 6 (Reflection)")
    print("=" * 70)

    # Tokenizer
    print(f"\n[1/5] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    # Load base model + new LoRA adapter (Use Unsloth's API which works)
    print(f"\n[2/5] Loading base + adding LoRA (xformers disabled)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    # Add NEW LoRA adapter on top of base (xformers off via env var)
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
    )
    print(f"  [OK] Base + new LoRA loaded. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    # Dataset
    print(f"\n[3/5] Loading glaive dataset...")
    raw = load_glaive(DATASET_PATH, TARGET_EXAMPLES)
    dataset = Dataset.from_list(raw)

    def apply_template(ex):
        text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": text}
    dataset = dataset.map(apply_template, remove_columns=["messages"])

    # Train
    print(f"\n[4/5] Training ({NUM_EPOCHS} epochs, ~{len(dataset)//(BATCH_SIZE*GRAD_ACCUM)*NUM_EPOCHS} steps)...")
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
            # Force eager attention (avoid xformers)
            optim="adamw_8bit",
        ),
    )

    start = time.time()
    train_result = trainer.train()
    elapsed = time.time() - start

    print(f"\n[OK] Training done in {elapsed:.1f}s | Final loss: {train_result.training_loss:.4f} | Peak VRAM: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")

    # Save final adapter
    os.makedirs(ADAPTER_DIR, exist_ok=True)
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    print(f"  [OK] Final adapter saved to {ADAPTER_DIR}")

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
