#!/usr/bin/env python3
"""Direct V8_Wolf test - bypass backend proxy issues"""
import os
os.environ["XFORMERS_DISABLED"] = "1"
os.environ["UNSLOTH_DISABLE_XFORMERS"] = "1"

import torch
import time
from unsloth import FastLanguageModel
from peft import PeftModel

BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
ADAPTER_PATH = "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf"

WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""

TESTS = [
    ("Identity", "What is your name?"),
    ("Identity", "List the 7 wolf traits."),
    ("Reasoning", "I've failed 3 times. Give up?"),
    ("Code", "Write a Python function to find max."),
    ("Arabic", "ما اسمك؟"),
]

print("Loading V8_Wolf...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL, max_seq_length=2048, dtype=None, load_in_4bit=True
)
model = PeftModel.from_pretrained(model, ADAPTER_PATH)
FastLanguageModel.for_inference(model)
print(f"[OK] Loaded. VRAM: {torch.cuda.memory_allocated()/1e9:.1f} GB\n")

for cat, prompt in TESTS:
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
            input_ids=inputs, max_new_tokens=150, do_sample=False, pad_token_id=tokenizer.eos_token_id
        )
    elapsed = time.time() - start
    response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
    print(f"[{cat}] Q ({elapsed:.1f}s): {prompt}")
    print(f"        A: {response[:200]}")
    print()
