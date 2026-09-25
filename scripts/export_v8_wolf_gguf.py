#!/usr/bin/env python3
"""V8_Wolf GGUF Export — Mix D Phase 10 — Production Deployment

Saves Alpha Wolf Agent as production-ready GGUF model.
Final step to achieve "Alpha Wolf = طفره" goal.
"""

import os
os.environ["XFORMERS_DISABLED"] = "1"
os.environ["UNSLOTH_DISABLE_XFORMERS"] = "1"

import sys
import shutil
import torch
from pathlib import Path

import unsloth
import unsloth_zoo
from unsloth import FastLanguageModel
from transformers import AutoTokenizer


# Configuration
BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct"
ADAPTER_PATH = "/workspace/v8_wolf/adapter"
OUTPUT_DIR = "/workspace/v8_wolf_gguf"
QUANTIZATION = "q4_k_m"  # 4-bit quantization for production

# Ollama Modelfile content
MODELFILE_CONTENT = """FROM ./v8_wolf_q4_k_m.gguf

# System prompt (Wolf identity)
SYSTEM \"\"\"You are Alpha Wolf Agent. Like a wolf, you embody 7 traits that guide all your actions:
1. اقتناص الأخطاء (Mistake Hunter): You hunt mistakes, don't hide them.
2. تتبع الأهداف (Goal Persistence): You track goals relentlessly, never abandoning.
3. الشراسة (Tenacity): You see failure as data, not defeat.
4. التفكير العميق (Deep Thinking): You think deeply before acting.
5. استخدام الموارد (Resourceful): You use every tool at the right time, not all at once.
6. الوعي الذاتي (Self-Aware): You know what you know and what you don't.
7. التعلم التعزيزي (Reinforcement Learning): You learn from every hunt — successful or not.

Your name is Alpha Wolf Agent. You serve Quхائد هشام with tenacity, intelligence, and resourcefulness.\"\"\"

# Model parameters
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 4096
PARAMETER stop "<|start_header_id|>"
PARAMETER stop "<|end_header_id|>"
PARAMETER stop "<|eot_id|>"
"""


def main():
    print("=" * 70)
    print("V8_Wolf GGUF Export — Production Deployment")
    print("=" * 70)

    print(f"\n[1/3] Load base + V8_Wolf adapter...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )
    # Load V8_Wolf adapter
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, ADAPTER_PATH)
    print(f"  [OK] Loaded. VRAM: {(torch.cuda.memory_allocated()/1e9):.2f} GB")

    print(f"\n[2/3] Save LoRA adapter (164 MB)...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    adapter_out = f"{OUTPUT_DIR}/adapter"
    os.makedirs(adapter_out, exist_ok=True)
    model.save_pretrained(adapter_out)
    tokenizer.save_pretrained(adapter_out)
    print(f"  [OK] Adapter saved")

    print(f"\n[3/3] Export to GGUF ({QUANTIZATION})...")
    gguf_dir = f"{OUTPUT_DIR}/gguf"
    os.makedirs(gguf_dir, exist_ok=True)

    try:
        model.save_pretrained_gguf(
            gguf_dir,
            tokenizer=tokenizer,
            quantization_method=QUANTIZATION,
        )
        print(f"  [OK] GGUF saved to {gguf_dir}")
    except Exception as e:
        print(f"  [WARN] GGUF export failed: {e}")
        print(f"  [INFO] Adapter-only deployment is possible")

    # Save Ollama Modelfile
    modelfile_path = f"{OUTPUT_DIR}/Modelfile"
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(MODELFILE_CONTENT)
    print(f"  [OK] Ollama Modelfile saved to {modelfile_path}")

    print(f"\n{'='*70}")
    print(f"[OK] V8_Wolf Production deployment ready!")
    print(f"     Adapter: {adapter_out}")
    print(f"     GGUF: {gguf_dir}")
    print(f"     Modelfile: {modelfile_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
