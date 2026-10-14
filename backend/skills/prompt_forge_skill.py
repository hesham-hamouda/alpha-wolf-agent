#!/usr/bin/env python3
r"""
Alpha Wolf — Prompt Forge skill | مهارة صياغة المطالب الاحترافية
==================================================================
Section: self-use — turns the leader's short/dialectal requests into
professional prompts for the Wolf itself, routed to the RIGHT capability.

Why this exists (2026-10-14, القائد): his requests are weak on purpose —
he is not technical. The agent must NOT ask him to "write a better
prompt"; it forges one itself and executes. Weak in → professional out.

Two jobs, honest about each:
  A. Detect the specialty (image / search / build / file / code / time /
     chat) from the raw request — offline, zero GPU, pure patterns.
  B. Forge the professional prompt for that specialty (task + context +
     constraints + output shape + quality bar) and name the exact route
     (skill or tool) that executes it. Image wording is delegated to
     qwen_image_skill (the specialist) — never duplicated here.

Iron Laws: #47 bilingual, #15 structured results, fail-safe (never raise).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

SKILL_NAME = "prompt_forge_skill"
SKILL_DESCRIPTION = ("Turn a weak, short, or dialectal user request into a "
                     "professional prompt for the agent itself, routed to the "
                     "correct skill/tool for execution. "
                     "Make sure to use this skill whenever the request is "
                     "thin, vague, dialectal, or missing details — even if "
                     "the user didn't ask for prompt help.")
SKILL_DESCRIPTION_AR = ("تحويل طلب المستخدم البسيط لأمر احترافي مع التوجيه "
                        "للقدرة الصحيحة — استخدمها مع أي طلب مختصر أو عامي.")

# -- scaffolding the leader never means as content ---------------------------
_DROP = (
    "من فضلك", "لو سمحت", "يعني", "كده", "زي", "شوية",
    "please",
)

# -- micro-gloss: leader's most common words → execution English --------------
_GLOSS = {
    "دولار": "dollar", "الذهب": "gold", "ذهب": "gold",
    "طقس": "weather", "الطقس": "weather",
    "سعر": "price", "اسعار": "prices", "أسعار": "prices",
    "اخبار": "news", "أخبار": "news",
    "النهاردة": "today", "اليوم": "today", "بسرعة": "quickly",
    "دور": "research", "دورلي": "research",
}


def _tokens(text: str) -> List[str]:
    return [t.strip(" \"'.,;!؟?،:()[]") for t in (text or "").split()]


def _core(request: str) -> str:
    """The request minus politeness scaffolding (never empty-guarded here)."""
    kept = [t for t in _tokens(request) if t and t not in _DROP]
    return " ".join(kept).strip()


def _norm(tok: str) -> str:
    """Definite-article + orthography tolerant lookup key."""
    t = (tok or "").strip()
    if len(t) > 3 and t.startswith("ال"):
        t = t[2:]
    return t.replace("ة", "ه").replace("أ", "ا").replace("إ", "ا")


_NORM_GLOSS = {t: v for t, v in _GLOSS.items()}
_NORM_GLOSS.update({
    "على": "of",
    "الدولار": "dollar",
})


def _gloss_en(text: str) -> str:
    out = []
    for t in _tokens(text):
        if not t:
            continue
        hit = (_GLOSS.get(t) or _NORM_GLOSS.get(t)
               or _NORM_GLOSS.get(_norm(t)))
        if hit is None:
            hit = next((v for k, v in _GLOSS.items()
                        if _norm(k) == _norm(t)), t)
        out.append(hit)
    return " ".join(out).strip()


def detect_specialty(request: str) -> str:
    """Route the raw request to one specialty (offline patterns).

    تحديد التخصص من الطلب الخام — أنماط فقط بلا موديل.
    """
    import re
    t = request or ""
    if re.search(r"(أنشئ|انشئ|إنشئ|ارسم|تخيل|صور|صورة|generate|create|draw|"
                 r"paint|imagine|دلفين|دلافين|قط|كلب|شاطئ|horse|beach|cat|dog)",
                 t, re.IGNORECASE):
        return "image"
    if re.search(r"(دور|ابحث|سعر|اسعار|أسعار|اخبار|أخبار|طقس|search|news|"
                 r"price|weather|دولار|ذهب)", t, re.IGNORECASE):
        return "search"
    if re.search(r"(اعمل|ابني|أنشئ تطبيق|اعملي|برنامج|موقع|تطبيق|app|website|"
                 r"program|لعبة)", t, re.IGNORECASE):
        return "build"
    if re.search(r"(اقرأ|افتح|اعرض|ملف|مجلد|read|list|file)", t,
                 re.IGNORECASE):
        return "file"
    if re.search(r"(شغل|نفذ|كود|run|execute|code|احسب)", t, re.IGNORECASE):
        return "code"
    if re.search(r"(التاريخ|الساعة|النهاردة.*الساعة|date|time|اليوم.*تاريخ)",
                 t, re.IGNORECASE):
        return "time"
    return "chat"


_ROUTES = {
    "image": {"skill": "qwen_image_skill"},
    "search": {"tool": "web_search"},
    "build": {"tool": "write_file"},
    "file": {"tool": "read_file"},
    "code": {"tool": "execute_python"},
    "time": {"tool": "system_time"},
    "chat": {},
}


def _forge_image(core: str) -> str:
    """Delegate wording to the image specialist (leverage, never duplicate)."""
    try:
        from backend.skills import qwen_image_skill as _qi
        eng = _qi.engineer_prompt(core or "")
        return eng.get("prompt", core)
    except Exception:
        return (f"Create a professional image: {core}. Requirements: sharp "
                f"focus, natural colors, cinematic light, true-to-life "
                f"detail, clean composition.")


def _forge_search(core: str) -> str:
    q = _gloss_en(core)
    return (f"Web research task: {q}. Requirements: fresh results first "
            f"(recency matters — note dates), at least 2 primary sources "
            f"with links, then an Arabic summary with cited numbers.")


def _forge_build(core: str) -> str:
    return (f"Build task: {core}. Plan: 1) write EVERY file under the "
            f"projects folder, 2) install deps if needed, 3) RUN it and "
            f"capture real output, 4) report paths + proof. Never claim "
            f"done without executed output.")


def _forge_generic(core: str, specialty: str) -> str:
    return (f"Task ({specialty}): {core}. Requirements: execute with the "
            f"routed tool, show real tool output as proof, answer in the "
            f"user's language (Arabic default).")


def run(request: str = "", specialty: str = "auto",
        **kwargs: Any) -> Dict[str, Any]:
    """Forge a weak request into a professional prompt + route.

    حوّل طلباً بسيطاً لأمر احترافي مع التوجيه للقدرة الصحيحة.
    """
    try:
        raw = (request or "").strip()
        if not raw:
            return {"success": False, "skill": SKILL_NAME,
                    "error": "request is required | الطلب مطلوب"}
        spec = (specialty or "auto").strip().lower()
        if spec in ("auto", ""):
            spec = detect_specialty(raw)
        if spec not in _ROUTES:
            spec = "chat"
        core = _core(raw)
        if spec == "image":
            pro = _forge_image(core)
        elif spec == "search":
            pro = _forge_search(core)
        elif spec == "build":
            pro = _forge_build(core)
        elif spec == "chat":
            pro = _forge_generic(core, spec)
        else:
            pro = _forge_generic(core, spec)
        clarify = ""
        if not core or (spec == "chat" and len(core.split()) <= 2):
            clarify = ("ممكن توضح عايز إيه بالظبط؟ صورة؟ بحث على النت؟ "
                       "برنامج؟ ملف؟ | Which one: image, web search, app, "
                       "file, or code?")
        return {"success": True, "skill": SKILL_NAME,
                "specialty": spec, "route": dict(_ROUTES[spec]),
                "professional_prompt": pro, "clarify": clarify,
                "core": core}
    except Exception as e:
        return {"success": False, "skill": SKILL_NAME,
                "error": f"{type(e).__name__}: {e}"}


def self_test() -> bool:
    print("prompt_forge_skill: offline forge check (no GPU, no network)")
    r1 = run(request="انشئ صور دلافين تطارد السمك تحت الماء مثل الحقيقه")
    r2 = run(request="ظبط الدنيا")
    checks = [
        r1.get("specialty") == "image"
        and r1.get("route") == {"skill": "qwen_image_skill"},
        "dolphin" in r1.get("professional_prompt", "").lower(),
        bool(r2.get("clarify")) and r2.get("route") == {},
        callable(run),
    ]
    print("SELF-TEST:", "PASSED" if all(checks) else f"FAILED {checks}")
    return bool(all(checks))


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)
