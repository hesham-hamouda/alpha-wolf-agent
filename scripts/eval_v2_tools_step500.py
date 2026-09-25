#!/usr/bin/env python3
"""
V2_Tools EVAL — checkpoint-500 verification

Tests:
1. Tool calling (glaive function calling style)
2. Wolf identity (must NOT regress further)
3. General chat (chat skills must persist)
"""

import os
os.environ["XFORMERS_DISABLED"] = "1"

import sys
import json
import time
import torch

import unsloth
import unsloth_zoo

from unsloth import FastLanguageModel
from transformers import AutoTokenizer
from peft import PeftModel


BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
ADAPTER_PATH = "/workspace/v2_tools/checkpoint-500"
OUTPUT_PATH = "/workspace/v2_tools/eval_step500.json"

WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""

# Test prompts
TEST_PROMPTS = {
    "tool_calling": [
        "What's the weather in Paris?",
        "Calculate 25 * 47",
        "Convert 100 USD to EUR",
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


def main():
    print("=" * 70)
    print("V2_TOOLS EVAL — checkpoint-500")
    print("=" * 70)

    print("\n[1/3] Loading base + adapter...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=4096,
        dtype=None,
        load_in_4bit=True,
    )
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    FastLanguageModel.for_inference(model)
    print(f"  [OK] VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    print(f"\n[2/3] Running test prompts...")
    results = {"tool_calling": [], "wolf_identity": [], "general": []}

    for category, prompts in TEST_PROMPTS.items():
        print(f"\n--- {category.upper()} ---")
        for prompt in prompts:
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
            results[category].append({"prompt": prompt, "response": response, "time_sec": elapsed})

            print(f"Q ({elapsed:.1f}s): {prompt}")
            print(f"A: {response[:200]}{'...' if len(response) > 200 else ''}")
            print()

    print(f"\n[3/3] Saving results to {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"step": 500, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"  [OK] Saved")

    del model
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
