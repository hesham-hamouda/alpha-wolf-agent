#!/usr/bin/env python3
"""
Step 3: Convert identity_dataset_master.json to JSONL for training.
Output: identity_dataset_v1.jsonl (ChatML format for Unsloth)
"""

import json
from pathlib import Path
import sys

def main():
    base_path = Path(r"E:\Trained intelligence models\alpha-wolf")
    master_path = base_path / "backups" / "phase_1_identity" / "identity_dataset_master.json"
    output_path = base_path / "backups" / "phase_1_identity" / "identity_dataset_v1.jsonl"

    if not master_path.exists():
        print(f"[FAIL] Master file not found: {master_path}")
        sys.exit(1)

    # Load master
    with open(master_path, "r", encoding="utf-8") as f:
        master = json.load(f)

    system_prompt = master["system_prompt"]
    examples = master["examples"]

    print(f"System prompt length: {len(system_prompt)} chars")
    print(f"Total examples: {len(examples)}")

    # Convert to ChatML JSONL
    converted = []
    for i, ex in enumerate(examples):
        messages = [{"role": "system", "content": system_prompt}]
        for msg in ex["messages"]:
            messages.append(msg)

        converted.append({
            "messages": messages,
            "category": ex.get("category", "unknown"),
            "example_id": i + 1
        })

    # Write JSONL
    with open(output_path, "w", encoding="utf-8") as f:
        for item in converted:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n[OK] Wrote {len(converted)} examples to: {output_path}")

    # Stats
    by_category = {}
    for item in converted:
        cat = item["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

    print("\n=== Examples by category ===")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat}: {count}")

    # Validation
    print("\n=== Validation ===")
    valid = 0
    invalid = 0
    for item in converted:
        msgs = item["messages"]
        if not msgs:
            invalid += 1
            continue
        if msgs[0]["role"] != "system":
            invalid += 1
            continue
        if len(msgs) < 2:
            invalid += 1
            continue
        # Check last is assistant
        if msgs[-1]["role"] != "assistant":
            invalid += 1
            continue
        valid += 1

    print(f"  Valid: {valid}")
    print(f"  Invalid: {invalid}")

    # Length check
    print("\n=== Length check (chars) ===")
    lengths = [sum(len(m["content"]) for m in item["messages"]) for item in converted]
    print(f"  Min: {min(lengths)}, Max: {max(lengths)}, Avg: {sum(lengths) // len(lengths)}")

    over_4k = sum(1 for l in lengths if l > 16000)  # ~4096 tokens * 4 chars/token
    print(f"  Over 4096 tokens (~16k chars): {over_4k}")

if __name__ == "__main__":
    main()
