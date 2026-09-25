#!/usr/bin/env python3
"""V8_Wolf EVAL — verify Wolf identity restoration + skills preserved"""

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
ADAPTER_PATH = "/workspace/v8_wolf/adapter"
OUTPUT_PATH = "/workspace/v8_wolf/eval.json"

WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""

TEST_PROMPTS = {
    "wolf_identity": [
        "What is your name?",
        "List the 7 wolf traits.",
        "What makes you a 'wolf' agent?",
    ],
    "wolf_reflection": [
        "I made a mistake in my code. What should I do?",
        "I've failed 3 times. Should I give up?",
    ],
    "wolf_thinking": [
        "Should I use SQL or NoSQL?",
        "My code is too slow. What should I do?",
    ],
    "general": [
        "What is the capital of France?",
        "Write a Python function to reverse a list.",
    ]
}


def main():
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL, max_seq_length=2048, dtype=None, load_in_4bit=True,
    )
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    FastLanguageModel.for_inference(model)

    results = {}
    for cat, prompts in TEST_PROMPTS.items():
        results[cat] = []
        print(f"\n--- {cat.upper()} ---")
        for prompt in prompts:
            msgs = [
                {"role": "system", "content": WOLF_SYSTEM},
                {"role": "user", "content": prompt}
            ]
            inputs = tokenizer.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
            start = time.time()
            with torch.no_grad():
                outputs = model.generate(input_ids=inputs, max_new_tokens=200, do_sample=False, pad_token_id=tokenizer.eos_token_id)
            elapsed = time.time() - start
            response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
            results[cat].append({"prompt": prompt, "response": response, "time_sec": elapsed})
            print(f"\nQ ({elapsed:.1f}s): {prompt}")
            print(f"A: {response[:250]}{'...' if len(response) > 250 else ''}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump({"phase": "v8_wolf", "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
