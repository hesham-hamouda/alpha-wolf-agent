#!/usr/bin/env python3
"""
Step 2a: Verify Unsloth Environment for Alpha Wolf Agent Training
Iron Law #15 (Verify Before Claim) + #44 (Methodology)
"""

import sys
import subprocess
import json

def check_docker():
    """Check if unsloth-alpha-wolf container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=unsloth", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def check_python():
    """Check Python version."""
    return f"Python: {sys.version}"

def check_torch():
    """Check PyTorch + CUDA."""
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if cuda_available else "CPU only"
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9 if cuda_available else 0
        return {
            "pytorch": torch.__version__,
            "cuda_available": cuda_available,
            "gpu_name": gpu_name,
            "gpu_memory_gb": round(gpu_memory, 1)
        }
    except Exception as e:
        return {"error": str(e)}

def check_unsloth():
    """Check Unsloth import (CRITICAL: must be before unsloth_zoo)."""
    try:
        import unsloth
        return {"unsloth": "OK (imported)"}
    except ImportError as e:
        return {"unsloth_error": str(e)}

def check_unsloth_zoo():
    """Check Unsloth Zoo (depends on env var from unsloth)."""
    try:
        import unsloth_zoo
        return {"unsloth_zoo": "OK"}
    except ImportError as e:
        return {"unsloth_zoo_error": str(e)}

def check_fast_language_model():
    """Check FastLanguageModel (the actual training class)."""
    try:
        from unsloth import FastLanguageModel
        return {"FastLanguageModel": "OK"}
    except Exception as e:
        return {"FastLanguageModel_error": str(e)}

def check_transformers():
    """Check transformers + peft + trl."""
    try:
        import transformers
        import peft
        import trl
        return {
            "transformers": transformers.__version__,
            "peft": peft.__version__,
            "trl": trl.__version__
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    print("=" * 60)
    print("ALPHA WOLF AGENT — Step 2a: Environment Verification")
    print("=" * 60)

    print("\n[1] Docker Container:")
    print(check_docker())

    print("\n[2] Python:")
    print(check_python())

    print("\n[3] PyTorch + CUDA:")
    print(json.dumps(check_torch(), indent=2))

    print("\n[4] Unsloth Import (CRITICAL — must be FIRST):")
    print(json.dumps(check_unsloth(), indent=2))

    print("\n[5] Unsloth Zoo (depends on env var from unsloth):")
    print(json.dumps(check_unsloth_zoo(), indent=2))

    print("\n[6] FastLanguageModel (training class):")
    print(json.dumps(check_fast_language_model(), indent=2))

    print("\n[7] Transformers + PEFT + TRL:")
    print(json.dumps(check_transformers(), indent=2))

    print("\n" + "=" * 60)
    print("Verification complete.")
    print("=" * 60)

if __name__ == "__main__":
    main()
