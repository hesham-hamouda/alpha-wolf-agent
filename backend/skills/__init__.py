#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Skills Package | حزمة المهارات
==================================================
Runtime-installable skills for Alpha Wolf Agent.

Each skill is a Python file in this directory with:
- A docstring containing metadata (Name, Description, Description_AR)
- A `run(**kwargs)` function (sync or async)

Skills are auto-discovered by backend.agent.skills.list_skills()
and can be installed at runtime via /v1/install_skill.
"""
from __future__ import annotations

# This package contains skill modules.
# Each .py file (except __init__.py and _*) is a skill.
# Skills are loaded dynamically by backend/agent/skills.py
