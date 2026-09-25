#!/usr/bin/env python3
"""
Download UltraChat-200k subset for Mix D Phase 2 Chat Baseline Training.

Per Iron Law #46: Use streaming to avoid downloading full dataset (~120 GB).
Per Iron Law #44: Detailed in DATA_STRATEGY.md (40% of Mix D = 50k examples subset).

Output:
    - 50k examples
    - JSONL format for Unsloth
    - Saved to alpha-wolf/backups/phase_2_chat/ultrachat_50k.jsonl
"""

import json
import sys
from pathlib import Path
from datasets import load_dataset

# Configuration
OUTPUT_DIR = Path(r"E:\Trained intelligence models\alpha-wolf\backups\phase_2_chat")
OUTPUT_FILE = OUTPUT_DIR / "ultrachat_50k.jsonl"
TARGET_EXAMPLES = 50000
MAX_CHARS_PER_EXAMPLE = 4000  # Filter out very long examples


def format_example(example):
    """Convert UltraChat format to ChatML messages.

    UltraChat-200k format (train_sft split):
    {
        "prompt": "user message",
        "prompt_id": "...",
        "messages": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]
    }
    """
    # Use 'messages' field directly (UltraChat's structured format)
    if "messages" in example and isinstance(example["messages"], list) and len(example["messages"]) >= 2:
        msgs = []
        for m in example["messages"]:
            role = m.get("role", "").lower()
            content = m.get("content", "")
            if role in ["user", "assistant", "system"] and content:
                msgs.append({"role": role, "content": content})
        # Ensure at least one user + one assistant
        has_user = any(m["role"] == "user" for m in msgs)
        has_assistant = any(m["role"] == "assistant" for m in msgs)
        if has_user and has_assistant:
            return msgs

    # Fallback: construct from prompt + completion (in case of different split)
    messages = []
    if "prompt" in example and example["prompt"]:
        messages.append({"role": "user", "content": example["prompt"]})
    if "completion" in example and example["completion"]:
        messages.append({"role": "assistant", "content": example["completion"]})
    return messages if len(messages) >= 2 else None


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Loading UltraChat-200k (streaming, target: {TARGET_EXAMPLES} examples)...")
    print("NOTE: Per Iron Law #46, ONLY the base model is cached. Datasets are downloaded once.")

    # Use streaming to avoid full download
    dataset = load_dataset(
        "HuggingFaceH4/ultrachat_200k",
        split="train_sft",
        streaming=True
    )

    print(f"\n[2/3] Streaming + filtering examples...")
    examples_kept = 0
    examples_skipped = 0
    total_chars = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for i, ex in enumerate(dataset):
            if examples_kept >= TARGET_EXAMPLES:
                break

            messages = format_example(ex)
            if not messages:
                examples_skipped += 1
                continue

            # Length check
            total_len = sum(len(m["content"]) for m in messages)
            if total_len > MAX_CHARS_PER_EXAMPLE * 4:  # ~4 chars/token
                examples_skipped += 1
                continue

            # Write as JSONL
            output = {
                "messages": messages,
                "source": "ultrachat_200k",
                "index": i
            }
            f.write(json.dumps(output, ensure_ascii=False) + "\n")
            examples_kept += 1
            total_chars += total_len

            if examples_kept % 5000 == 0:
                avg_chars = total_chars // examples_kept
                print(f"  [{examples_kept}/{TARGET_EXAMPLES}] avg_len={avg_chars} chars, skipped={examples_skipped}")

    print(f"\n[3/3] DONE!")
    print(f"  Kept: {examples_kept} examples")
    print(f"  Skipped: {examples_skipped} examples")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Size: {OUTPUT_FILE.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Partial download may exist")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
