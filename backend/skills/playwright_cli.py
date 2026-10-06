"""
Name: playwright_cli
Description: Browser Automation with playwright-cli
Description_AR: مهارة مكيفة من مصدر خارجي للذئب ألفا
Author: Alpha Wolf skill-forge
Version: 1.0.0
Parameters: {"task": "string"}
"""
from pathlib import Path as _Path

WOLF_PACK_DIR = str(_Path(__file__).resolve().parent / "playwright_cli_pack")
WOLF_SOURCE_URL = 'https://www.skills.sh/microsoft/playwright/playwright-cli'


def _playbook():
    """Read the adapted playbook (quarantined pack data, never executed)."""
    try:
        return (_Path(WOLF_PACK_DIR) / "PLAYBOOK.md").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "(playbook missing)"


def run(task="", **kwargs):
    """Return the adapted playbook for the model to execute with its tools.

    يرجع دليل التشغيل المكيف لينفذه النموذج بأدواته.
    The Wolf READS this and performs the steps via write_file/run_shell/etc.
    """
    extra = ""
    if kwargs:
        extra = "\nTask arguments: " + str(kwargs)[:500]
    user_task = task or str(kwargs.get("goal", "")) or "(no task given)"
    return (
        "ADAPTED SKILL PLAYBOOK — follow these steps using your tools "
        "(write_file/run_shell/execute_python), verifying each by RUNNING:\n\n"
        "USER TASK: " + user_task[:1000] + extra + "\n\n" + _playbook()
    )
