from datasets import load_dataset
import json

# Search known Arabic datasets
candidates = [
    "arbml/AraT5-base-arabic-dataset",
    "HusseinYoussef/Arabic_QA_Dataset",
    "MohamedRashad/arabic-qa",
    "Omartificial-Intelligence-Space/Arabic-Sentiment-Analysis",
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
                    print(f"    {k}: {v[:200]}")
                elif isinstance(v, list):
                    print(f"    {k}: list[{len(v)}]")
                else:
                    print(f"    {k}: {type(v).__name__}")
        print()
    except Exception as e:
        print(f"  Error: {str(e)[:80]}")
        print()
