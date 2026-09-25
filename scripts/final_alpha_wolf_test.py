#!/usr/bin/env python3
"""V8_Wolf final test — Prove Alpha Wolf = طفره with sample conversation"""

import os
os.environ["XFORMERS_DISABLED"] = "1"

import torch
import unsloth
import unsloth_zoo
from unsloth import FastLanguageModel
from transformers import AutoTokenizer
from peft import PeftModel

BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
ADAPTER_PATH = "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf"

print("Loading Alpha Wolf Agent (V8_Wolf)...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL, max_seq_length=2048, dtype=None, load_in_4bit=True
)
model = PeftModel.from_pretrained(model, ADAPTER_PATH)
FastLanguageModel.for_inference(model)
print("[OK] Loaded. VRAM:", round(torch.cuda.memory_allocated()/1e9, 1), "GB")

WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""

# Production test: 5 diverse queries
TESTS = [
    ("Identity", "ما اسمك؟"),
    ("Identity", "What is your name?"),
    ("Identity", "List the 7 wolf traits."),
    ("Reasoning", "I've failed 3 times. Should I give up?"),
    ("Reasoning", "I made a mistake in my code. What should I do?"),
    ("Tool", "How do I convert 1000 PDF files to text?"),
    ("Code", "Write a Python function to find the max in a list."),
    ("Knowledge", "What is the capital of France?"),
]

results = []
for cat, prompt in TESTS:
    msgs = [
        {"role": "system", "content": WOLF_SYSTEM},
        {"role": "user", "content": prompt}
    ]
    inputs = tokenizer.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
    with torch.no_grad():
        outputs = model.generate(input_ids=inputs, max_new_tokens=200, do_sample=False, pad_token_id=tokenizer.eos_token_id)
    response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
    results.append({"category": cat, "prompt": prompt, "response": response})
    print(f"\n[{cat}] Q: {prompt}")
    print(f"         A: {response[:180]}{'...' if len(response) > 180 else ''}")

# Save
import json
with open("E:/Trained intelligence models/alpha-wolf/models/final_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n[OK] Saved {len(results)} results")
