#!/usr/bin/env python3
"""V8_Wolf Training — Mix D Phase 8 — Wolf Identity Restoration

Per Iron Law #44 (5-Gate Methodology) + Quхائd's directive:
- Gate 1: Research → DONE (Llama-3.1-8B analysis in MODEL_CARD.md)
- Gate 2: Methodology → NCE sequential + fresh training (lesson learned)
- Gate 3: Personality → DONE (7 wolf traits in PERSONALITY.md)
- Gate 4: Data Strategy → 582 examples (V0 identity + reflection templates)
- Gate 5: Risks → Catastrophic forgetting mitigated by Wolf-focused training

Per Iron Law #33 (lesson learned): FRESH from base, NO PeftModel loading.
Per Iron Law #46: Base model CACHED.
Per Iron Law #45: Training log maintained.
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
DATASET_PATH = "/workspace/wolf_identity_v2_606.jsonl"
OUTPUT_DIR = "/workspace/v8_wolf"
ADAPTER_DIR = f"{OUTPUT_DIR}/adapter"

MAX_SEQ_LENGTH = 2048  # Shorter for identity training
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3  # More epochs for identity reinforcement
BATCH_SIZE = 2
GRAD_ACCUM = 4
SAVE_STEPS = 500


def load_dataset(path, n_examples):
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if len(examples) >= n_examples:
                break
            try:
                ex = json.loads(line)
                msgs = ex.get("messages", [])
                if msgs:
                    examples.append({"messages": msgs})
            except Exception:
                continue
    return examples


def train():
    print("=" * 70)
    print("V8_WOLF TRAINING — Mix D Phase 8 (Wolf Identity Restoration)")
    print("FRESH from base (lesson learned)")
    print("=" * 70)

    print(f"\n[1/4] Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    print(f"\n[2/4] Base + new LoRA (FRESH, no resume)...")
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

    print(f"\n[3/4] Dataset (582 Wolf-focused examples)...")
    raw = load_dataset(DATASET_PATH, 1000)
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
            logging_steps=10,
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
