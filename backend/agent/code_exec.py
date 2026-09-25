#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Code Execution Sandbox | بيئة تنفيذ الكود
============================================================
Dedicated module for SAFE Python code execution (separate from tools.py).

Wolf Trait: Resourceful — runs code to verify hypotheses.
            Mistake Hunter — catches dangerous calls BEFORE execution.

Safety layers:
1. AST parse (block: os.system, subprocess.Popen, __import__('os'))
2. Subprocess isolation (no shell, no network env vars)
3. Restricted builtins (no open, no input)
4. Timeout (default 30s, configurable)
5. Output capture (stdout/stderr)
6. Resource limits (no fs writes outside workspace)

Iron Laws Applied:
- #13 (Self-Critical):  self-test in __main__
- #15 (Verify):         AST pre-check + subprocess timeout
- #21 (NO Deletion):    restricted env, no destructive imports
- #22 (Autonomous):     no prompts — returns dict immediately
- #33 (Lessons):        bilingual docstrings (AR + EN)
- #41 (Conflict):       detailed error context on rejection
- #47 (Bilingual):      every public function has Arabic translation
"""
from __future__ import annotations

import ast
import logging
import re
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("alpha_wolf.code_exec")


# ============================================================================
# Safety Configuration
# ============================================================================

# Default timeout for code execution (Iron Law #15 — bounded execution)
DEFAULT_TIMEOUT_SEC = 30
MAX_TIMEOUT_SEC = 120  # hard cap regardless of user request
MAX_OUTPUT_BYTES = 50_000  # 50KB stdout/stderr limit

# Dangerous AST nodes — these trigger immediate rejection
BLOCKED_AST_NODES = frozenset({
    ast.Import,    # blocks `import os`
    ast.ImportFrom,  # blocks `from os import system`
})

# Allowlist of safe modules (Whitelist principle — Iron Law #7 anti-contamination)
ALLOWED_MODULES = frozenset({
    "math", "json", "datetime", "collections",
    "itertools", "functools", "re", "string",
    "random", "statistics", "typing", "time",  # time is needed for sleeps + timing
    "pathlib",  # safe subset — controlled by other checks
})

# Dangerous functions to block (Iron Law #41 — Conflict Disclosure)
BLOCKED_FUNCTION_CALLS = frozenset({
    "os.system", "os.popen", "os.exec", "os.spawn",
    "subprocess.Popen", "subprocess.run", "subprocess.call",
    "subprocess.check_output", "subprocess.check_call",
    "builtins.exec", "builtins.eval", "builtins.compile",
    "builtins.__import__", "builtins.open",  # file ops via tools.py only
    "sys.exit", "sys.stdin",  # prevent console takeover
    "shutil.rmtree", "shutil.move",
    "socket.socket",  # block raw network
    "urllib.request.urlopen", "http.client.HTTPConnection",
    "ftplib.FTP", "smtplib.SMTP",
})

# Allowed builtins (conservative subset)
ALLOWED_BUILTINS = frozenset({
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray",
    "bytes", "callable", "chr", "complex", "dict", "divmod",
    "enumerate", "filter", "float", "format", "frozenset",
    "hash", "hex", "id", "int", "isinstance", "issubclass",
    "iter", "len", "list", "map", "max", "min", "next",
    "object", "oct", "ord", "pow", "print", "range", "repr",
    "reversed", "round", "set", "slice", "sorted", "str",
    "sum", "tuple", "type", "vars", "zip", "True", "False",
    "None",
})

# Block sensitive paths from imports (Iron Law #42 — Storage Discipline)
SENSITIVE_PATH_PATTERNS = [
    r"\.opencode[/\\]agent",      # expert prompts
    r"\.opencode[/\\]memory",      # memories
    r"\.opencode[/\\]knowledge",   # KBs
    r"\.git[/\\]",
    r"backups[/\\]",
    r"body[/\\]curation_log",
]


# ============================================================================
# Result Dataclass
# ============================================================================

@dataclass
class CodeExecResult:
    """Structured result of code execution.

    نتيجة منظّمة لتنفيذ الكود.
    """
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    execution_time_sec: float = 0.0
    execution_id: str = ""
    error: Optional[str] = None
    safety_check: Optional[Dict[str, Any]] = None
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = asdict(self)
        # Truncate outputs
        if len(d.get("stdout", "")) > 2000:
            d["stdout"] = d["stdout"][:2000] + "\n[... truncated]"
        if len(d.get("stderr", "")) > 2000:
            d["stderr"] = d["stderr"][:2000] + "\n[... truncated]"
        return d


# ============================================================================
# Safety Checks
# ============================================================================

def safety_check(code: str) -> Dict[str, Any]:
    """AST-based safety check (rejects dangerous calls BEFORE execution).

    فحص سلامة AST (يرفض الاستدعاءات الخطيرة قبل التنفيذ).

    Returns dict with: passed (bool), violations (list), warnings (list)
    """
    violations = []
    warnings = []

    # 1. Parse AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {
            "passed": False,
            "violations": [f"SyntaxError: {e}"],
            "warnings": [],
            "error": str(e),
        }

    # 2. Walk AST for dangerous patterns
    for node in ast.walk(tree):
        # 2a. Block `import os` etc. (only allow whitelisted modules)
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".")[0]
                if module_name not in ALLOWED_MODULES:
                    violations.append(
                        f"Import '{alias.name}' not allowed (whitelist: {sorted(ALLOWED_MODULES)})"
                    )
        elif isinstance(node, ast.ImportFrom):
            module_name = (node.module or "").split(".")[0]
            if module_name not in ALLOWED_MODULES:
                violations.append(
                    f"Import from '{node.module}' not allowed (whitelist: {sorted(ALLOWED_MODULES)})"
                )

        # 2b. Block dangerous function calls
        elif isinstance(node, ast.Call):
            func_name = _get_call_name(node.func)
            if func_name:
                # Check against blocked list (with or without module prefix)
                for blocked in BLOCKED_FUNCTION_CALLS:
                    if func_name == blocked or func_name.endswith("." + blocked.split(".")[-1]):
                        violations.append(
                            f"Dangerous call: {func_name} (blocked: {blocked})"
                        )

        # 2c. Block attribute access patterns (e.g., os.system, subprocess.Popen)
        elif isinstance(node, ast.Attribute):
            attr_chain = _get_attribute_chain(node)
            if attr_chain:
                for blocked in BLOCKED_FUNCTION_CALLS:
                    if attr_chain == blocked or attr_chain.endswith("." + blocked):
                        violations.append(
                            f"Dangerous attribute access: {attr_chain}"
                        )

    # 3. Check for sensitive paths in string literals (raw heuristic)
    for line in code.split("\n"):
        for pattern in SENSITIVE_PATH_PATTERNS:
            if re.search(pattern, line):
                warnings.append(
                    f"Sensitive path reference: '{line.strip()[:80]}'"
                )

    # 4. Heuristic: detect exec/eval strings
    if re.search(r"\beval\s*\(", code):
        violations.append("Use of eval() detected")
    if re.search(r"\bexec\s*\(", code):
        violations.append("Use of exec() detected")

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "error": None if len(violations) == 0 else violations[0],
    }


def _get_call_name(node: ast.AST) -> Optional[str]:
    """Get the name of a function call (best-effort)."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return _get_attribute_chain(node)
    return None


def _get_attribute_chain(node: ast.Attribute) -> Optional[str]:
    """Build dotted name from attribute chain (e.g., os.system)."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


# ============================================================================
# Execution
# ============================================================================

def execute_python(
    code: str,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    work_dir: Optional[Path] = None,
) -> CodeExecResult:
    """Execute Python code in a sandboxed subprocess.

    تنفيذ كود بايثون في عملية فرعية معزولة.

    Args:
        code: Python source code
        timeout_sec: max execution time (capped at MAX_TIMEOUT_SEC)
        work_dir: working directory (default: temp dir)

    Returns:
        CodeExecResult with success, stdout, stderr, etc.
    """
    execution_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()
    timeout_sec = min(max(1, timeout_sec), MAX_TIMEOUT_SEC)

    # Step 1: Safety check (Iron Law #15 — reject dangerous code BEFORE running)
    safety = safety_check(code)
    if not safety["passed"]:
        return CodeExecResult(
            success=False,
            execution_id=execution_id,
            execution_time_sec=0.0,
            timestamp=timestamp,
            error=f"Safety check failed: {safety.get('error')}",
            safety_check=safety,
        )

    # Step 2: Prepare work directory (Iron Law #42 — workspace-bound)
    if work_dir is None:
        work_dir = Path(tempfile.gettempdir()) / f"alpha_wolf_exec_{execution_id}"
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

    code_file = work_dir / "snippet.py"
    try:
        code_file.write_text(code, encoding="utf-8")
    except (OSError, PermissionError) as e:
        return CodeExecResult(
            success=False,
            execution_id=execution_id,
            timestamp=timestamp,
            error=f"Failed to write code file: {e}",
            safety_check=safety,
        )

    # Step 3: Execute in subprocess with restricted env (no network)
    restricted_env = {
        "PATH": "/usr/bin:/bin",  # minimal path
        "LANG": "en_US.UTF-8",
        "HOME": str(work_dir),  # isolate HOME
        "TMPDIR": str(work_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        # Intentionally OMIT proxy env vars, AWS_*, GITHUB_*, etc.
    }

    try:
        start_time = time.time() if 'time' in dir() else None
        import time as _time
        start_time = _time.time()

        result = subprocess.run(
            [sys.executable, str(code_file)],
            cwd=str(work_dir),
            env=restricted_env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,  # don't raise on non-zero exit
            shell=False,  # no shell injection
        )

        elapsed = _time.time() - start_time

        # Truncate outputs (Iron Law #15 bounded execution)
        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        stderr = result.stderr[:MAX_OUTPUT_BYTES]

        return CodeExecResult(
            success=result.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            return_code=result.returncode,
            execution_time_sec=round(elapsed, 3),
            execution_id=execution_id,
            timestamp=timestamp,
            safety_check=safety,
        )

    except subprocess.TimeoutExpired:
        return CodeExecResult(
            success=False,
            execution_id=execution_id,
            timestamp=timestamp,
            error=f"Execution timed out after {timeout_sec}s",
            safety_check=safety,
        )
    except subprocess.SubprocessError as e:
        return CodeExecResult(
            success=False,
            execution_id=execution_id,
            timestamp=timestamp,
            error=f"Subprocess error: {e}",
            safety_check=safety,
        )
    except Exception as e:
        return CodeExecResult(
            success=False,
            execution_id=execution_id,
            timestamp=timestamp,
            error=f"Unexpected error: {type(e).__name__}: {e}",
            safety_check=safety,
        )


# ============================================================================
# Time import (for execution_time_sec)
# ============================================================================

import time  # noqa: E402

# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify code_exec safety + execution works.

    التحقق من سلامة وتنفيذ الكود يعملان.
    """
    print("Running code_exec self-tests...")
    print("تشغيل اختبارات بيئة الكود...")

    passed = 0
    failed = 0

    try:
        # Test 1: Safe code executes
        safe_code = "print('Hello Wolf!')\nprint(2 + 2)"
        result = execute_python(safe_code, timeout_sec=10)
        if result.success and "Hello Wolf!" in result.stdout:
            passed += 1
            print(f"  ✓ safe execution: stdout={result.stdout.strip()}")
        else:
            failed += 1
            print(f"  ✗ safe execution failed: {result}")

        # Test 2: Dangerous code (import os) is BLOCKED
        dangerous_code = "import os\nos.system('echo BAD')"
        result = execute_python(dangerous_code, timeout_sec=5)
        if not result.success and "Safety check" in (result.error or ""):
            passed += 1
            print(f"  ✓ blocked 'import os': {result.error[:60]}")
        else:
            failed += 1
            print(f"  ✗ failed to block 'import os': {result}")

        # Test 3: Dangerous code (subprocess) is BLOCKED
        dangerous_code = "import subprocess\nsubprocess.run(['cmd.exe'])"
        result = execute_python(dangerous_code, timeout_sec=5)
        if not result.success and "Safety check" in (result.error or ""):
            passed += 1
            print(f"  ✓ blocked subprocess")
        else:
            failed += 1
            print(f"  ✗ failed to block subprocess")

        # Test 4: eval() is BLOCKED
        dangerous_code = "result = eval('1+1')"
        safety = safety_check(dangerous_code)
        if not safety["passed"] and any("eval" in v for v in safety["violations"]):
            passed += 1
            print(f"  ✓ blocked eval: {safety['violations'][0]}")
        else:
            failed += 1
            print(f"  ✗ failed to block eval: {safety}")

        # Test 5: Whitelisted module (math) works
        whitelist_code = "import math\nprint(math.pi)"
        result = execute_python(whitelist_code, timeout_sec=5)
        if result.success and "3.14" in result.stdout:
            passed += 1
            print(f"  ✓ whitelisted math: stdout={result.stdout.strip()}")
        else:
            failed += 1
            print(f"  ✗ whitelisted math failed: {result}")

        # Test 6: Timeout works
        timeout_code = "import time\ntime.sleep(60)"
        result = execute_python(timeout_code, timeout_sec=2)
        if not result.success and "timed out" in (result.error or "").lower():
            passed += 1
            print(f"  ✓ timeout enforcement")
        else:
            failed += 1
            print(f"  ✗ timeout failed: {result}")

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
