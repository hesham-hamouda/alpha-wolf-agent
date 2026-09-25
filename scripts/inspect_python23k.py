from datasets import load_dataset

print("Inspecting ajibawa-2023/Python-Code-23k-ShareGPT...")
ds = load_dataset("ajibawa-2023/Python-Code-23k-ShareGPT", split="train", streaming=True)
for i, ex in enumerate(ds):
    if i >= 1:
        break
    print(f"Keys: {list(ex.keys())}")
    print(f"Conversations: {ex['conversations']}")
    print(f"Type of conv[0]: {type(ex['conversations'][0])}")
    print(f"Conv[0]: {ex['conversations'][0]}")
    print(f"Conv[1]: {ex['conversations'][1]}")
