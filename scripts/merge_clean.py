import sys
sys.path.insert(0, ".")

from unsloth import FastLanguageModel
from peft import PeftModel
import torch
import json
import os

print("Loading base model (4-bit)...")
base, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Meta-Llama-3.1-8B-Instruct",
    max_seq_length=4096,
    load_in_4bit=True,
)

print("Loading v8_wolf adapter...")
model = PeftModel.from_pretrained(
    base,
    "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf",
)

print("Merging adapter into base model...")
model = model.merge_and_unload()

print("Saving merged model (clean state_dict, no quantization metadata)...")
save_dir = "E:/Trained intelligence models/alpha-wolf/models/v8_wolf_merged_clean"
os.makedirs(save_dir, exist_ok=True)

# Save only the model weights, stripping any quantization metadata
state_dict = model.state_dict()
# Remove any quantization-related keys
clean_sd = {}
for k, v in state_dict.items():
    if "quant" in k.lower() or "absmax" in k.lower():
        continue
    clean_sd[k] = v

torch.save(clean_sd, os.path.join(save_dir, "pytorch_model.bin"))
print(f"Saved {len(clean_sd)} tensors (removed {len(state_dict) - len(clean_sd)} quant tensors)")

# Save config without quantization_config
config = model.config.to_dict()
config.pop("quantization_config", None)
with open(os.path.join(save_dir, "config.json"), "w") as f:
    json.dump(config, f, indent=2)

# Save generation config
generation_config = model.generation_config.to_dict()
with open(os.path.join(save_dir, "generation_config.json"), "w") as f:
    json.dump(generation_config, f, indent=2)

# Save tokenizer
tokenizer.save_pretrained(save_dir)

print(f"DONE - clean merged model saved to {save_dir}")
