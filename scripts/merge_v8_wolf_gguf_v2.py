import sys
sys.path.insert(0, ".")

from unsloth import FastLanguageModel
from peft import PeftModel
import torch
import os

# Monkey-patch to bypass revert_weight_conversion bug
import transformers.modeling_utils as _mu
_original_save = _mu.PreTrainedModel.save_pretrained
def _patched_save(self, *args, **kwargs):
    try:
        return _original_save(self, *args, **kwargs)
    except (NotImplementedError, RuntimeError):
        pass
    os.makedirs(args[0] if args else kwargs.get("save_directory", "."), exist_ok=True)
    state_dict = self.state_dict()
    torch.save(state_dict, os.path.join(args[0] if args else kwargs["save_directory"], "pytorch_model.bin"))
    return None
_mu.PreTrainedModel.save_pretrained = _patched_save

print("Loading base model...")
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

print("Exporting as GGUF (Q4_K_M) with monkey-patch...")
try:
    model.save_pretrained_gguf(
        save_directory="E:/Trained intelligence models/alpha-wolf/models/v8_wolf_gguf",
        tokenizer=tokenizer,
        quantization_method="q4_k_m",
    )
    print("DONE - GGUF saved")
except Exception as e:
    print(f"GGUF export failed: {e}")
    print("Trying alternative: save as fp16 then convert...")
    model.save_pretrained(
        "E:/Trained intelligence models/alpha-wolf/models/v8_wolf_fp16",
        safe_serialization=True,
    )
    tokenizer.save_pretrained("E:/Trained intelligence models/alpha-wolf/models/v8_wolf_fp16")
    print("FP16 saved - convert to GGUF manually with llama.cpp")
