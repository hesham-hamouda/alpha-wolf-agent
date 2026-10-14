"""Section-chat mapping tests — offline (pending/unknown paths only, no loads)."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "frontend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "frontend"))

from backend.agent import model_router_bridge as b
from backend.agent.streaming import MEASURED_SERVED_CTX, MEASURED_ARCH_CTX
from backend.main import _AVAILABLE_MODELS, _resolve_model
from utils import MODEL_DISPLAY


def test_every_entry_synced():
    for e in b.CHAT_EXTRA:
        mid = e[0]
        assert mid in MEASURED_SERVED_CTX, mid
        assert mid in MEASURED_ARCH_CTX, mid
        assert mid in MODEL_DISPLAY, mid
        assert mid in _AVAILABLE_MODELS, mid
        assert _resolve_model(mid) == mid, mid


def test_direct_not_section_routed():
    assert not b.is_section_model("maternion/spark-x2.5:4b-q4_K_M")
    assert not b.is_section_model("alpha-wolf-qwen2.5-1.5b")
    assert b.is_section_model("esm2_t30_150M")
    assert b.is_section_model("qwen-image-2.1-turbo-int8")
    assert not b.is_section_model("no-such-model")


def test_skill_files_exist():
    import os
    for disp, fname in b.SKILL_FILES.items():
        assert os.path.isfile(str(PROJECT_ROOT / "backend" / "skills" / f"{fname}.py")), disp
    for e in b.CHAT_EXTRA:
        via = e[7]
        if via.startswith("skill:"):
            assert via.split(":", 1)[1] in b.SKILL_FILES, e[0]


def test_pending_and_unknown_paths_offline():
    r = b.run_section_turn("dinov2-small", [{"role": "user", "content": "hi"}])
    assert "moondream" in r["choices"][0]["message"]["content"]
    assert r.get("section_skill", {}).get("pending") is True
    r = b.run_section_turn("no-such-model", [{"role": "user", "content": "hi"}])
    assert r.get("status") == "section_error"


def test_adapter_paths_and_conventions():
    assert b._paths_from_text("see D:\\photo.png and file:///tmp/a.wav") == [
        "D:\\photo.png", "/tmp/a.wav"]
    assert b._convention("do it\nfields: name, age", "fields") == ["name", "age"]
    assert b._convention("rank\nvs: AAA | AA", "vs", "candidates") == ["AAA", "AA"]


def test_query_stripped_of_conventions():
    # Regression 2026-10-13: contaminated query inverted live ESM ranking.
    assert b._strip_conventions("MKTAYIAK vs: MKTAYIAK, GGG") == "MKTAYIAK"
    assert b._strip_conventions("plain problem") == "plain problem"


def test_thinking_recovery_detector():
    full = {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
    starved = {"choices": [{"message": {"role": "assistant", "content": "",
                                        "reasoning": "x" * 100}}]}
    assert b.needs_thinking_recovery(full) is False
    assert b.needs_thinking_recovery(starved) is True
    assert b.needs_thinking_recovery({"status": "backend_unavailable"}) is False
    assert b.needs_thinking_recovery({}) is False
