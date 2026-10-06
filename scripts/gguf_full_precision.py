import sys
sys.path.insert(0, ".")

from unsloth import FastLanguageModel
import torch

print("Loading merged model at FULL 16-bit precision (no quantization)...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="E:/Trained intelligence models/alpha-wolf/models/v8_wolf_merged",
    max_seq_length=4096,
    load_in_4bit=False,
    load_in_8bit=False,
    dtype=torch.bfloat16,
)

print("Exporting as GGUF (Q4_K_M)...")
model.save_pretrained_gguf(
    save_directory="E:/Trained intelligence models/alpha-wolf/models/v8_wolf_gguf",
    tokenizer=tokenizer,
    quantization_method="q4_k_m",
)
print("DONE - GGUF saved to E:/Trained intelligence models/alpha-wolf/models/v8_wolf_gguf")
