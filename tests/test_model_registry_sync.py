"""Registry sync test (POLICY 2026-10-12 — C3).

Fails when the backend model registry drifts from the frontend fallback
registry (D1): same ids, same measured served_ctx/arch_ctx, same default.

Run:
    cd "E:\\Projects and systems managed by the team of experts\\Alpha Wolf Agent"
    python -m pytest tests/test_model_registry_sync.py -q
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "frontend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "frontend"))

from backend.main import _AVAILABLE_MODELS, _resolve_model  # noqa: E402
from backend.agent.streaming import (  # noqa: E402
    MEASURED_SERVED_CTX,
    MEASURED_ARCH_CTX,
    registry_served_ctx,
)
from utils import MODEL_DISPLAY, PHASE_58_DEFAULT_MODEL  # noqa: E402

DEAD_IDS = {
    "alpha-wolf-agent",
    "alpha-wolf-agent:latest",
    "alpha-wolf-agent:default",
    "alpha-wolf-qwen3.5-v10",
    "alpha-wolf-agent-v8",
}


def test_same_ids():
    assert set(_AVAILABLE_MODELS) == set(MODEL_DISPLAY), (
        f"backend={sorted(_AVAILABLE_MODELS)} frontend={sorted(MODEL_DISPLAY)}"
    )


def test_no_dead_ids():
    for mid in list(_AVAILABLE_MODELS) + list(MODEL_DISPLAY):
        assert mid not in DEAD_IDS, f"dead model id leaked into registry: {mid}"
    assert PHASE_58_DEFAULT_MODEL not in DEAD_IDS


def test_ctx_matches_measured_table():
    for mid, info in _AVAILABLE_MODELS.items():
        assert info.served_ctx == MEASURED_SERVED_CTX[mid], mid
        assert info.arch_ctx == MEASURED_ARCH_CTX[mid], mid
    for mid, disp in MODEL_DISPLAY.items():
        assert disp["served_ctx"] == MEASURED_SERVED_CTX[mid], mid
        assert disp["arch_ctx"] == MEASURED_ARCH_CTX[mid], mid


def test_default_is_first_entry_everywhere():
    first = next(iter(_AVAILABLE_MODELS))
    assert PHASE_58_DEFAULT_MODEL == first
    assert _resolve_model("auto-select") == first
    for dead in ("alpha-wolf-qwen3.5-v10", "alpha-wolf-agent"):
        assert _resolve_model(dead) == first


def test_registry_served_ctx_helper():
    assert registry_served_ctx("maternion/spark-x2.5:4b-q4_K_M") == 262144
    assert registry_served_ctx("moondream:latest") == 2048
    # unknown id -> fail-safe fallback (never crash, never over-claim)
    assert registry_served_ctx("no-such-model") >= 0


def _env_model(path):
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("LLAMACPP_MODEL="):
            return s.split("=", 1)[1].split()[0]
    return ""


def test_live_env_matches_canonical_default():
    # Regression 2026-10-13: live .env said 0.5b while serving spark —
    # self-model lied about its own brain (served 0.5b-named brain).
    live = _env_model(PROJECT_ROOT / ".env")
    example = _env_model(PROJECT_ROOT / ".env.example")
    assert live == PHASE_58_DEFAULT_MODEL, f".env says {live}"
    assert example == PHASE_58_DEFAULT_MODEL, f".env.example says {example}"
