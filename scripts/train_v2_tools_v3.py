#!/usr/bin/env python3
"""
Continue V2_Tools training using Unsloth's native adapter loading.
No PeftModel.from_pretrained() — instead use Unsloth's adapter loading.
"""

import os
# Force disable xformers COMPLETELY
os.environ["XFORMERS_DISABLED"] = "1"
os.environ["UNSLOTH_DISABLE_XFORMERS"] = "1"
os.environ["TORCH_USE_CUDA_DSA"] = "1"

import sys
import json
import time
import torch
from datasets import Dataset

import unsloth
import unsloth_zoo

# Patch xformers to be None BEFORE any other imports
import sys as _sys
_sys.modules['xformers'] = None
_sys.modules['xformers.ops'] = None

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments, AutoTokenizer


BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
RESUME_ADAPTER_DIR = "/workspace/v2_tools/checkpoint-500"
OUTPUT_DIR = "/workspace/v2_tools_v3"

DATASET_PATH = "/workspace/glaive_20k.jsonl"
TARGET_EXAMPLES = 20000
MAX_SEQ_FILTER = 12288

MAX_SEQ_LENGTH = 4096
LORA_R = 16
LORA_ALPHA = 32
LEARNING_RATE = 2e-4
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
    print("V2_TOOLS CONTINUE v3 — Train fresh LoRA on top of checkpoint-500")
    print("=" * 70)

    print(f"\n[1/4] Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    print(f"\n[2/4] Load base model with checkpoint-500 loaded as LoRA adapter...")
    # Use Unsloth's FastLanguageModel which handles xformers internally
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    # Use load_adapter method instead of PeftModel.from_pretrained
    # This is Unsloth's safe way to load existing LoRA adapters
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, RESUME_ADAPTER_DIR, is_trainable=True)
    print(f"  [OK] Resume from {RESUME_ADAPTER_DIR}. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    print(f"\n[3/4] Dataset...")
    raw = load_glaive(DATASET_PATH, TARGET_EXAMPLES)
    dataset = Dataset.from_list(raw)

    def apply_template(ex):
        text = tokenizer.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": text}
    dataset = dataset.map(apply_template, remove_columns=["messages"])

    print(f"\n[4/4] Training (500 more steps)...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=dataset,
        dataset_text_field="text", max_seq_length=MAX_SEQ_LENGTH,
        args=TrainingArguments(
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=0,
            max_steps=500,
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

    print(f"\n[OK] Done in {elapsed:.1f}s | Final loss: {train_result.training_loss:.4f}")
    print(f"  Peak VRAM: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")

    # Save adapter
    adapter_out = f"{OUTPUT_DIR}/adapter_step1500_actual"  # 500 + 500 = ~step 1500 in this fresh training
    os.makedirs(adapter_out, exist_ok=True)
    model.save_pretrained(adapter_out)
    tokenizer.save_pretrained(adapter_out)
    print(f"  [OK] Saved to {adapter_out}")

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
