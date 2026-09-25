from datasets import load_dataset
import json

# Try Arabic LLM training datasets (verified to exist)
candidates = [
    "ajibawa-2023/Python-Code-23k-ShareGPT",  # exists
    "Open-Orca/OpenOrca",  # too big
    "tatsu-lab/alpaca",  # exists, English
    "yahma/alpaca-cleaned",
    "bigcode/the-stack-smol",
]

for name in candidates:
    try:
        print(f"=== {name} ===")
        ds = load_dataset(name, split="train", streaming=True)
        for i, ex in enumerate(ds):
            if i >= 1:
                break
            print(f"  Keys: {list(ex.keys())}")
            for k, v in ex.items():
                if isinstance(v, str):
                    print(f"    {k}: {v[:150]}")
                elif isinstance(v, list):
                    print(f"    {k}: list[{len(v)}]")
                else:
                    print(f"    {k}: {type(v).__name__}")
        print()
        break
    except Exception as e:
        print(f"  Error: {str(e)[:80]}")
        print()
