import sys
sys.path.insert(0, ".")

from unsloth import FastLanguageModel
from peft import PeftModel
import torch

print("Loading base model (bnb-8bit)...")
base, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Meta-Llama-3.1-8B-Instruct-unsloth-bnb-8bit",
    max_seq_length=4096,
    load_in_4bit=False,
    load_in_8bit=True,
)

print("Loading v8_wolf adapter...")
model = PeftModel.from_pretrained(
    base,
    "E:/Trained intelligence models/alpha-wolf/adapters/v8_wolf",
)

print("Merging adapter into base model...")
model = model.merge_and_unload()

print("Exporting as GGUF (Q4_K_M)...")
model.save_pretrained_gguf(
    save_directory="E:/Trained intelligence models/alpha-wolf/models/v8_wolf_gguf",
    tokenizer=tokenizer,
    quantization_method="q4_k_m",
)
print("DONE - GGUF saved to E:/Trained intelligence models/alpha-wolf/models/v8_wolf_gguf")
