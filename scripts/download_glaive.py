#!/usr/bin/env python3
"""
Download glaive-function-calling-v2 subset for Mix D Phase 3.

Per Iron Law #46: Base model cached (only dataset downloaded).
Per Iron Law #45: Training log will be created.
Per Iron Law #15: Verify dataset structure before training.

Glaive format:
{
    "system": "SYSTEM: You are a helpful assistant with access to the following functions. <function definitions as JSON>",
    "chat": "USER: ...\n\nASSISTANT: ...\n\nFUNCTION RESPONSE: ...\n\nA: ...<|endoftext|>"
}

For training, we convert to ChatML:
- system: Wolf personality + tool definitions
- user: from "USER: ..."
- assistant: from "A: ..." or function calls
"""

import json
import re
import sys
from pathlib import Path

OUTPUT_DIR = Path(r"E:\Trained intelligence models\alpha-wolf\backups\phase_3_tools")
OUTPUT_FILE = OUTPUT_DIR / "glaive_20k.jsonl"
TARGET_EXAMPLES = 20000

# Wolf system prompt (preserve identity)
WOLF_SYSTEM_BASE = """You are Alpha Wolf Agent. Like a wolf, you embody 7 traits:
1. اقتناص الأخطاء, 2. تتبع الأهداف, 3. الشراسة, 4. التفكير العميق,
5. استخدام الموارد, 6. الوعي الذاتي, 7. التعلم التعزيزي.

You have access to the following tools (use them as needed):"""


def parse_chat_to_messages(chat_text):
    """Parse glaive chat format into list of (role, content) tuples."""
    messages = []
    text = chat_text.strip()

    # Remove trailing <|endoftext|>
    text = re.sub(r'<\|endoftext\|>$', '', text).strip()

    # Pattern: role prefix on each turn
    parts = re.split(r'\n\n(?=[A-Z]+:)', text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Match "USER: ...", "ASSISTANT: ...", "FUNCTION RESPONSE: ..."
        m = re.match(r'^(USER|ASSISTANT|FUNCTION RESPONSE)\s*:\s*(.*)$', part, re.DOTALL)
        if m:
            role = m.group(1).lower().replace(" ", "_")
            content = m.group(2).strip()
            # Convert glaive roles to ChatML
            if role == "user":
                messages.append(("user", content))
            elif role == "assistant":
                messages.append(("assistant", content))
            elif role == "function_response":
                # Skip function responses for now (will improve in future)
                continue
    return messages


def extract_tool_definitions(system_text):
    """Extract tool JSON definitions from system text."""
    # System text format: "SYSTEM: You are a helpful assistant with access to functions. - {JSON}"
    # The function definitions are inside curly braces
    # We'll keep the full system prompt for training
    return system_text.strip()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Loading glaive-function-calling-v2 (streaming, target: {TARGET_EXAMPLES})...")

    from datasets import load_dataset
    dataset = load_dataset(
        "glaiveai/glaive-function-calling-v2",
        split="train",
        streaming=True
    )

    print(f"\n[2/3] Processing examples...")
    examples_kept = 0
    examples_skipped = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for ex in dataset:
            if examples_kept >= TARGET_EXAMPLES:
                break

            system_text = ex.get("system", "")
            chat_text = ex.get("chat", "")

            if not system_text or not chat_text:
                examples_skipped += 1
                continue

            # Extract tool definitions (keep entire system text for context)
            tool_defs = extract_tool_definitions(system_text)

            # Combine wolf system + tool defs
            combined_system = f"{WOLF_SYSTEM_BASE}\n\n{tool_defs}"

            # Parse chat to messages
            msgs_raw = parse_chat_to_messages(chat_text)

            if len(msgs_raw) < 2:
                examples_skipped += 1
                continue

            # Build ChatML
            chatml_messages = [{"role": "system", "content": combined_system}]
            for role, content in msgs_raw:
                if role in ["user", "assistant"]:
                    chatml_messages.append({"role": role, "content": content})

            # Need at least user + assistant
            has_user = any(m["role"] == "user" for m in chatml_messages)
            has_assistant = any(m["role"] == "assistant" for m in chatml_messages)
            if not (has_user and has_assistant):
                examples_skipped += 1
                continue

            # Length check
            total_len = sum(len(m["content"]) for m in chatml_messages)
            if total_len > 16384 or total_len < 100:
                examples_skipped += 1
                continue

            # Write
            out = {
                "messages": chatml_messages,
                "source": "glaive_function_calling_v2",
                "tool_count": tool_defs.count('"name":')
            }
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
            examples_kept += 1

            if examples_kept % 4000 == 0:
                print(f"  [{examples_kept}/{TARGET_EXAMPLES}] skipped={examples_skipped}")

    print(f"\n[3/3] DONE!")
    print(f"  Kept: {examples_kept}")
    print(f"  Skipped: {examples_skipped}")
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
