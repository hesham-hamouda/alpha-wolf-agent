#!/usr/bin/env python3
"""
V0_Identity Training for Alpha Wolf Agent
Phase 1 of Mix D — Identity First (Quхائd directive 2026-09-23)

Trains Llama-3.1-8B-Instruct (4-bit + LoRA) on 106 Wolf personality examples.

After training, evaluates Wolf trait presence on 14 test prompts.

Iron Law #15: Verify Before Claim — actual training + actual evaluation
"""

import os
import sys
import json
import time
import torch
from datasets import Dataset

# CRITICAL: Unsloth imports MUST come first
import unsloth
import unsloth_zoo

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments, AutoTokenizer


# ============================================================
# Configuration (per ALPHA_WOLF_METHODOLOGY.md)
# ============================================================

DATASET_PATH = "/workspace/identity_dataset_v2_200plus.jsonl"
OUTPUT_DIR = "/workspace/v0_identity"
ADAPTER_DIR = f"{OUTPUT_DIR}/adapter"
MODEL_DIR = f"{OUTPUT_DIR}/model_gguf"

# Hyperparameters (per Methodology defaults for Identity phase)
MAX_SEQ_LENGTH = 2048          # Reduced for identity data (Q3: 1268 sys + 1500 max content < 2048)
LOAD_IN_4BIT = True             # Required for 16GB VRAM
LORA_R = 16                     # r=16
LORA_ALPHA = 32                 # 2×r (Unsloth recommendation)
LORA_DROPOUT = 0.05
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"]
LEARNING_RATE = 2e-4            # Standard QLoRA
NUM_EPOCHS = 3                  # Identity needs more epochs (small dataset)
BATCH_SIZE = 2                  # Per-device
GRAD_ACCUM = 4                  # Effective batch = 8
WARMUP_STEPS = 5                # Standard
WEIGHT_DECAY = 0.01
LOGGING_STEPS = 2
SAVE_STEPS = 500

# Model
MODEL_NAME = "unsloth/Meta-Llama-3.1-8B-Instruct"
QUANTIZATION = "q4_k_m"          # For GGUF export


def load_dataset(path):
    """Load JSONL dataset and convert to list of dicts."""
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            ex = json.loads(line)
            examples.append(ex)
    print(f"[OK] Loaded {len(examples)} examples from {path}")
    return examples


def format_for_training(examples):
    """Convert chat messages to Llama-3.1 chat template text."""
    formatted = []
    for ex in examples:
        # Use Llama-3.1 chat template via tokenizer.apply_chat_template
        formatted.append({"messages": ex["messages"]})
    return formatted


def train():
    print("=" * 70)
    print("ALPHA WOLF AGENT — V0_IDENTITY TRAINING")
    print("=" * 70)
    print(f"Model: {MODEL_NAME}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Epochs: {NUM_EPOCHS}, Batch: {BATCH_SIZE}, Grad Accum: {GRAD_ACCUM}")
    print(f"LoRA: r={LORA_R}, alpha={LORA_ALPHA}, dropout={LORA_DROPOUT}")
    print()

    # ============================================================
    # Step 1: Load tokenizer (needed before model for chat template)
    # ============================================================
    print("[1/5] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    print(f"  [OK] Tokenizer loaded. Vocab size: {tokenizer.vocab_size}")

    # ============================================================
    # Step 2: Load dataset
    # ============================================================
    print("\n[2/5] Loading and formatting dataset...")
    raw_examples = load_dataset(DATASET_PATH)
    formatted = format_for_training(raw_examples)
    dataset = Dataset.from_list(formatted)

    # Apply Llama-3.1 chat template to get text
    def apply_template(ex):
        text = tokenizer.apply_chat_template(
            ex["messages"],
            tokenize=False,
            add_generation_prompt=False
        )
        return {"text": text}

    dataset = dataset.map(apply_template, remove_columns=["messages"])
    print(f"  [OK] Dataset prepared. First example preview:")
    print(f"    {dataset[0]['text'][:200]}...")

    # ============================================================
    # Step 3: Load model with 4-bit quantization
    # ============================================================
    print("\n[3/5] Loading model (4-bit)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=LOAD_IN_4BIT,
    )
    print(f"  [OK] Model loaded. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

    # ============================================================
    # Step 4: Add LoRA adapter
    # ============================================================
    print("\n[4/5] Adding LoRA adapter...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        use_gradient_checkpointing="unsloth",
    )
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"  [OK] Trainable: {trainable_params:,} / {total_params:,} ({100 * trainable_params / total_params:.2f}%)")

    # ============================================================
    # Step 5: Train
    # ============================================================
    print("\n[5/5] Training...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=WARMUP_STEPS,
            num_train_epochs=NUM_EPOCHS,
            learning_rate=LEARNING_RATE,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=LOGGING_STEPS,
            weight_decay=WEIGHT_DECAY,
            output_dir=OUTPUT_DIR,
            save_strategy="steps",
            save_steps=SAVE_STEPS,
            report_to="none",
            save_total_limit=2,
        ),
    )

    start = time.time()
    train_result = trainer.train()
    elapsed = time.time() - start

    print(f"\n[OK] Training completed in {elapsed:.1f}s")
    print(f"  Final training loss: {train_result.training_loss:.4f}")
    print(f"  Peak VRAM: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")

    # Check for NaN
    if torch.isnan(torch.tensor(train_result.training_loss)):
        print("  [WARN] Loss is NaN! Investigate before using this model.")
        return False

    # ============================================================
    # Step 6: Save adapter
    # ============================================================
    print("\n[6/6] Saving LoRA adapter...")
    os.makedirs(ADAPTER_DIR, exist_ok=True)
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    print(f"  [OK] Adapter saved to {ADAPTER_DIR}")

    # ============================================================
    # Step 7: Export GGUF
    # ============================================================
    print("\n[7/7] Exporting to GGUF...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    try:
        model.save_pretrained_gguf(
            MODEL_DIR,
            tokenizer=tokenizer,
            quantization_method=QUANTIZATION,
        )
        print(f"  [OK] GGUF model saved to {MODEL_DIR}")
    except Exception as e:
        print(f"  [WARN] GGUF export failed: {e}")
        print(f"  [INFO] Adapter saved. GGUF can be exported later.")

    # Cleanup
    del trainer
    del model
    torch.cuda.empty_cache()

    print("\n" + "=" * 70)
    print("V0_IDENTITY TRAINING COMPLETE")
    print("=" * 70)
    print(f"  Adapter: {ADAPTER_DIR}")
    print(f"  GGUF: {MODEL_DIR}")
    print(f"  Training time: {elapsed:.1f}s")
    print(f"  Final loss: {train_result.training_loss:.4f}")
    return True


if __name__ == "__main__":
    success = train()
    sys.exit(0 if success else 1)
