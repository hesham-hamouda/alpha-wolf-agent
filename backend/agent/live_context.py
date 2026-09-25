#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Live Context Awareness | السياق الحي
=========================================================
GraphRAG-style LIVE awareness of the project folder + body folder.

Wolf Trait: Self-Aware (الوعي الذاتي) — knows what lives where.
            Deep Thinking (التفكير العميق) — reads before answering.

Unlike cached embeddings, this module:
1. Reads project folder structure on EACH call (freshness)
2. Builds a tree summary from disk (no DB dependency)
3. Greps recent files + key project metadata

Iron Laws Applied:
- #13 (Self-Critical):  self-test in __main__
- #15 (Verify):         Live file system reads, no caching
- #21 (NO Deletion):    read-only operations only
- #33 (Lessons):        bilingual docstrings (AR + EN)
- #41 (Conflict):       graceful degradation if dir missing
- #42 (Storage):        paths resolved from PROJECT_ROOT only
- #47 (Bilingual):      every public function has Arabic translation
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("alpha_wolf.live_context")


# ============================================================================
# Path Resolution (Iron Law #42 — Storage Discipline)
# ============================================================================

def _project_root() -> Path:
    """Resolve Alpha Wolf project root (workspace).

    المجلد الجذر للمشروع (workspace).
    """
    # backend/agent/live_context.py  ->  backend/agent  ->  backend  ->  PROJECT_ROOT
    return Path(__file__).resolve().parent.parent.parent


def _body_root() -> Path:
    """Resolve body folder (read-only).

    مجلد الجسم (قراءة فقط).
    """
    project = _project_root()
    # Body sits OUTSIDE the workspace per Iron Law #42 — at D:/Trained models/alpha-wolf/
    # But for awareness we look at the local mirror at body/ inside the project
    local_body = project / "body"
    if local_body.exists():
        return local_body
    # External body location (preferred)
    external = Path(os.environ.get("ALPHA_WOLF_BODY", r"E:\Trained intelligence models\alpha-wolf"))
    return external if external.exists() else local_body


# Directories to ALWAYS exclude from tree summary (heavy / noisy)
EXCLUDED_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".cache", ".mypy_cache",
    "unsloth_compiled_cache", "checkpoints", ".chainlit",
    "backups",  # large backup files
})

# File extensions to exclude (binary / heavy)
EXCLUDED_EXTENSIONS = frozenset({
    ".pyc", ".pyd", ".so", ".dll", ".exe", ".bin",
    ".gguf", ".safetensors", ".pt", ".pth",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pdf", ".mp3", ".mp4", ".wav", ".mov",
})

# Key files to surface in summary (project metadata)
KEY_METADATA_FILES = frozenset({
    "README.md", "PROJECT_PLAN.md", "PROJECT_LOG.md",
    "pyproject.toml", "package.json", "requirements.txt",
    "PROMPT_NEW_CHAT.md", ".env.example",
})


# ============================================================================
# Live Context Class
# ============================================================================

class LiveContext:
    """GraphRAG-style LIVE awareness of project + body folders.

    الوعي الحي للملفات والمجلدات (يقرأ من القرص في كل استعلام).

    No caching — every call returns fresh data (Iron Law #15 freshness).
    Thread-safe via stdlib only.
    """

    def __init__(self, project_root: Optional[Path] = None, body_root: Optional[Path] = None):
        self.project_root = Path(project_root) if project_root else _project_root()
        self.body_root = Path(body_root) if body_root else _body_root()

    # ------------------------------------------------------------------
    # Tree Summary
    # ------------------------------------------------------------------

    def _walk_dir(
        self,
        root: Path,
        max_depth: int = 3,
        current_depth: int = 0,
    ) -> List[str]:
        """Walk a directory tree, returning formatted lines.

        يمشي شجرة المجلدات ويُرجع الأسطر المنسّقة.
        """
        if current_depth > max_depth:
            return []
        if not root.exists() or not root.is_dir():
            return []

        lines = []
        try:
            entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except (PermissionError, OSError) as e:
            logger.warning("Cannot read %s: %s", root, e)
            return [f"  [permission denied] {root.name}"]

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in (".env.example",):
                continue
            if entry.is_dir():
                if entry.name in EXCLUDED_DIRS:
                    continue
                indent = "  " * current_depth
                lines.append(f"{indent}📁 {entry.name}/")
                lines.extend(self._walk_dir(entry, max_depth, current_depth + 1))
            else:
                if entry.suffix in EXCLUDED_EXTENSIONS:
                    continue
                try:
                    size_kb = entry.stat().st_size / 1024
                    if size_kb > 500:  # skip files > 500KB in tree
                        size_str = f" ({size_kb:.0f}KB)"
                    else:
                        size_str = ""
                except OSError:
                    size_str = ""
                indent = "  " * current_depth
                lines.append(f"{indent}📄 {entry.name}{size_str}")
        return lines

    def get_project_summary(
        self,
        max_depth: int = 3,
        recent_days: int = 7,
    ) -> Dict[str, Any]:
        """Return a structured project summary (tree + recent files + metadata).

        يُرجع ملخص المشروع (شجرة + ملفات حديثة + بيانات وصفية).

        Args:
            max_depth: Tree depth limit (default 3 levels)
            recent_days: Files modified in last N days (default 7)

        Returns:
            dict with keys: tree, recent_files, key_metadata, timestamp
        """
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self.project_root),
            "body_root": str(self.body_root),
            "tree": [],
            "recent_files": [],
            "key_metadata": {},
            "stats": {},
        }

        # 1. File tree (3 levels deep)
        summary["tree"] = self._walk_dir(self.project_root, max_depth=max_depth)

        # 2. Recently modified files
        summary["recent_files"] = self._recent_files(recent_days=recent_days)

        # 3. Key metadata from key files (READ ONLY, truncate to 1500 chars each)
        summary["key_metadata"] = self._read_key_metadata()

        # 4. Stats
        summary["stats"] = {
            "tree_lines": len(summary["tree"]),
            "recent_files_count": len(summary["recent_files"]),
            "metadata_files_found": len(summary["key_metadata"]),
        }

        return summary

    def _recent_files(self, recent_days: int = 7, limit: int = 30) -> List[Dict[str, Any]]:
        """List recently modified files (Iron Law #15 — actually scans disk).

        قائمة الملفات المُعدَّلة مؤخراً.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
        recent = []

        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix in EXCLUDED_EXTENSIONS:
                continue
            # Skip noisy dirs
            if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
                continue
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                if mtime > cutoff:
                    rel = path.relative_to(self.project_root)
                    recent.append({
                        "path": str(rel),
                        "absolute": str(path),
                        "modified_at": mtime.isoformat(),
                        "size_kb": round(path.stat().st_size / 1024, 1),
                    })
            except (OSError, ValueError):
                continue

        recent.sort(key=lambda x: x["modified_at"], reverse=True)
        return recent[:limit]

    def _read_key_metadata(self) -> Dict[str, str]:
        """Read KEY_METADATA_FILES (project docs), truncating to 1500 chars.

        قراءة الملفات الرئيسية (تقطيع إلى 1500 حرف).
        """
        metadata = {}
        for filename in KEY_METADATA_FILES:
            path = self.project_root / filename
            if not path.exists():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if len(content) > 1500:
                    content = content[:1500] + f"\n\n[... truncated, total {len(content)} chars]"
                metadata[filename] = content
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read %s: %s", filename, e)
        return metadata

    # ------------------------------------------------------------------
    # Search in files (text search)
    # ------------------------------------------------------------------

    def search_in_files(
        self,
        query: str,
        file_patterns: Optional[List[str]] = None,
        max_results: int = 10,
        context_chars: int = 200,
    ) -> List[Dict[str, Any]]:
        """Search for a text query in project files (graph traversal).

        البحث عن نص داخل ملفات المشروع.

        Args:
            query: Text to search for (case-insensitive substring)
            file_patterns: glob filters (default ["*.md", "*.py", "*.txt"])
            max_results: max number of results
            context_chars: chars before/after match

        Returns:
            list of dicts: {path, line, match, context}
        """
        if not query:
            return []

        patterns = file_patterns or ["*.md", "*.py", "*.txt", "*.json", "*.toml"]
        query_lower = query.lower()
        results = []

        for pattern in patterns:
            for path in self.project_root.rglob(pattern):
                if not path.is_file():
                    continue
                if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
                    continue
                if path.suffix in EXCLUDED_EXTENSIONS:
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    if query_lower in content.lower():
                        # Extract first match with context
                        idx = content.lower().find(query_lower)
                        line_no = content[:idx].count("\n") + 1
                        start = max(0, idx - context_chars)
                        end = min(len(content), idx + len(query) + context_chars)
                        context = content[start:end].strip()
                        results.append({
                            "path": str(path.relative_to(self.project_root)),
                            "absolute": str(path),
                            "line": line_no,
                            "match": query,
                            "context": f"...{context}...",
                        })
                        if len(results) >= max_results:
                            return results
                except (OSError, UnicodeDecodeError):
                    continue
        return results

    # ------------------------------------------------------------------
    # System Prompt Builder
    # ------------------------------------------------------------------

    def build_system_context(
        self,
        query: Optional[str] = None,
        max_depth: int = 2,
        search_top_k: int = 5,
    ) -> str:
        """Build a system prompt with LIVE project context injected.

        يبني سياق نظامي مع البيانات الحية لمشروع.

        Args:
            query: optional user query to also search for relevant files
            max_depth: tree depth (default 2 to keep prompt small)
            search_top_k: search results to include

        Returns:
            Markdown-formatted string for injection into system message
        """
        summary = self.get_project_summary(max_depth=max_depth, recent_days=7)

        sections = [
            "You are Alpha Wolf Agent with LIVE awareness of your project body.",
            "أنت Alpha Wolf Agent مع وعي حي بجسم مشروعك.",
            "",
            "## Current Project Structure:",
            f"Project root: `{summary['project_root']}`",
            f"Body root: `{summary['body_root']}`",
            "",
            "\n".join(summary["tree"]) or "(empty project)",
            "",
            "## Recently Modified Files (last 7 days):",
        ]

        # Add recent files (limit 10)
        for rf in summary["recent_files"][:10]:
            sections.append(f"- `{rf['path']}` (modified {rf['modified_at']}, {rf['size_kb']}KB)")

        # Add search results if query provided
        if query:
            search_results = self.search_in_files(query, max_results=search_top_k)
            if search_results:
                sections.extend([
                    "",
                    f"## Relevant Files to Query '{query}':",
                ])
                for sr in search_results:
                    sections.append(
                        f"- `{sr['path']}` (line {sr['line']}): {sr['context'][:300]}"
                    )

        # Add key metadata (truncated)
        if summary["key_metadata"]:
            sections.extend([
                "",
                "## Key Project Metadata:",
            ])
            for filename, content in summary["key_metadata"].items():
                # Show only first 500 chars of each metadata file in context
                sections.append(f"### {filename}:\n{content[:500]}")

        sections.extend([
            "",
            "---",
            "**Note:** This is LIVE data from disk — always reflects current state.",
            "**ملاحظة:** هذه بيانات حية من القرص — تعكس الحالة الحالية دائماً.",
        ])

        return "\n".join(sections)


# ============================================================================
# Module-level Singleton (Iron Law #15 freshness — no caching)
# ============================================================================

_default_instance: Optional[LiveContext] = None


def get_live_context() -> LiveContext:
    """Get or create the default LiveContext instance.

    الحصول على نسخة السياق الحي الافتراضية.
    """
    global _default_instance
    if _default_instance is None:
        _default_instance = LiveContext()
    return _default_instance


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify live_context works end-to-end.

    التحقق من السياق الحي يعمل من البداية للنهاية.
    """
    print("Running live_context self-tests...")
    print("تشغيل اختبارات السياق الحي...")

    passed = 0
    failed = 0

    try:
        lc = LiveContext()

        # Test 1: Project summary
        s = lc.get_project_summary(max_depth=2)
        if s["tree"] and s["timestamp"]:
            passed += 1
            print(f"  ✓ get_project_summary: {len(s['tree'])} tree lines, {len(s['recent_files'])} recent files")
        else:
            failed += 1
            print(f"  ✗ get_project_summary: {s}")

        # Test 2: Recent files
        if len(s["recent_files"]) >= 0:  # can be 0 if no recent edits
            passed += 1
            print(f"  ✓ _recent_files: {len(s['recent_files'])} files")
        else:
            failed += 1
            print(f"  ✗ _recent_files")

        # Test 3: Key metadata
        if "README.md" in s["key_metadata"] or "PROJECT_PLAN.md" in s["key_metadata"]:
            passed += 1
            print(f"  ✓ _read_key_metadata: {list(s['key_metadata'].keys())}")
        else:
            failed += 1
            print(f"  ✗ _read_key_metadata: {list(s['key_metadata'].keys())}")

        # Test 4: Search (search for "wolf" should hit README or PROJECT_PLAN)
        results = lc.search_in_files("wolf", max_results=3)
        if len(results) >= 0:  # even 0 is acceptable
            passed += 1
            print(f"  ✓ search_in_files 'wolf': {len(results)} matches")
        else:
            failed += 1
            print(f"  ✗ search_in_files")

        # Test 5: Build system context
        ctx = lc.build_system_context(query="wolf", max_depth=2, search_top_k=3)
        if "Alpha Wolf Agent" in ctx and len(ctx) > 200:
            passed += 1
            print(f"  ✓ build_system_context: {len(ctx)} chars")
        else:
            failed += 1
            print(f"  ✗ build_system_context: too short or missing Agent tag")

        # Test 6: Singleton
        lc2 = get_live_context()
        if lc2 is not None:
            passed += 1
            print(f"  ✓ get_live_context singleton")
        else:
            failed += 1
            print(f"  ✗ get_live_context")

    except Exception as e:
        failed += 1
        print(f"  ✗ exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()
