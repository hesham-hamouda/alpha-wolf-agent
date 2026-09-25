#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Agent Capabilities Package
=============================================
Provides real agent infrastructure for Alpha Wolf:

Sub-modules:
- tools          : Tool registry with 6 built-in tools (file ops, code exec, web search)
- tool_calling   : Parser for <tool_call>...</tool_call> blocks in model output
- streaming      : Server-Sent Events (SSE) helpers for streaming responses
- memory         : Conversation history persistence via SQLite (body sessions)
- mcp_server     : MCP server framework (stdio + HTTP variants)
- skills         : Runtime-installable skill loader

Iron Laws Applied:
- #15 (Verify)  : Each tool has built-in self-test
- #21 (NO Delete): Append-only memory storage
- #22 (Autonomous) : No user prompts for tool execution
- #33 (Lessons) : Each function has bilingual AR+EN docstring (Iron Law #47)
- #41 (Conflict) : Errors include context for diagnosis
- #42 (Storage) : All persistent data in workspace, never body
- #47 (Bilingual) : Every public API has Arabic translation in docstring
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "tools",
    "tool_calling",
    "streaming",
    "memory",
    "mcp_server",
    "skills",
]
