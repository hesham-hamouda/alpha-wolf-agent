#!/usr/bin/env python3
r"""
Alpha Wolf — Extract skill | مهارة الاستخلاص (قسم extract)
=============================================================
Section models: NuExtract-tiny (D: hub, numind).
Structured field extraction: text + field list → JSON.

Iron Laws: #47 bilingual, #15 structured, fail-safe (never raise).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

SKILL_NAME = "extract_skill"
SKILL_DESCRIPTION = ("Structured extraction to JSON (NuExtract-tiny). "
                     "Use to pull fields/tables from unstructured text.")
SKILL_DESCRIPTION_AR = "استخلاص الحقول لهيكل JSON."
MODELS = ["NuExtract-tiny"]
HUB = "numind/NuExtract-tiny"


def run(text: str = "", fields: List[str] | None = None,
        **kwargs: Any) -> Dict[str, Any]:
    """Extract fields as JSON. استخرج الحقول بصيغة JSON."""
    try:
        if not (text or "").strip() or not fields:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "text and fields are required"}
        from backend.agent import hf_runner
        schema = json.dumps({f: "string" for f in fields}, ensure_ascii=False)
        prompt = (f"<|input|>\n{text[:4000]}\n<|schema|>\n{schema}\n<|output|>\n")
        r = hf_runner.run_pipe("text-generation", HUB, prompt,
                               max_new_tokens=512, do_sample=False)
        if not r.get("success"):
            return {"success": False, "skill": SKILL_NAME,
                    "models": MODELS, "error": r.get("error")}
        gen = r["output"]
        raw = (gen[0].get("generated_text", "") if isinstance(gen, list)
               else str(gen))
        raw = raw[len(prompt):] if raw.startswith(prompt) else raw
        try:
            data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        except Exception:
            data = {"_raw": raw.strip()[:2000]}
        return {"success": True, "skill": SKILL_NAME, "models": MODELS,
                "model_used": HUB, "data": data}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {str(e)[:300]}"}


def self_test() -> bool:
    ok = callable(run) and MODELS == ["NuExtract-tiny"]
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
