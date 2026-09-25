#!/usr/bin/env python3
"""V8_Wolf GGUF Export — Try merge approach"""
import os
os.environ["XFORMERS_DISABLED"] = "1"
os.environ["UNSLOTH_DISABLE_XFORMERS"] = "1"

import torch
import unsloth
import unsloth_zoo
from unsloth import FastLanguageModel
from transformers import AutoTokenizer
from peft import PeftModel


BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
ADAPTER_PATH = "/workspace/v8_wolf/adapter"
OUTPUT_DIR = "/workspace/v8_wolf_merged_gguf"


def main():
    print("Loading base...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )

    print("Loading adapter...")
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)

    print("Merging LoRA into base...")
    try:
        model = model.merge_and_unload()
        print("  [OK] Merged")
    except Exception as e:
        print(f"  [WARN] Merge failed: {e}")
        return

    print("Exporting merged model to GGUF...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        model.save_pretrained_gguf(
            OUTPUT_DIR,
            tokenizer=tokenizer,
            quantization_method="q4_k_m",
        )
        print(f"  [OK] GGUF saved to {OUTPUT_DIR}")
    except Exception as e:
        print(f"  [FAIL] GGUF: {e}")
        # Save merged FP16 model at least
        merged_dir = f"{OUTPUT_DIR}/merged_fp16"
        model.save_pretrained(merged_dir)
        tokenizer.save_pretrained(merged_dir)
        print(f"  [INFO] Merged FP16 model saved to {merged_dir}")


if __name__ == "__main__":
    main()
