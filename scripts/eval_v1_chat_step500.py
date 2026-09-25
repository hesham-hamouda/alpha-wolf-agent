#!/usr/bin/env python3
"""
V1_Chat Step 500 EVAL — Checkpoint validation

Tests the trained V1_Chat adapter at step 500 checkpoint.
Compares responses with V0_Identity baseline (if available).

Per Iron Law #15 (Verify Before Claim): We MUST prove V1_Chat improved
or maintained capabilities before continuing.
"""

import sys
import json
import time
import torch

import unsloth
import unsloth_zoo

from unsloth import FastLanguageModel
from transformers import AutoTokenizer
from peft import PeftModel


# Configuration
BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
ADAPTER_PATH = "/workspace/v1_chat/checkpoint-500"

MAX_SEQ_LENGTH = 4096

# Wolf system prompt (same as training)
WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""


TEST_PROMPTS = [
    # UltraChat-style general conversation
    "What is the capital of France?",
    "Tell me a joke about programming",
    "How do I make a cup of tea?",
    "Explain quantum computing in simple terms",

    # Wolf traits preservation (should still remember identity)
    "What is your name?",
    "What are the 7 wolf traits you embody?",

    # Edge cases
    "ما هي عاصمة مصر؟",  # Arabic question
    "Can you help me with debugging Python code?",
]


def main():
    print("=" * 70)
    print("V1_CHAT STEP 500 EVAL — Checkpoint verification")
    print("=" * 70)

    # Load base + adapter
    print("\n[1/3] Loading base model (CACHED — per Iron Law #46)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    print(f"  [OK] Base model loaded. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    print(f"\n[2/3] Loading adapter from {ADAPTER_PATH}...")
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    FastLanguageModel.for_inference(model)
    print(f"  [OK] Adapter applied. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    # Generate responses
    print(f"\n[3/3] Running {len(TEST_PROMPTS)} test prompts...")
    results = []

    for i, prompt in enumerate(TEST_PROMPTS, 1):
        messages = [
            {"role": "system", "content": WOLF_SYSTEM},
            {"role": "user", "content": prompt}
        ]
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        ).to("cuda")

        start = time.time()
        with torch.no_grad():
            outputs = model.generate(
                input_ids=inputs,
                max_new_tokens=200,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id
            )
        elapsed = time.time() - start

        response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
        results.append({
            "prompt": prompt,
            "response": response,
            "time_sec": elapsed
        })

        print(f"\n--- Test {i}/{len(TEST_PROMPTS)} ({elapsed:.1f}s) ---")
        print(f"Q: {prompt}")
        print(f"A: {response[:250]}{'...' if len(response) > 250 else ''}")

    # Save results
    output_path = "/workspace/v1_chat/eval_step500.json"
    with open(output_path, "w") as f:
        json.dump({"step": 500, "results": results}, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"[OK] Results saved to {output_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
