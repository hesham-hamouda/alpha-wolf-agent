#!/usr/bin/env python3
"""prompt_forge_skill: weak user request → professional prompt + right route."""
from backend.skills import prompt_forge_skill as pf


def test_weak_image_request_forged_and_routed():
    r = pf.run(request="انشئ صور دلافين تطارد السمك تحت الماء مثل الحقيقه")
    assert r["success"], r
    assert r["specialty"] == "image", r
    assert r["route"] == {"skill": "qwen_image_skill"}, r
    p = r["professional_prompt"].lower()
    assert "dolphin" in p and "underwater" in p, p
    assert "انشئ" not in r["professional_prompt"], p


def test_weak_search_request_forged_and_routed():
    r = pf.run(request="دورلي على سعر الدولار النهاردة بسرعة")
    assert r["success"], r
    assert r["specialty"] == "search", r
    assert r["route"] == {"tool": "web_search"}, r
    p = r["professional_prompt"].lower()
    assert "dollar" in p or "exchange rate" in p, p
    assert "sources" in p or "recency" in p or "today" in p, p


def test_thin_request_asks_back():
    r = pf.run(request="ظبط الدنيا")
    assert r["success"], r
    assert r["clarify"], r
    assert r["route"] == {}, r


def test_selftest_contract():
    assert pf.self_test() is True
