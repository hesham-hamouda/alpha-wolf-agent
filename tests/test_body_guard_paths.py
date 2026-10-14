"""Body-guard path normalization (FIX 2026-10-14): file:/// URLs with %20
must judge as their real TESTS path (allow), never as outside (deny)."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent import body_guard as g  # noqa: E402


def test_raw_tests_dir_allowed():
    ok, _ = g.check_write(r"D:\A\Applications under development\TESTS\صور")
    assert ok is True


def test_file_url_form_allowed():
    ok, _ = g.check_write(
        "file:///D:/A/Applications%20under%20development/TESTS/%D8%B5%D9%88%D8%B1")
    assert ok is True


def test_body_still_guarded():
    ok, _ = g.check_write("file:///E:/Projects%20and%20systems%20managed%20by%20the%20team%20of%20experts/Alpha%20Wolf%20Agent/body/memory/state.db")
    assert ok is False


def test_sensitive_still_denied():
    ok, _ = g.check_write(str(PROJECT_ROOT / ".env"))
    assert ok is False
    ok2, _ = g.check_write(str(PROJECT_ROOT / "body" / "memory" / "state.db"))
    assert ok2 is False
