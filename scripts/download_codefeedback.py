#!/usr/bin/env python3
"""Download CodeFeedback subset for Mix D Phase 4 (Code).

Per Iron Law #46: Base model cached, only dataset downloaded.
Per Iron Law #45: Training log will be maintained.
"""

import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(r"E:\Trained intelligence models\alpha-wolf\backups\phase_4_code")
OUTPUT_FILE = OUTPUT_DIR / "codefeedback_30k.jsonl"
TARGET_EXAMPLES = 30000

WOLF_SYSTEM = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي."""


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Loading CodeFeedback-Filtered-Instruction (streaming, target {TARGET_EXAMPLES})...")
    from datasets import load_dataset
    ds = load_dataset(
        "m-a-p/CodeFeedback-Filtered-Instruction",
        split="train",
        streaming=True
    )

    print(f"\n[2/3] Processing examples...")
    kept = 0
    skipped = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for ex in ds:
            if kept >= TARGET_EXAMPLES:
                break

            query = ex.get("query", "").strip()
            answer = ex.get("answer", "").strip()
            lang = ex.get("lang", "")

            if not query or not answer:
                skipped += 1
                continue

            # Length check (in chars)
            total_len = len(query) + len(answer)
            if total_len > 8000 or total_len < 100:
                skipped += 1
                continue

            # Build ChatML
            chatml = [
                {"role": "system", "content": WOLF_SYSTEM + (f"\n\nPreferred language: {lang}" if lang else "")},
                {"role": "user", "content": query},
                {"role": "assistant", "content": answer}
            ]

            out = {"messages": chatml, "source": "codefeedback", "lang": lang}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
            kept += 1

            if kept % 5000 == 0:
                print(f"  [{kept}/{TARGET_EXAMPLES}] skipped={skipped}")

    print(f"\n[3/3] DONE!")
    print(f"  Kept: {kept}")
    print(f"  Skipped: {skipped}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Size: {OUTPUT_FILE.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
