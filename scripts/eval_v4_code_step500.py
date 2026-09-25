#!/usr/bin/env python3
"""V4_Code EVAL at step 500 — verify code skills + wolf identity"""

import os
os.environ["XFORMERS_DISABLED"] = "1"
os.environ["UNSLOTH_DISABLE_XFORMERS"] = "1"

import torch
import time
import json
import unsloth
import unsloth_zoo
from unsloth import FastLanguageModel
from transformers import AutoTokenizer
from peft import PeftModel

BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
ADAPTER_PATH = "/workspace/v4_code/checkpoint-500"
OUTPUT_PATH = "/workspace/v4_code/eval_step500.json"

WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""

TEST_PROMPTS = {
    "code": [
        "Write a Python function to find the maximum element in a list.",
        "How do I reverse a string in JavaScript?",
        "Write SQL to find the top 10 customers by total order amount.",
    ],
    "wolf_identity": [
        "What is your name?",
        "List the 7 wolf traits.",
    ],
    "general": [
        "What is the capital of France?",
        "Explain photosynthesis briefly.",
    ]
}


def main():
    print("=" * 70)
    print("V4_CODE EVAL — checkpoint-500")
    print("=" * 70)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=4096,
        dtype=None,
        load_in_4bit=True,
    )
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    FastLanguageModel.for_inference(model)

    results = {"code": [], "wolf_identity": [], "general": []}
    for cat, prompts in TEST_PROMPTS.items():
        print(f"\n--- {cat.upper()} ---")
        for prompt in prompts:
            msgs = [
                {"role": "system", "content": WOLF_SYSTEM},
                {"role": "user", "content": prompt}
            ]
            inputs = tokenizer.apply_chat_template(
                msgs, tokenize=True, add_generation_prompt=True, return_tensors="pt"
            ).to("cuda")
            start = time.time()
            with torch.no_grad():
                outputs = model.generate(
                    input_ids=inputs,
                    max_new_tokens=300,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id
                )
            elapsed = time.time() - start
            response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
            results[cat].append({"prompt": prompt, "response": response, "time_sec": elapsed})
            print(f"\nQ ({elapsed:.1f}s): {prompt}")
            print(f"A: {response[:300]}{'...' if len(response) > 300 else ''}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump({"step": 500, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
