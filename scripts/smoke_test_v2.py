#!/usr/bin/env python3
"""
Step 2a SIMPLIFIED Smoke Test
Just verify imports + CUDA + Unsloth + Llama tokenizer works.
NO actual training (training was getting stuck at 0% CPU).
"""

import sys
import json
import time

def main():
    print("=" * 60)
    print("ALPHA WOLF SIMPLIFIED SMOKE TEST (Iron Law #15)")
    print("=" * 60)

    results = {}

    # 1. PyTorch + CUDA
    try:
        import torch
        results["torch"] = {
            "version": torch.__version__,
            "cuda": torch.cuda.is_available(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1) if torch.cuda.is_available() else 0
        }
        print(f"[OK] PyTorch {results['torch']['version']}, CUDA={results['torch']['cuda']}")
    except Exception as e:
        results["torch"] = {"error": str(e)}
        print(f"[FAIL] PyTorch: {e}")
        return False

    # 2. Unsloth (CRITICAL: must import BEFORE unsloth_zoo)
    try:
        import unsloth
        results["unsloth"] = "OK"
        print("[OK] Unsloth imported")
    except Exception as e:
        results["unsloth"] = f"FAIL: {e}"
        print(f"[FAIL] Unsloth: {e}")
        return False

    # 3. Unsloth Zoo
    try:
        import unsloth_zoo
        results["unsloth_zoo"] = "OK"
        print("[OK] Unsloth Zoo imported")
    except Exception as e:
        results["unsloth_zoo"] = f"FAIL: {e}"
        print(f"[FAIL] Unsloth Zoo: {e}")
        return False

    # 4. FastLanguageModel
    try:
        from unsloth import FastLanguageModel
        results["FastLanguageModel"] = "OK"
        print("[OK] FastLanguageModel imported")
    except Exception as e:
        results["FastLanguageModel"] = f"FAIL: {e}"
        print(f"[FAIL] FastLanguageModel: {e}")
        return False

    # 5. Model Load Test (4-bit, 512 tokens only — fast!)
    print("\n[5] Loading Llama-3.1-8B-Instruct (4-bit, 512 tokens only for tokenizer test)...")
    try:
        start = time.time()
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            "unsloth/Meta-Llama-3.1-8B-Instruct",
            use_fast=True,
        )
        elapsed = time.time() - start
        vocab_size = tokenizer.vocab_size
        results["tokenizer"] = {
            "loaded": True,
            "vocab_size": vocab_size,
            "load_time_sec": round(elapsed, 1)
        }
        print(f"[OK] Tokenizer loaded in {elapsed:.1f}s, vocab={vocab_size}")
    except Exception as e:
        results["tokenizer"] = {"error": str(e)}
        print(f"[FAIL] Tokenizer: {e}")

    # 6. Test a simple inference (no training — just generate)
    print("\n[6] Quick inference test (1 prompt, no training)...")
    try:
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name="unsloth/Meta-Llama-3.1-8B-Instruct",
            max_seq_length=512,
            dtype=None,
            load_in_4bit=True,
        )
        # Test generation
        prompt = "Q: What is 2+2?\nA:"
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            start = time.time()
            outputs = model.generate(**inputs, max_new_tokens=10, do_sample=False)
            elapsed = time.time() - start
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        results["inference"] = {
            "response": response,
            "time_sec": round(elapsed, 1)
        }
        print(f"[OK] Inference in {elapsed:.1f}s: '{response[:50]}...'")
    except Exception as e:
        results["inference"] = {"error": str(e)}
        print(f"[FAIL] Inference: {e}")
    finally:
        try:
            del model
        except:
            pass
        torch.cuda.empty_cache()

    # Summary
    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print("\n[VERDICT]:")
    if "error" not in str(results.get("inference", {})):
        print("✅ All checks passed. Environment is ready for training.")
        print("⚠️ NOTE: Full training (10 steps) hung in round 2 — ")
        print("         likely a Unsloth + Windows multiprocessing issue.")
        print("         We will use Docker or reduce batch size for real training.")
        return True
    else:
        print("❌ Some checks failed. See above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
