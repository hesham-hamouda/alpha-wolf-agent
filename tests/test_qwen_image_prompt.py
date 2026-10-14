#!/usr/bin/env python3
"""Regression: cat→man bug 2026-10-14 — spaced Windows path + AR verbs polluted visual prompt."""
from backend.skills import qwen_image_skill as qis


def test_spaced_quoted_path_stripped():
    idea = 'انشئ لى صوره فى هذا المسار لقط صغير يلعب "D:\\A\\Applications under development\\TESTS\\صور"'
    p = qis.engineer_prompt(idea)["prompt"]
    low = p.lower()
    assert "under development" not in low, p
    assert "tests" not in low, p
    assert "d:" not in low, p
    assert "kitten" in low and "playing" in low, p


def test_instruction_verbs_stripped():
    p = qis.engineer_prompt('انشئ لى صوره لقط صغير يلعب')["prompt"]
    assert "انشئ" not in p, p
    assert "المسار" not in p, p
    assert "kitten" in p.lower(), p


def test_animal_neutral_template():
    p = qis.engineer_prompt('قط صغير يلعب')["prompt"]
    assert "ears, paws, tails" in p, p


def test_family_horses_beach_gloss():
    p = qis.engineer_prompt(
        "انشئ صورة لأب وابنه وبنته وزوجته يركبون الخيل على الشاطئ في راس البر"
    )["prompt"]
    low = p.lower()
    for w in ("father", "son", "daughter", "wife", "riding",
              "horses", "beach", "ras"):
        assert w in low, p


def test_weak_request_becomes_professional_beach_family():
    """Leader demand: weak AR request → professional EN scene (Self-Capability)."""
    p = qis.engineer_prompt(
        "انشئ صورة لأب وابنه وبنته وزوجته يركبون الخيل على الشاطئ في راس البر"
    )["prompt"]
    low = p.lower()
    # fluent group, not word salad
    assert "family" in low, p
    assert "horse" in low, p  # horses/horseback ok
    # professional photography language (natural, never banned stuffing)
    assert any(k in low for k in (
        "golden hour", "cinematic", "depth of field", "85mm",
        "wide-angle", "wide angle", "motion")), p
    # no instruction/path residue
    for bad in ("انشئ", "المسار", "under development", "d:"):
        assert bad not in low, p


def test_weak_request_becomes_professional_cat():
    p = qis.engineer_prompt("قط صغير يلعب")["prompt"]
    low = p.lower()
    assert "kitten" in low or "cat" in low, p
    assert any(k in low for k in (
        "fur detail", "whisker", "shallow depth of field",
        "catchlight", "cinematic")), p


def test_negative_prompt_guards_quality():
    """Render seam: every prompt ships a quality-guarding negative prompt."""
    eng = qis.engineer_prompt("قط صغير يلعب")
    neg = eng.get("negative_prompt", "")
    low = neg.lower()
    assert "blurry" in low, neg
    assert any(k in low for k in ("extra limbs", "distorted", "watermark")), neg
    assert "8k" not in low and "masterpiece" not in low, neg


def test_pending_path_carries_professional_prompt(monkeypatch):
    """Delivery seam (offline): pending result keeps the full pro prompt."""
    monkeypatch.setattr(qis, "_comfy_alive", lambda timeout=5: False)
    monkeypatch.setattr(qis, "_ensure_comfy", lambda wait_s=150: False)
    res = qis.run(idea="انشئ صورة لأب وابنه وبنته وزوجته يركبون الخيل على الشاطئ في راس البر")
    assert res.get("runner") == "pending", res
    eng = res.get("engineered", {})
    assert "family" in eng.get("prompt", "").lower(), eng
    assert eng.get("negative_prompt", ""), eng


def test_partial_family_not_overfit():
    """Review fix: father+son must not render daughter/wife/Ras-El-Bar."""
    p = qis.engineer_prompt("انشئ صورة لأب وابنه يركبون الخيل")["prompt"]
    low = p.lower()
    assert "father" in low and "son" in low, p
    assert "daughter" not in low and "wife" not in low, p
    assert "ras el bar" not in low, p


def test_generic_cat_sentence_wellformed():
    p = qis.engineer_prompt("قط كبير")["prompt"]
    assert "A cat" in p, p
    assert "A cat  " not in p, p  # no doubled space from empty rest


def test_dolphins_underwater_professional():
    """Sea-life seam: weak AR dolphin request → EN underwater cinema."""
    p = qis.engineer_prompt("انشئ صور دلافين تطارد السمك تحت الماء مثل الحقيقه")["prompt"]
    low = p.lower()
    assert "dolphin" in low, p
    assert "fish" in low, p
    assert any(k in low for k in ("underwater", "ocean", "deep blue")), p
    assert any(k in low for k in ("cinematic", "sun rays", "sunrays",
                                  "depth of field", "motion")), p
    for bad in ("انشئ", "مثل الحقيقه", "مثل الحقيقة"):
        assert bad not in low, p


def test_ensure_comfy_already_up_no_launch(monkeypatch):
    """Ordinary-user seam: ComfyUI up → True, launcher never touched."""
    monkeypatch.setattr(qis, "_comfy_alive", lambda timeout=5: True)
    launched = []
    monkeypatch.setattr(qis, "_launch_comfy", lambda: launched.append(1) or False)
    assert qis._ensure_comfy(wait_s=1) is True
    assert launched == []


def test_ensure_comfy_down_no_venv_fast_fail(monkeypatch):
    monkeypatch.setattr(qis, "_comfy_alive", lambda timeout=5: False)
    monkeypatch.setattr(qis, "_COMFY_VENV_PY", "D:\\nope\\python.exe")
    assert qis._ensure_comfy(wait_s=1) is False


def test_ensure_comfy_down_launch_recovers(monkeypatch):
    states = {"up": False}
    monkeypatch.setattr(qis, "_comfy_alive", lambda timeout=5: states["up"])

    def fake_launch():
        states["up"] = True
        return True

    monkeypatch.setattr(qis, "_launch_comfy", fake_launch)
    assert qis._ensure_comfy(wait_s=5) is True


def test_pending_message_tells_user_plainly(monkeypatch):
    """Pending seam: no tech jargon, says what happened + what to do."""
    monkeypatch.setattr(qis, "_comfy_alive", lambda timeout=5: False)
    monkeypatch.setattr(qis, "_ensure_comfy", lambda wait_s=150: False)
    res = qis.run(idea="قط صغير يلعب")
    assert res.get("runner") == "pending", res
    err = res.get("error", "")
    assert "ComfyUI" not in err or "برنامج الرسم" in err, err


def test_selftest_contract():
    assert qis.self_test() is True
