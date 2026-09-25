#!/usr/bin/env python3
r"""Example Skill — Template for new skills.

This file demonstrates the skill structure. Copy this file, rename it,
and customize the run() function to create your own skill.

Skill Metadata (parsed from docstring):
  Name: example_skill
  Description: Example skill that demonstrates the skill system
  Description_AR: مهارة مثال توضح نظام المهارات
  Author: Alpha Wolf Team
  Version: 1.0.0
  Parameters: {"name": "string", "shout": "boolean"}

The `run(**kwargs)` function is the entry point. It can be:
- Sync: `def run(...)`
- Async: `async def run(...)`

Both are supported. Return value can be any JSON-serializable type.

Iron Laws Applied:
- #15 (Verify): The skill self-tests verify it loads + runs
- #22 (Autonomous): No prompts — execute immediately
- #33 (Lessons): Bilingual AR+EN docstrings
- #47 (Bilingual): Parameters documented in both languages
"""
from __future__ import annotations

from typing import Any, Dict


def run(name: str = "World", shout: bool = False, **kwargs: Any) -> Dict[str, Any]:
    """Example run function — greet the user.

    دالة تشغيل المثال — تحية المستخدم.

    Args:
        name: Name to greet | اسم المُرحَّب به
        shout: If True, use uppercase | إذا كان True، استخدم الأحرف الكبيرة

    Returns:
        Dict with greeting message, timestamp, and metadata.
        قاموس يحتوي على رسالة الترحيب والوقت والبيانات الوصفية.
    """
    greeting = f"Hello, {name}!"
    if shout:
        greeting = greeting.upper()

    return {
        "greeting": greeting,
        "shout": shout,
        "language_pair": "EN+AR",
        "wolf_signature": "🐺 Alpha Wolf Agent says hi!",
    }
