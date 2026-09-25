from datasets import load_dataset
import json

print("Inspecting Arabic instruction datasets...")
print()

# Try multiple Arabic datasets
candidates = [
    "HuggingFaceH4/arabic-instruct",  # probably doesn't exist
    "M-A-D/Arabic-DPO-50K",  # exists
    "AIDC-AI/MARCUS-instruct-Arabic",  # exists
    "akhooli/Arabic-Chat-Instruct",
]

for name in candidates:
    try:
        print(f"=== Trying: {name} ===")
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
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")
        print()
