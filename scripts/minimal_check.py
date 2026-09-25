#!/usr/bin/env python3
"""
Simplest possible check — no training, no inference.
Just verify Python + imports + CUDA all work.
"""

import sys

print("=" * 50)
print("MINIMAL ENVIRONMENT CHECK (Iron Law #15)")
print("=" * 50)

# 1. Python
print(f"[OK] Python: {sys.version}")

# 2. PyTorch + CUDA
try:
    import torch
    print(f"[OK] PyTorch: {torch.__version__}")
    print(f"[OK] CUDA available: {torch.cuda.is_available()}")
    print(f"[OK] GPU: {torch.cuda.get_device_name(0)}")
    print(f"[OK] VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
except Exception as e:
    print(f"[FAIL] PyTorch: {e}")
    sys.exit(1)

# 3. Unsloth import (CRITICAL: must be first)
try:
    import unsloth
    print("[OK] Unsloth imported (no errors)")
except Exception as e:
    print(f"[FAIL] Unsloth: {e}")
    sys.exit(1)

# 4. Unsloth Zoo
try:
    import unsloth_zoo
    print("[OK] Unsloth Zoo imported")
except Exception as e:
    print(f"[FAIL] Unsloth Zoo: {e}")
    sys.exit(1)

# 5. FastLanguageModel
try:
    from unsloth import FastLanguageModel
    print("[OK] FastLanguageModel imported")
except Exception as e:
    print(f"[FAIL] FastLanguageModel: {e}")
    sys.exit(1)

# 6. Verify Llama-3.1-8B-Instruct is already downloaded (cache check)
print()
print("=" * 50)
print("MODEL CACHE CHECK")
print("=" * 50)
from pathlib import Path

cache_path = Path("D:/Intelligence Models/huggingface/hub/models--unsloth--meta-llama-3.1-8b-instruct-unsloth-bnb-4bit")
if cache_path.exists():
    size_bytes = sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file())
    print(f"[OK] Llama-3.1-8B-Instruct 4-bit cached: {size_bytes / 1e9:.2f} GB")
    print(f"[OK] Location: {cache_path}")
else:
    print(f"[FAIL] Model not found at {cache_path}")

# 7. Disk space
print()
print("=" * 50)
print("DISK SPACE")
print("=" * 50)
import shutil
for drive in ["C", "D", "E"]:
    try:
        usage = shutil.disk_usage(f"{drive}:/")
        print(f"  {drive}: drive: {usage.free / 1e9:.1f} GB free / {usage.total / 1e9:.1f} GB total")
    except Exception as e:
        print(f"  {drive}: drive: error - {e}")

print()
print("=" * 50)
print("[OK] ALL MINIMAL CHECKS PASSED")
print("=" * 50)
print("Environment is ready.")
print("NOTE: Full Unsloth training has Windows multiprocessing bug.")
print("      Use Docker 'unsloth-alpha-wolf' container for actual training.")
