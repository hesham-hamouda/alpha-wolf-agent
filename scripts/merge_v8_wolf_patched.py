import sys
sys.path.insert(0, ".")

from unsloth import FastLanguageModel
from peft import PeftModel
import torch

# Monkey-patch to bypass revert_weight_conversion bug in transformers v5.5.0
import transformers.modeling_utils as _mu
_original_save = _mu.PreTrainedModel.save_pretrained
def _patched_save(self, *args, **kwargs):
    kwargs["safe_serialization"] = True
    try:
        return _original_save(self, *args, **kwargs)
    except NotImplementedError:
        pass
    import os
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

print("Saving merged model...")
save_dir = "E:/Trained intelligence models/alpha-wolf/models/v8_wolf_merged"
model.save_pretrained(save_dir, safe_serialization=True)
tokenizer.save_pretrained(save_dir)
print(f"DONE - merged model saved to {save_dir}")
