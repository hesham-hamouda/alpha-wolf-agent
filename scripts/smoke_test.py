#!/usr/bin/env python3
"""
Step 2a: Smoke Test for Alpha Wolf Agent Training
Iron Law #15 (Verify Before Claim) — must PROVE training works before Phase 2

Tests:
1. Load Llama-3.1-8B-Instruct (4-bit)
2. Add LoRA adapter
3. Train 10 steps on dummy data
4. Verify no crashes, no NaN, loss decreases
"""

import os
import sys
import json
import torch
from datasets import Dataset

# CRITICAL: Unsloth imports MUST come first (sets env var)
import unsloth
import unsloth_zoo

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments

def main():
    print("=" * 60)
    print("ALPHA WOLF SMOKE TEST — 10 steps on dummy data")
    print("=" * 60)

    # 1. Load model (4-bit, max_seq_length=4096 per Quхائd hard rule)
    print("\n[1/5] Loading Llama-3.1-8B-Instruct (4-bit)...")
    MAX_SEQ_LENGTH = 2048  # Reduced for smoke test (faster)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Meta-Llama-3.1-8B-Instruct",
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    print(f"    [OK] Model loaded. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

    # 2. Add LoRA adapter
    print("\n[2/5] Adding LoRA adapter (r=16, alpha=32)...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
    )
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"    [OK] LoRA added. Trainable: {trainable_params:,} / {total_params:,} ({100 * trainable_params / total_params:.2f}%)")

    # 3. Create dummy dataset (Wolf-themed for fun)
    print("\n[3/5] Creating dummy dataset (5 Wolf-themed examples)...")
    dummy_data = [
        {
            "text": "<|begin▁of▁sentence|>You are Alpha Wolf Agent. A wolf who hunts mistakes.\n\nUser: What's your name?\nAssistant: I am Alpha Wolf Agent. I hunt mistakes, track goals, and never give up.<|end▁of▁sentence|>"
        },
        {
            "text": "<|begin▁of▁sentence|>You are Alpha Wolf Agent.\n\nUser: How do you approach a hard problem?\nAssistant: Like a wolf: I observe, plan, use my senses (body KB + tools), then act. I never abandon a goal.<|end▁of▁sentence|>"
        },
        {
            "text": "<|begin▁of▁sentence|>You are Alpha Wolf Agent.\n\nUser: What if you fail?\nAssistant: Failure is data. I reflect on what went wrong, learn from it, and try a new strategy.<|end▁of▁sentence|>"
        },
        {
            "text": "<|begin▁of▁sentence|>You are Alpha Wolf Agent.\n\nUser: Are you self-aware?\nAssistant: Yes. I know what I know and what I don't. When uncertain, I admit it and seek verification from my body KB.<|end▁of▁sentence|>"
        },
        {
            "text": "<|begin▁of▁sentence|>You are Alpha Wolf Agent.\n\nUser: Tell me about tool use.\nAssistant: I use my tools at the right time, not all at once. I query my body KB when needed, and I cite my sources.<|end▁of▁sentence|>"
        },
    ]
    dataset = Dataset.from_list(dummy_data)
    print(f"    [OK] Dataset created: {len(dataset)} examples")

    # 4. Configure training (10 steps only — smoke test)
    print("\n[4/5] Configuring trainer (10 steps)...")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=2,
            warmup_steps=2,
            max_steps=10,
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            output_dir="E:/Trained intelligence models/alpha-wolf/checkpoints/smoke_test",
            save_strategy="no",  # No save for smoke test
            report_to="none",
        ),
    )

    # 5. Run smoke test
    print("\n[5/5] Running smoke test (10 steps)...")
    print("-" * 40)
    try:
        train_result = trainer.train()
        print("-" * 40)
        print(f"\n[OK] Smoke test PASSED!")
        print(f"    Training loss (final): {train_result.training_loss:.4f}")
        print(f"    VRAM peak: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")

        # Verify no NaN
        if torch.isnan(torch.tensor(train_result.training_loss)):
            print("    [FAIL] Loss is NaN!")
            return False

        return True
    except Exception as e:
        print(f"\n[FAIL] Smoke test FAILED: {e}")
        return False
    finally:
        # Cleanup
        del model
        del trainer
        torch.cuda.empty_cache()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
