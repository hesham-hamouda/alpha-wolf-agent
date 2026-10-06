import sys
sys.path.insert(0, ".")

from unsloth import FastLanguageModel
from peft import PeftModel
import torch

print("Loading base model (full precision for merge)...")
base, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Meta-Llama-3.1-8B-Instruct",
    max_seq_length=4096,
    load_in_4bit=False,
    dtype=torch.bfloat16,
)

print("Loading v8_wolf adapter...")
model = PeftModel.from_pretrained(
    base,
    "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf",
)

print("Merging adapter into base model...")
model = model.merge_and_unload()

print("Saving merged model (safe serialization)...")
model.save_pretrained(
    "E:/Trained intelligence models/alpha-wolf/models/v8_wolf_merged",
    safe_serialization=True,
)
tokenizer.save_pretrained(
    "E:/Trained intelligence models/alpha-wolf/models/v8_wolf_merged",
)
print("DONE - merged model saved to E:/Trained intelligence models/alpha-wolf/models/v8_wolf_merged")
