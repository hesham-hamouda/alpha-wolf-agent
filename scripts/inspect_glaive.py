#!/usr/bin/env python3
"""
Inspect glaive-function-calling-v2 dataset structure before downloading.

Per Iron Law #15 (Verify Before Claim): Know what you're downloading first.
"""

import sys
import subprocess

# Script that loads and prints 2 examples
inspect_script = '''
import sys
sys.stdout.reconfigure(line_buffering=True)

from datasets import load_dataset

print("Loading glaiveai/glaive-function-calling-v2 (streaming)...")
ds = load_dataset("glaiveai/glaive-function-calling-v2", split="train", streaming=True)

for i, ex in enumerate(ds):
    if i >= 2:
        break
    print(f"=== Example {i+1} ===")
    print(f"Keys: {list(ex.keys())}")
    for k, v in ex.items():
        if isinstance(v, str):
            print(f"  {k}: {v[:300]}{"..." if len(v) > 300 else ""}")
        elif isinstance(v, list):
            print(f"  {k}: list[{len(v)}]")
            if v:
                print(f"    first item type: {type(v[0]).__name__}")
                if isinstance(v[0], dict):
                    print(f"    first item keys: {list(v[0].keys())}")
                    print(f"    first item: {v[0]}")
        else:
            print(f"  {k}: {type(v).__name__} = {v}")
    print()
print("DONE")
'''

import os
log_path = r"E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\glaive_inspect.log"
with open(log_path, "w") as f:
    result = subprocess.run(
        ["python", "-c", inspect_script],
        stdout=f, stderr=subprocess.STDOUT,
        timeout=180
    )

with open(log_path, "r") as f:
    print(f.read())

os.remove(log_path)
