#!/usr/bin/env python3
r"""
Alpha Wolf — Math skill | مهارة الرياضيات (قسم math)
======================================================
Section models: Qwen2.5-Math-1.5B (D: hub, Qwen instruct).
Rule (Jev): the small model proposes, CODE disposes — numeric answers are
re-checked with sympy/python when the problem is closed-form.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

import re
from typing import Any, Dict

SKILL_NAME = "math_skill"
SKILL_DESCRIPTION = ("Math problem solving (Qwen2.5-Math-1.5B, verified in code). "
                     "Use for equations, integrals, derivatives, word problems.")
SKILL_DESCRIPTION_AR = "حل المسائل الرياضية مع تحقق برمجي."
MODELS = ["Qwen2.5-Math-1.5B"]
HUB = "Qwen/Qwen2.5-Math-1.5B-Instruct"


def _verify_closed_form(problem: str, answer: str) -> Dict[str, Any]:
    """Try sympy for arithmetic/single-equation checks. Best-effort."""
    try:
        import sympy
        nums = re.findall(r"-?\d+(?:\.\d+)?", answer)
        if not nums or not re.search(r"[+\-*/^=]", problem):
            return {"checked": False, "reason": "not closed-form"}
        expr = re.sub(r"[^0-9+\-*/().^ ]", "", problem.split("=")[0])
        expr = expr.replace("^", "**")
        if not expr.strip():
            return {"checked": False, "reason": "no expression"}
        val = float(sympy.sympify(expr).evalf())
        return {"checked": True, "code_value": val,
                "model_value": float(nums[-1]),
                "agree": abs(val - float(nums[-1])) < 1e-6}
    except Exception as e:
        return {"checked": False, "reason": f"{type(e).__name__}"}


def run(problem: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Solve a math problem (model proposes, code verifies). حل مسألة رياضية."""
    try:
        if not (problem or "").strip():
            return {"success": False, "skill": SKILL_NAME,
                    "error": "problem is required"}
        from backend.agent import hf_runner
        sys_prompt = ("You are a math solver. Solve step by step, end with "
                      "the final numeric result on its own line.")
        r = hf_runner.run_pipe("text-generation", HUB,
                               f"{sys_prompt}\nProblem: {problem}\nSolution:",
                               max_new_tokens=512, do_sample=False)
        if not r.get("success"):
            return {"success": False, "skill": SKILL_NAME,
                    "models": MODELS, "error": r.get("error")}
        gen = r["output"]
        answer = (gen[0].get("generated_text", "") if isinstance(gen, list)
                  else str(gen)).strip()
        _prefix = f"{sys_prompt}\nProblem: {problem}\nSolution:"
        if answer.startswith(_prefix):
            answer = answer[len(_prefix):].strip()
        check = _verify_closed_form(problem, answer)
        return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                "model_used": HUB, "answer": answer, "code_check": check}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    c = _verify_closed_form("2+2*3", "result 8")
    ok = callable(run) and c.get("checked") and c.get("agree")
    print("SELF-TEST:", "PASSED" if ok else f"FAILED {c}")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
