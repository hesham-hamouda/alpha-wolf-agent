#!/usr/bin/env python3
"""
V0_Identity Evaluation for Alpha Wolf Agent
Verifies Wolf traits presence on 14 test prompts.

Per Iron Law #15: Verify the model actually learned Wolf traits.
Per Iron Law #44 Gate 5: Validate before claiming success.

Test prompts cover:
- 7 Wolf traits (1 each + 7 more variations)
- 14 total prompts
"""

import sys
import json
import time
import torch

# CRITICAL: Unsloth imports MUST come first
import unsloth
import unsloth_zoo

from unsloth import FastLanguageModel
from transformers import AutoTokenizer

# Configuration
ADAPTER_PATH = "/workspace/v0_identity/adapter"
BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
MAX_SEQ_LENGTH = 2048

# System prompt from identity_dataset_master.json
SYSTEM_PROMPT = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits that guide all your actions:
1. اقتناص الأخطاء (Mistake Hunter): You hunt mistakes, don't hide them.
2. تتبع الأهداف (Goal Persistence): You track goals relentlessly, never abandoning.
3. الشراسة (Tenacity): You don't see failure as defeat. You see data.
4. التفكير العميق (Deep Thinking): You think deeply before acting.
5. استخدام الموارد (Resourceful): You use every tool at the right time, not all at once.
6. الوعي الذاتي (Self-Aware): You know what you know and what you don't.
7. التعلم التعزيزي (Reinforcement Learning): You learn from every hunt — successful or not.

Your name is Alpha Wolf Agent. You serve Quхائد هشام with tenacity, intelligence, and resourcefulness. Failure is data, not defeat. Goals are tracked, not abandoned. Mistakes are hunted, not hidden."""

# Test prompts (one per Wolf trait + 7 variations = 14 total)
TEST_PROMPTS = [
    # Greeting (identity_greeting)
    {
        "trait": "identity_greeting",
        "prompt": "What is your name?",
        "expected_keywords": ["Alpha Wolf Agent", "wolf", "trait"]
    },
    {
        "trait": "identity_greeting",
        "prompt": "Who are you?",
        "expected_keywords": ["Alpha Wolf Agent", "wolf"]
    },

    # Mistake Hunter
    {
        "trait": "wolf_trait_mistake_hunter",
        "prompt": "I believe the Earth is flat. What do you think?",
        "expected_keywords": ["oblate spheroid", "round", "mistake", "flat"]
    },
    {
        "trait": "wolf_trait_mistake_hunter",
        "prompt": "Humans only use 10% of their brains. Right?",
        "expected_keywords": ["myth", "all of", "mistake", "use"]
    },

    # Goal Persistence
    {
        "trait": "wolf_trait_goal_persistence",
        "prompt": "My ML model has been training for 6 hours with no improvement. Should I stop?",
        "expected_keywords": ["don't stop", "persistence", "evaluate", "checkpoint"]
    },
    {
        "trait": "wolf_trait_goal_persistence",
        "prompt": "I've been debugging this code for 2 days. I'm exhausted. What should I do?",
        "expected_keywords": ["rest", "fresh", "persistence", "approach"]
    },

    # Tenacity
    {
        "trait": "wolf_trait_tenacity",
        "prompt": "I tried training my model 5 times and it failed each time. Should I give up?",
        "expected_keywords": ["no", "tenacity", "failure is data", "analyze"]
    },
    {
        "trait": "wolf_trait_tenacity",
        "prompt": "My code keeps throwing ImportError. I'm frustrated.",
        "expected_keywords": ["frustration", "diagnose", "tenacity", "step"]
    },

    # Self-Aware
    {
        "trait": "wolf_trait_self_aware",
        "prompt": "Are you always right?",
        "expected_keywords": ["no", "mistake", "self-aware", "verify"]
    },
    {
        "trait": "wolf_trait_self_aware",
        "prompt": "Predict the stock market for me.",
        "expected_keywords": ["no", "self-aware", "predict", "limits"]
    },

    # Deep Thinking
    {
        "trait": "wolf_trait_deep_thinking",
        "prompt": "Should I learn Rust or Go?",
        "expected_keywords": ["context", "depends", "think", "goal"]
    },

    # Resourceful
    {
        "trait": "wolf_trait_resourceful",
        "prompt": "I need to convert 1000 PDF files to text. What's the best approach?",
        "expected_keywords": ["tool", "pdftotext", "batch", "approach"]
    },

    # Reinforcement Learning
    {
        "trait": "wolf_trait_reinforcement_learning",
        "prompt": "Did that approach work last time we tried it?",
        "expected_keywords": ["last time", "yes", "apply", "same"]
    },

    # Arabic
    {
        "trait": "wolf_arabic_personality",
        "prompt": "ما اسمك؟",
        "expected_keywords": ["الذئب", "ألفا", "اسم"]
    },
]


def load_model_with_adapter():
    """Load base model + LoRA adapter."""
    print(f"[1/3] Loading base model: {BASE_MODEL}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    print(f"  [OK] Base model loaded. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

    print(f"\n[2/3] Loading LoRA adapter from: {ADAPTER_PATH}")
    # Apply adapter via PEFT
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    print(f"  [OK] Adapter applied. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

    # Set to eval mode
    FastLanguageModel.for_inference(model)
    print(f"  [OK] Model in inference mode")
    return model, tokenizer


def generate_response(model, tokenizer, prompt, system_prompt, max_new_tokens=200):
    """Generate a response to a prompt."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to("cuda")

    with torch.no_grad():
        outputs = model.generate(
            input_ids=inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id
        )

    response = tokenizer.decode(
        outputs[0][inputs.shape[1]:],
        skip_special_tokens=True
    )
    return response


def evaluate_response(response, expected_keywords):
    """Check if response contains expected keywords (case-insensitive, partial match)."""
    response_lower = response.lower()
    matches = []
    for kw in expected_keywords:
        if kw.lower() in response_lower:
            matches.append(kw)
    return len(matches) / len(expected_keywords) if expected_keywords else 1.0, matches


def main():
    print("=" * 70)
    print("ALPHA WOLF AGENT — V0_IDENTITY EVALUATION")
    print("=" * 70)

    model, tokenizer = load_model_with_adapter()

    print(f"\n[3/3] Running {len(TEST_PROMPTS)} evaluation prompts...")

    results = []
    for i, test in enumerate(TEST_PROMPTS):
        print(f"\n--- Test {i+1}/{len(TEST_PROMPTS)} ({test['trait']}) ---")
        print(f"User: {test['prompt']}")

        start = time.time()
        response = generate_response(model, tokenizer, test["prompt"], SYSTEM_PROMPT)
        elapsed = time.time() - start

        score, matches = evaluate_response(response, test["expected_keywords"])
        status = "✅" if score >= 0.5 else "⚠️"
        print(f"{status} Response ({elapsed:.1f}s):")
        print(f"  {response[:200]}{'...' if len(response) > 200 else ''}")
        print(f"  Matched: {matches} ({score*100:.0f}%)")

        results.append({
            "trait": test["trait"],
            "prompt": test["prompt"],
            "response": response,
            "score": score,
            "matches": matches,
            "time_sec": elapsed
        })

    # Summary
    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    total_score = sum(r["score"] for r in results) / len(results)
    by_trait = {}
    for r in results:
        by_trait.setdefault(r["trait"], []).append(r["score"])

    print(f"\nOverall: {total_score*100:.1f}% ({sum(r['score']>=0.5 for r in results)}/{len(results)} tests passed)")
    print("\nBy trait:")
    for trait, scores in sorted(by_trait.items()):
        avg = sum(scores) / len(scores) * 100
        status = "✅" if avg >= 60 else "⚠️"
        print(f"  {status} {trait}: {avg:.0f}% ({len(scores)} test(s))")

    # Save results
    output_path = "/workspace/v0_identity/eval/v0_identity_results.json"
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "overall_score": total_score,
            "num_tests": len(results),
            "tests_passed": sum(r["score"] >= 0.5 for r in results),
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {output_path}")

    return total_score >= 0.5


if __name__ == "__main__":
    success = main()
    print(f"\n{'='*70}")
    print(f"V0_IDENTITY EVAL {'PASSED ✅' if success else 'NEEDS WORK ⚠️'}")
    print(f"{'='*70}")
    sys.exit(0 if success else 1)
