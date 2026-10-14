"""Bridge offline tests — no model loads, no DB writes (skipped paths only)."""
from backend.agent import model_router_bridge as b


def test_route_chat_defaults_spark():
    r = b.route_chat("اشرح الفرق بين الذئب والثعلب")
    assert r["model"] == b.SPARK
    assert r["section"] == "chat"


def test_route_chat_detects_code_section():
    r = b.route_chat("اكتب دالة بايثون تفرز قائمة")
    assert r["section"] == "code"
    assert r["model"] == b.SPARK  # chat still served by spark


def test_fallback_chain_order():
    assert b.fallback_next(b.SPARK) == "qwen3:4b"
    assert b.fallback_next("qwen3:4b") == "qwen2.5:1.5b"
    assert b.fallback_next("qwen2.5:0.5b") == ""  # exhausted → escalate honestly


def test_pick_vision_light_colives():
    p = b.pick_vision("اوصف لقطة الشاشة")
    assert p["model"] == "moondream:latest"
    assert p["vram_action"] == "co_live"


def test_pick_vision_flagship_parks_chat():
    p = b.pick_vision("حلّل المخطط الهندسي بدقة عالية")
    assert p["model"] == "qwen2.5vl:7b"
    assert p["vram_action"] == "unload_chat_first"


def test_govern_colive_noop():
    g = b.govern_vram_for("moondream:latest", ollama_url="http://127.0.0.1:9")
    assert g["unloaded"] == []


def test_distill_skips_errors_and_shorts():
    assert b.maybe_distill_turn([], {"status": "backend_unavailable"})["distilled"] is False
    ok = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
    assert b.maybe_distill_turn([{"role": "user", "content": "hi"}], ok)["distilled"] is False


def test_route_chat_longform_stays_spark():
    # PHILOSOPHY 2026-10-14 (leader): spark primary for ALL text; others are
    # backup-on-failure only. Pre-emptive rerouting was my violation — locked.
    r = b.route_chat("اكتب مقالا موسعا عن الطاقة")
    assert r["model"] == b.SPARK
    r = b.route_chat("Write a long article about solar")
    assert r["model"] == b.SPARK


def test_route_chat_normal_stays_spark():
    r = b.route_chat("ما اسمك؟")
    assert r["model"] == b.SPARK


def test_pick_image_turbo_first():
    p = b.pick_image("sunset over the sea")
    assert p["model"] == "qwen-image-2.1-turbo-int8"
    assert p["vram_action"] == "unload_chat_first"


def test_pick_ocr_chandra_first():
    p = b.pick_ocr("استخرج نص العقد")
    assert p["model"] == "chandra-ocr-2"
    assert p["vram_action"] == "unload_chat_first"


def test_govern_heavy_never_raises_offline():
    g = b.govern_vram_for("chandra-ocr-2", ollama_url="http://127.0.0.1:9")
    assert isinstance(g["unloaded"], list)
    g = b.govern_vram_for("qwen-image-2.1-turbo-int8", ollama_url="http://127.0.0.1:9")
    assert isinstance(g["unloaded"], list)
