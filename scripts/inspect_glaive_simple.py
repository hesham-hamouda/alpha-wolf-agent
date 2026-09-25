from datasets import load_dataset
import json

print("Loading glaiveai/glaive-function-calling-v2 (streaming)...")
try:
    ds = load_dataset("glaiveai/glaive-function-calling-v2", split="train", streaming=True)
    for i, ex in enumerate(ds):
        if i >= 2:
            break
        print(f"=== Example {i+1} ===")
        print(f"Keys: {list(ex.keys())}")
        for k, v in ex.items():
            if isinstance(v, str):
                print(f"  {k}: {v[:300]}")
            elif isinstance(v, list):
                print(f"  {k}: list[{len(v)}]")
                if v and isinstance(v[0], dict):
                    print(f"    first item keys: {list(v[0].keys())}")
                    print(f"    first item: {v[0]}")
            else:
                print(f"  {k}: {type(v).__name__} = {v}")
        print()
    print("DONE")
except Exception as e:
    print(f"Error: {e}")
