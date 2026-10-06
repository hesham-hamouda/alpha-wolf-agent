import sys
sys.path.insert(0, ".")

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

print("Loading merged model from disk...")
model = AutoModelForCausalLM.from_pretrained(
    "E:/Trained intelligence models/alpha-wolf/models/v8_wolf_merged",
    torch_dtype=torch.float16,
    device_map="auto",
    low_cpu_mem_usage=True,
)
tokenizer = AutoTokenizer.from_pretrained(
    "E:/Trained intelligence models/alpha-wolf/models/v8_wolf_merged",
)

print("Exporting as GGUF (Q4_K_M)...")
model.save_pretrained_gguf(
    save_directory="E:/Trained intelligence models/alpha-wolf/models/v8_wolf_gguf",
    tokenizer=tokenizer,
    quantization_method="q4_k_m",
)
print("DONE - GGUF saved to E:/Trained intelligence models/alpha-wolf/models/v8_wolf_gguf")
