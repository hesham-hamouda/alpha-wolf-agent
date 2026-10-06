#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Tool Calling Parser | محلل استدعاء الأدوات
=============================================================
Parses tool calls from model output and executes them.

Format (XML-style, model-friendly):
<tool_call name="tool_name">
<arg_name>arg_value</arg_name>
</tool_call>

The parser is:
- Lenient: handles whitespace, multiple blocks, partial closing tags
- Self-validating: checks against tool registry for required params
- Recursive: supports tool calls inside reasoning (max 5 iterations to prevent loops)

Iron Laws Applied:
- #15 (Verify)        : Self-test included
- #22 (Autonomous)    : Execute immediately, no prompts
- #33 (Lessons)       : Bilingual AR+EN docstrings (Iron Law #47)
- #41 (Conflict)      : Errors include diagnostic context
"""
from __future__ import annotations

import functools
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from .tools import ToolResult, execute_tool, get_tool_spec, TOOL_SPECS

logger = logging.getLogger("alpha_wolf.tool_calling")


# ============================================================================
# Retry Decorator — P1-3 (Round 25, 2026-09-29)
# ============================================================================
# Exponential backoff for transient errors (network, timeout, 5xx).
# Permanent errors (FileNotFound, PermissionError, ValueError, SyntaxError)
# are NOT retried — retrying them is just noise.

def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
):
    """Decorator: exponential backoff retry for transient errors.

    مُزخرف: إعادة المحاولة مع تأخير أُسّي للأخطاء العابرة.

    Transient errors (retry): requests.RequestException, ConnectionError,
                              TimeoutError, OSError, IOError.
    Permanent errors (no retry): FileNotFoundError, PermissionError,
                                 ValueError, SyntaxError, TypeError.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            last_error = None
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, ConnectionError, TimeoutError,
                        OSError, IOError) as e:
                    # Transient — retry with backoff
                    last_error = e
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        f"  [Retry] {func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                except (FileNotFoundError, PermissionError, ValueError,
                        SyntaxError, TypeError) as e:
                    # Permanent — no retry
                    logger.error(f"  [Retry] {func.__name__} permanent error: "
                                 f"{type(e).__name__}: {e}")
                    raise
            logger.error(
                f"  [Retry] {func.__name__} exhausted {max_attempts} attempts: "
                f"{type(last_error).__name__}: {last_error}"
            )
            raise last_error
        return wrapper
    return decorator


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ParsedToolCall:
    """A single tool call parsed from model output.

    استدعاء أداة واحد تم تحليله من مخرجات النموذج.
    """
    name: str                                          # اسم الأداة
    arguments: Dict[str, Any] = field(default_factory=dict)  # الوسائط
    raw: str = ""                                      # النص الأصلي
    line_number: int = 0                               # رقم السطر


@dataclass
class ParsedResponse:
    """Result of parsing a model response.

    نتيجة تحليل رد النموذج.
    """
    text: str                                          # النص (بدون tool calls)
    tool_calls: List[ParsedToolCall] = field(default_factory=list)
    has_tool_calls: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "tool_calls": [
                {"name": tc.name, "arguments": tc.arguments, "raw": tc.raw}
                for tc in self.tool_calls
            ],
            "has_tool_calls": self.has_tool_calls,
        }


# ============================================================================
# Parser
# ============================================================================

# Regex: <tool_call name="X">...</tool_call>
# Allows: name="x", name='x', name=x, whitespace
TOOL_CALL_PATTERN = re.compile(
    r'<tool_call\s+name\s*=\s*["\']?([a-zA-Z_][a-zA-Z0-9_]*)["\']?\s*>(.*?)</?\s*tool_call\s*>',
    re.DOTALL | re.IGNORECASE,
)

# Inside <tool_call>, parse <arg_name>value</arg_name>
ARG_PATTERN = re.compile(
    r'<([a-zA-Z_][a-zA-Z0-9_]*)\s*>(.*?)</?\s*\1\s*>',
    re.DOTALL,
)

# Unclosed form (FIX 2026-09-26, Round 13 — observed live): the model emits
#   <tool_call name="system_status">
#   <system_status></system_status>
# and simply never writes the closing tag, so the closed-form regex missed it
# and the raw protocol text leaked into the user's answer. The body runs to
# the next <tool_call or the end of the message.
OPEN_TOOL_CALL_PATTERN = re.compile(
    r'<tool_call\s+name\s*=\s*["\']?([a-zA-Z_][a-zA-Z0-9_]*)["\']?\s*>(.*)',
    re.DOTALL | re.IGNORECASE,
)

# Narrated calls: **Tool Call:** NAME + **Arguments:** + ```json {...} ```
_NARRATED_CALL_PATTERN = re.compile(
    r"\*\*Tool Call:\*\*\s*([a-zA-Z_][a-zA-Z0-9_]*)"
    r"\s*\*\*Arguments:\*\*\s*```(?:json)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

# Narrated envelope: ```json {"tool_name"|"function": "X", ...} ```
# Matched with a brace-balancing scanner (envelopes contain NESTED
# objects/arrays, which regex [^{}]* cannot span — FIX 2026-09-26).
_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def _balanced_json_objects(block: str) -> List[str]:
    """Extract top-level {...} spans with balanced braces (strings respected)."""
    spans: List[str] = []
    i, n = 0, len(block)
    while i < n:
        if block[i] != "{":
            i += 1
            continue
        depth, instr, esc = 0, False, False
        start = i
        closed = False
        while i < n:
            ch = block[i]
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    instr = False
            elif ch == '"':
                instr = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    spans.append(block[start:i + 1])
                    closed = True
                    i += 1
                    break
            i += 1
        if not closed:
            break
    return spans


def parse_tool_calls(text: str) -> ParsedResponse:
    """Parse tool calls from model output.

    تحليل استدعاءات الأدوات من مخرجات النموذج.

    Returns a ParsedResponse with the text (stripped of tool calls) and the parsed calls.
    """
    tool_calls: List[ParsedToolCall] = []

    for match in TOOL_CALL_PATTERN.finditer(text):
        tool_name = match.group(1)
        inner = match.group(2)
        raw = match.group(0)

        # Parse arguments as XML-style tags
        arguments: Dict[str, Any] = {}
        for arg_match in ARG_PATTERN.finditer(inner):
            arg_name = arg_match.group(1)
            arg_value = arg_match.group(2).strip()
            # Try to coerce to JSON if it looks like a number/bool/null
            arguments[arg_name] = _coerce_value(arg_value)

        # FIX 2026-09-25: tolerate model variants like
        # <code_name>code</code_name><code_value>print(1)</code_value>
        # or <name>code</name><value>print(1)</value>.
        # Normalize to the real parameter name so execute_tool() finds it.
        arguments = _normalize_xml_arguments(tool_name, arguments)

        tool_calls.append(ParsedToolCall(
            name=tool_name,
            arguments=arguments,
            raw=raw,
            line_number=text[:match.start()].count('\n') + 1,
        ))

    # Strip tool_call blocks from text
    cleaned_text = TOOL_CALL_PATTERN.sub('', text).strip()

    # FIX 2026-09-26 (user-observed): the model sometimes NARRATES calls as
    # markdown instead of emitting machine-readable blocks:
    #   **Tool Call:** write_file
    #   **Arguments:**
    #   ```json
    #   {"path": "...", "content": "..."}
    #   ```
    # Parse and execute those too — intent is unambiguous.
    for match in _NARRATED_CALL_PATTERN.finditer(cleaned_text):
        tool_name = match.group(1)
        raw = match.group(0)
        arguments = parse_tool_arguments(match.group(2), tool_name)
        if not arguments:
            continue
        arguments = _normalize_xml_arguments(tool_name, arguments)
        tool_calls.append(ParsedToolCall(
            name=tool_name,
            arguments=arguments,
            raw=raw,
            line_number=text[:match.start()].count('\n') + 1,
        ))
    if len(tool_calls) > sum(1 for _ in TOOL_CALL_PATTERN.finditer(text)):
        cleaned_text = _NARRATED_CALL_PATTERN.sub('', cleaned_text).strip()

    # FIX 2026-09-26: narrated envelope form — ```json {"tool_name"|"function"|"action":
    # "X", ...} ``` (flat, "params"-wrapped, or NESTED). Brace-balanced scan
    # (regex cannot span nesting). Unwrap and execute; validation errors feed
    # back so the model corrects its schema on follow-up.
    for fence_m in _FENCE_PATTERN.finditer(cleaned_text):
        for span in _balanced_json_objects(fence_m.group(1)):
            try:
                envelope = parse_tool_arguments(span, "")
            except Exception:
                continue
            if not isinstance(envelope, dict):
                continue
            tool_name = (envelope.get("tool_name", "") or envelope.get("function", "")
                         or envelope.get("action", ""))
            if not isinstance(tool_name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tool_name):
                continue
            params = envelope.get("params", envelope.get("arguments"))
            if isinstance(params, dict):
                arguments = params
            else:
                arguments = {k: v for k, v in envelope.items()
                             if k not in ("tool_name", "function", "action")}
            if not arguments:
                continue
            arguments = _normalize_xml_arguments(tool_name, arguments)
            tool_calls.append(ParsedToolCall(
                name=tool_name,
                arguments=arguments,
                raw=fence_m.group(0),
                line_number=text[:fence_m.start()].count('\n') + 1,
            ))
    if any(tc.raw.startswith("```") for tc in tool_calls):
        cleaned_text = _FENCE_PATTERN.sub(
            lambda m: "" if any(tc.raw == m.group(0) for tc in tool_calls) else m.group(0),
            cleaned_text,
        ).strip()

    # FIX 2026-09-26 (user-observed): inline pseudo-code narration —
    # `track_goal("Name", [...])` / `list_goals("X")` — valid call SYNTAX in
    # backticks but never executed. Parse with AST (balanced parens), map
    # positionals to the spec's parameter order. Only KNOWN tools (never
    # random `foo()` mentions).
    for span in _backtick_call_spans(cleaned_text):
        found = _parse_backtick_call(span)
        if not found:
            continue
        tool_name, arguments = found
        arguments = _normalize_xml_arguments(tool_name, arguments)
        tool_calls.append(ParsedToolCall(
            name=tool_name,
            arguments=arguments,
            raw=span,
            line_number=text[:max(text.find(span), 0)].count('\n') + 1,
        ))
    if any(tc.raw.startswith("`") and not tc.raw.startswith("```") for tc in tool_calls):
        for tc in [t for t in tool_calls if t.raw.startswith("`") and not t.raw.startswith("```")]:
            cleaned_text = cleaned_text.replace(tc.raw, "", 1)
        cleaned_text = cleaned_text.strip()

    # FIX 2026-09-26 (Round 13): UNCLOSED <tool_call> blocks. Thinking models
    # frequently stop mid-format and never write the closing tag, so the
    # closed-form regex above matched nothing and the raw protocol text was
    # shown to the user instead of a tool result. Body runs to the next
    # <tool_call or the end of the message.
    for match in OPEN_TOOL_CALL_PATTERN.finditer(cleaned_text):
        tool_name = match.group(1)
        body = match.group(2)
        nxt = body.lower().find("<tool_call")
        if nxt != -1:
            body = body[:nxt]
        arguments: Dict[str, Any] = {}
        for arg_match in ARG_PATTERN.finditer(body):
            arguments[arg_match.group(1)] = _coerce_value(arg_match.group(2).strip())
        arguments = _normalize_xml_arguments(tool_name, arguments)
        tool_calls.append(ParsedToolCall(
            name=tool_name,
            arguments=arguments,
            raw=match.group(0)[:400],
            line_number=cleaned_text[:match.start()].count('\n') + 1,
        ))
        cleaned_text = (cleaned_text[:match.start()]
                        + cleaned_text[match.start() + len(match.group(0)):]).strip()

    return ParsedResponse(
        text=cleaned_text,
        tool_calls=tool_calls,
        has_tool_calls=len(tool_calls) > 0,
    )


def _backtick_call_spans(text: str) -> List[str]:
    """Find `name(...)` spans with balanced parens (backtick-delimited)."""
    spans: List[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "`":
            i += 1
            continue
        m = re.match(r"`([A-Za-z_][A-Za-z0-9_]*)\(", text[i:])
        if not m:
            i += 1
            continue
        j = i + m.end()  # just after '('
        depth, instr, esc = 1, False, False
        quote = ""
        while j < n:
            ch = text[j]
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    instr = False
            elif ch in ("'", '"'):
                instr, quote = True, ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    if j + 1 < n and text[j + 1] == "`":
                        spans.append(text[i:j + 2])
                        i = j + 2
                    break
            j += 1
        else:
            i += 1
            continue
        if j >= n:
            i += 1
    return spans


def _parse_backtick_call(span: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Parse one `name(args)` span into (tool, arguments) if tool is known."""
    import ast as _ast

    m = re.match(r"`([A-Za-z_][A-Za-z0-9_]*)\(", span)
    if not m:
        return None
    tool_name = m.group(1)
    try:
        from .tools import get_tool_spec
        spec = get_tool_spec(tool_name)
    except Exception:
        return None
    if spec is None:
        return None  # unknown tool — never execute prose mentions
    try:
        node = _ast.parse(span.strip("`").strip(), mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(node, _ast.Call):
        return None
    prop_order = list((spec.parameters.get("properties", {}) or {}).keys())
    arguments: Dict[str, Any] = {}
    try:
        for value_node, pname in zip(node.args, prop_order):
            arguments[pname] = _ast.literal_eval(value_node)
        for kw in node.keywords:
            if kw.arg:
                arguments[kw.arg] = _ast.literal_eval(kw.value)
    except (ValueError, SyntaxError):
        return None
    return tool_name, arguments


def _normalize_xml_arguments(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize model-invented XML arg variants to real parameter names.

    توحيد وسائط XML المخترعة من النموذج إلى أسماء الوسائط الحقيقية.

    Observed model drift (E2E 2026-09-25):
        <code_name>code</code_name><code_value>print(40+2)</code_value>
    instead of:
        <code>print(40+2)</code>

    Rules (generic, no hard-coded tool list):
    1. <X_name>N</X_name> + <X_value>V</X_value> (or <name>N</name> +
       <value>V</value>) -> {N: V} when N looks like a parameter name.
    2. <X_value>V</X_value> alone where X matches a known param prefix
       (code/path/query/pattern/content/text/question/query) -> {X: V}.
    3. <value>V</value> alone with a single <name>N</name> -> {N: V}.
    """
    if not arguments:
        return arguments

    try:
        from .tools import get_tool_spec
    except Exception:
        get_tool_spec = None  # type: ignore

    known_params: set[str] = set()
    if get_tool_spec is not None:
        try:
            spec = get_tool_spec(tool_name)
            if spec is not None:
                known_params = set((spec.parameters.get("properties", {}) or {}).keys())
        except Exception:
            pass

    normalized: Dict[str, Any] = dict(arguments)

    # Rule 0 (FIX 2026-09-26, user-observed): model invents near-synonym keys
    # (goal_name instead of title). Map to the real required name when the
    # spec knows it and the real one is absent.
    if "title" in known_params and "title" not in normalized:
        for alias in ("goal_name", "name", "task_title"):
            if alias in normalized and isinstance(normalized[alias], str):
                normalized["title"] = normalized.pop(alias)
                break

    # Rule 1: name/value pairs
    pair_keys = [k for k in list(normalized.keys()) if k.endswith("_name") or k == "name"]
    for name_key in pair_keys:
        base = name_key[:-5] if name_key.endswith("_name") else ""
        value_key = f"{base}_value" if base else "value"
        if value_key in normalized:
            declared = str(normalized[name_key]).strip().strip("\"'")
            if declared and declared in known_params:
                normalized[declared] = normalized[value_key]
            elif declared and not base:
                # <name>code</name><value>...</value> generic form
                normalized[declared] = normalized[value_key]
            # Drop the helper keys to avoid confusing execute_tool()
            normalized.pop(name_key, None)
            if value_key in normalized and value_key not in known_params:
                normalized.pop(value_key, None)

    # Rule 2: <X_value>V</X_value> alone (e.g. code_value without code_name)
    for key in list(normalized.keys()):
        if key.endswith("_value"):
            real = key[:-6]
            if real and real not in normalized and (not known_params or real in known_params):
                normalized[real] = normalized.pop(key)
            elif real and real in known_params and real not in normalized:
                normalized[real] = normalized.pop(key)

    return normalized


def parse_tool_arguments(raw: Any, tool_name: str = "") -> Dict[str, Any]:
    r"""Parse tool arguments tolerantly (model JSON is often sloppy).

    تحليل وسائط الأدوات بتسامح (JSON النموذج غالباً غير دقيق).

    Handles: valid JSON; single-backslash Windows paths; truncated
    fragments via per-parameter regex fallback. Never raises.

    Windows-path subtlety (FIX 2026-09-26, user-observed): in
    `"path": "D:\A\new\f.txt"` the `\f` is a VALID JSON escape
    (formfeed), so strict parsing "succeeds" with a corrupted path.
    Path-like params are therefore extracted first and unescaped
    path-aware (`\X` stays literal inside drive paths).
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    s = raw.strip()
    if not s:
        return {}
    # 1. Path-aware pass: pull out drive-path params before JSON parsing.
    s, _holders = _extract_path_params(s, tool_name)
    # 2. Strict, then lone-backslash-fixed parse.
    v: Any = None
    try:
        v = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        v = None
    if not isinstance(v, dict):
        try:
            v = json.loads(re.sub(r"\\(?![\\/bfnrtu\"])", r"\\\\", s))
        except (json.JSONDecodeError, ValueError):
            v = None
    if isinstance(v, dict):
        if _holders:
            for k, val in v.items():
                if isinstance(val, str) and val in _holders:
                    v[k] = _holders[val]
        return v
    # 3. Last resort: per-parameter regex extraction.
    out = _regex_extract_params(raw if isinstance(raw, str) else s, tool_name)
    if _holders:
        for k, val in out.items():
            if isinstance(val, str) and val in _holders:
                out[k] = _holders[val]
    return out


_PATH_PARAM_NAMES = frozenset({
    "path", "cwd", "file", "filepath", "filename", "directory", "folder",
    "source", "url", "root", "dir",
})
_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _path_unescape(inner: str) -> str:
    """Unescape a raw drive-path value: every backslash is literal."""
    prot = inner.replace("\\\\", "\x00")
    prot = re.sub(r"\\(.)", r"\\\1", prot, flags=re.DOTALL)
    return prot.replace("\x00", "\\")


def _extract_path_params(s: str, tool_name: str = "") -> tuple:
    """Replace drive-path param values with holders. Returns (text, holders)."""
    holders: Dict[str, str] = {}
    try:
        from .tools import get_tool_spec
        spec = get_tool_spec(tool_name) if tool_name else None
        props = (spec.parameters.get("properties", {}) or {}) if spec else {}
    except Exception:
        props = {}
    names = [n for n, p in props.items() if (p or {}).get("type", "string") == "string"]
    names += [n for n in _PATH_PARAM_NAMES if n not in names]

    def _repl(m: "re.Match") -> str:
        key, inner = m.group(1), m.group(2)
        if key in names and _DRIVE_PATH_RE.match(inner):
            holder = f"__WOLF_PATH_{len(holders)}__"
            holders[holder] = _path_unescape(inner)
            return f'"{key}": "{holder}"'
        return m.group(0)

    try:
        fixed = re.sub(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*"((?:[^"\\]|\\.)*)"', _repl, s)
    except re.error:
        return s, {}
    return fixed, holders


def _regex_extract_params(s: str, tool_name: str = "") -> Dict[str, Any]:
    """Last-resort per-parameter regex extraction."""
    try:
        from .tools import get_tool_spec
        spec = get_tool_spec(tool_name) if tool_name else None
        props = (spec.parameters.get("properties", {}) or {}) if spec else {}
    except Exception:
        props = {}
    out: Dict[str, Any] = {}
    for pname, pinfo in props.items():
        ptype = (pinfo or {}).get("type", "string")
        if ptype in ("integer", "number", "boolean"):
            m = re.search(r'"' + re.escape(pname) + r'"\s*:\s*(-?\d+(?:\.\d+)?|true|false|null)', s)
            if m:
                try:
                    out[pname] = json.loads(m.group(1))
                    continue
                except (json.JSONDecodeError, ValueError):
                    pass
        m = re.search(r'"' + re.escape(pname) + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', s)
        if m:
            inner = m.group(1)
            if pname in _PATH_PARAM_NAMES and _DRIVE_PATH_RE.match(inner):
                out[pname] = _path_unescape(inner)
                continue
            frag = '"' + inner + '"'
            try:
                out[pname] = json.loads(frag)
            except (json.JSONDecodeError, ValueError):
                try:
                    out[pname] = json.loads(re.sub(r"\\(?![\\/bfnrtu\"])", r"\\\\", frag))
                except (json.JSONDecodeError, ValueError):
                    out[pname] = inner
    return out


def _coerce_value(value: str) -> Any:
    """Coerce string value to int/float/bool/None if possible.

    تحويل القيمة النصية إلى نوع مناسب (رقم/منطقي/فارغ) إن أمكن.
    """
    # Try JSON
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        pass

    # Common literals
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    if value.lower() in ("null", "none", ""):
        return None

    # Try int
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    return value  # Return as string


def execute_tool_calls(
    parsed: ParsedResponse,
    max_iterations: int = 5,
) -> Tuple[str, List[ToolResult]]:
    """Execute all parsed tool calls.

    تنفيذ جميع استدعاءات الأدوات المحللة.

    Returns (text_without_tool_calls, list_of_results).
    """
    results = []
    for tc in parsed.tool_calls[:max_iterations]:
        result = execute_tool(tc.name, tc.arguments)
        results.append(result)
    return parsed.text, results


def format_tool_results_for_followup(results: List[ToolResult], max_chars: int = 5000) -> str:
    """Format tool results to feed back into a follow-up model call.

    تنسيق نتائج الأدوات لتغذيتها في استدعاء متابعة للنموذج.

    max_chars caps embedded output (read_file follow-ups pass a larger budget
    so the model sees whole files instead of a truncated head).
    """
    if not results:
        return ""

    lines = ["\n\n[Tool Results | نتائج الأدوات]"]
    for r in results:
        status = "✓" if r.success else "✗"
        lines.append(f"\n{status} {r.tool_name} ({r.duration_ms:.0f}ms)")
        if r.success:
            output_str = json.dumps(r.output, ensure_ascii=False, default=str)
            if len(output_str) > max_chars:
                output_str = output_str[:max_chars] + "... (truncated)"
            lines.append(f"  Output: {output_str}")
        else:
            lines.append(f"  Error: {r.error}")
    lines.append(
        "\n\n=== SYSTEM INSTRUCTION ===\n"
        "You are an AI assistant answering a USER question. The block above contains "
        "REAL tool output data. Your job:\n"
        "1. READ the tool output carefully.\n"
        "2. ANSWER the user's original question USING the data above.\n"
        "3. NEVER copy the '[Tool Results]' header, tool names, or raw JSON into your answer.\n"
        "4. NEVER repeat the tool output verbatim — synthesize a concise response.\n"
        "5. If the tool output is a file, summarize its CONTENT.\n"
        "6. Respond in the SAME language as the user's question."
    )
    return "\n".join(lines)


# ============================================================================
# Explicit-intent detectors (deterministic fallbacks when the model calls
# nothing despite an explicit user request — FIX 2026-09-26, user-observed)
# ============================================================================

_SEARCH_INTENT_RE = re.compile(
    r"(ابحث|إبحث|ابحثي|ابحث لي|دور على|دوّر على|\bsearch the web\b|\bsearch for\b"
    r"|\bsearch about\b|\bgoogle it\b|\bgoogle\b|\blook up\b|\blook it up\b)",
    re.IGNORECASE,
)
_DATE_INTENT_RE = re.compile(
    r"(تاريخ اليوم|ايه النهاردة|النهاردة ايه|الساعة كام|الوقت الحالي|التاريخ الحالي"
    r"|كم الساعة|الساعة الان|الساعة الآن|الوقت الان|الوقت الآن"
    r"|\bwhat('s| is) (today'?s date|the date|the time)\b|\bcurrent (date|time)\b"
    r"|\btoday'?s date\b|\bwhat time is it\b|\bwhat is the time\b|\bwhat is today\b)",
    re.IGNORECASE,
)
_SEARCH_VERBS_RE = re.compile(
    r"(ابحث|إبحث|ابحثي|ابحث لي|على الويب|على الانترنت|على الإنترنت"
    r"|\bsearch the web\b|\bsearch for\b|\bsearch about\b|\bgoogle it\b"
    r"|\bgoogle\b|\blook up\b|\blook it up\b|\bplease\b|\bمن فضلك\b)",
    re.IGNORECASE,
)
_INSTRUCTION_TAIL_RE = re.compile(
    r"(وأعطني|واعطني|وأخبرني|واخبرني|مع روابط?|مع مصادر?|مع الروابط|مع المصادر"
    r"|\bgive me\b|\btell me\b|\bwith links?\b|\bwith sources?\b|\band give\b).*",
    re.IGNORECASE | re.DOTALL,
)
_LEADING_TOPIC_WORD_RE = re.compile(
    r"^(عن|على|حول|ل|about|on|for|of)\s+", re.IGNORECASE,
)
_PATH_TOKEN_RE = re.compile(
    r"([A-Za-z]:[\\/][\w\-. \\/]+|[\w\-.\\/]*\.[\w]+)",
)
# file:///D:/A/.../x.html (browsers paste %20 for spaces). Decoded to a
# local path and read — FIX 2026-09-26 (user-observed refusal on 3d-clock).
_FILE_URL_RE = re.compile(r"file:///[^\s\"'<>]+", re.IGNORECASE)


def normalize_file_url(text: str) -> str:
    """Extract first file:// URL and decode to a local path ("" if none)."""
    m = _FILE_URL_RE.search(text or "")
    if not m:
        return ""
    try:
        import urllib.parse as _up
        import urllib.request as _urlreq
        return _urlreq.url2pathname(_up.urlparse(m.group(0)).path)
    except Exception:
        return ""


def detect_file_url(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """A pasted file:// link IS a readable local file — read it.

    رابط file:// الملصق ملف محلي مقروء — اقرأه.
    Fires regardless of verbs (e.g. "make better than <file://...>").
    """
    path = normalize_file_url(user_text or "")
    if path:
        return ("read_file", {"path": path})
    return None
_READ_INTENT_RE = re.compile(
    r"(اقرأ|إقرأ|افتح|اعرض|استعرض|\bread\b|\bopen\b).{0,20}(الملف|ملف|file)",
    re.IGNORECASE | re.DOTALL,
)
_LIST_INTENT_RE = re.compile(
    r"(list_directory|اعرض محتويات|استخدم list_directory|محتويات المجلد"
    r"|\blist (the |files|directory|folder|all files))",
    re.IGNORECASE,
)
_SKILL_INSTALL_INTENT_RE = re.compile(
    r"(install_skill|ثبت (مهارة|أداة)|أنشئ (مهارة|أداة)|اصنع (مهارة|أداة)"
    r"|create.{0,10}skill|add.{0,10}skill)",
    re.IGNORECASE | re.DOTALL,
)
_SKILL_RUN_INTENT_RE = re.compile(
    r"(run_skill|شغل (المهارة|مهارة)|شغلي|نفذ (المهارة|مهارة)|شغل لي"
    r"|run.{0,10}skill|execute.{0,10}skill)",
    re.IGNORECASE | re.DOTALL,
)
_SKILL_RUN_NAME_RE = re.compile(
    r"(?:المهارة|مهارة|skill)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_AR_KWARG_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:تساوي|يساوي|=|:)\s*(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SKILL_NAME_RE = re.compile(
    r"(?:اسمها|باسم|اسمه|name|named)\s*[\"':=\s]*([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def has_search_intent(text: str) -> bool:
    """True when the user explicitly asks to search the web."""
    return bool(text and _SEARCH_INTENT_RE.search(text))


def has_date_intent(text: str) -> bool:
    """True when the user asks for current date/time."""
    return bool(text and _DATE_INTENT_RE.search(text))


def extract_search_topic(user_text: str) -> str:
    """Extract a clean engine query from a search request.

    استخراج موضوع بحث نظيف: strips command verbs AND instruction tails
    ("... وأعطني أهم نتيجتين مع رابطهما" -> topic only).
    """
    topic = _SEARCH_VERBS_RE.sub(" ", user_text or "")
    topic = _INSTRUCTION_TAIL_RE.sub(" ", topic)
    topic = _LEADING_TOPIC_WORD_RE.sub("", topic.strip())
    topic = re.sub(r"\s+", " ", topic).strip(" .؟?!\u061f")
    return topic[:500] or (user_text or "")[:500]


def detect_file_op(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect explicit read/list requests with a usable path.

    كشف طلبات القراءة/العرض الصريحة مع مسار قابل للاستخدام.
    Returns (tool_name, args) or None.
    """
    text = user_text or ""
    if _READ_INTENT_RE.search(text):
        m = _PATH_TOKEN_RE.search(text)
        if m:
            return ("read_file", {"path": m.group(1).strip()})
        return None
    if _LIST_INTENT_RE.search(text):
        if re.search(r"(الحالي|الحالية|current|\bhre\b|\bhere\b)", text, re.IGNORECASE):
            return ("list_directory", {"path": "."})
        m = _PATH_TOKEN_RE.search(text)
        if m:
            return ("list_directory", {"path": m.group(1).strip()})
        return ("list_directory", {"path": "."})
    return None


def detect_skill_install(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect explicit skill-install requests with name + Python source.

    كشف طلبات تثبيت مهارة صريحة مع الاسم والكود.
    Source: fenced ```python block preferred, else `def run` span to end.
    Returns (install_skill, args) or None when name/source unusable.
    """
    text = user_text or ""
    if not _SKILL_INSTALL_INTENT_RE.search(text):
        return None
    name_m = _SKILL_NAME_RE.search(text)
    if not name_m:
        return None
    fence_m = _CODE_FENCE_RE.search(text)
    if fence_m and "def run" in fence_m.group(1):
        source = fence_m.group(1).strip()
    else:
        run_at = text.find("def run")
        if run_at == -1:
            return None
        source = text[run_at:].strip()
    if "def run" not in source:
        return None
    return ("install_skill", {"name": name_m.group(1), "source": source})


def detect_skill_run(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect explicit skill-run requests (Arabic prose kwargs supported).

    كشف طلبات تشغيل مهارة صريحة (يدعم وسائط عربية مثل a تساوي 5).
    Returns (run_skill, args) or None.
    """
    text = user_text or ""
    if not _SKILL_RUN_INTENT_RE.search(text):
        return None
    name_m = _SKILL_RUN_NAME_RE.search(text)
    if not name_m:
        return None
    args: Dict[str, Any] = {}
    json_m = re.search(r"\{[^{}]*\}", text)
    if json_m:
        try:
            parsed_args = json.loads(json_m.group(0))
            if isinstance(parsed_args, dict):
                args = parsed_args
        except (json.JSONDecodeError, ValueError):
            pass
    if not args:
        for k, v in _AR_KWARG_RE.findall(text):
            args[k] = float(v) if "." in v else int(v)
    return ("run_skill", {"skill_name": name_m.group(1), "arguments": args})


_BUILD_INTENT_RE = re.compile(
    r"(أنشئ|انشئ|اصنع|اصنعي|ابن[يى]|ابني|برمج|اكتب لي|طور|انتج|صمم|بني|بنيه|أنشئ|أنشئي|اعمل|اعملي|create|build|scaffold|set up|setup|develop|code|program|write me|make me|design)"
    r".{0,40}(مشروع|مشروعا|تطبيق|تطبيقا|تطبيقات|برنامج|ملفات|app|project|application|script|tool|أداة|سكربت|كود|code|system|نظام|بوت|bot|agent|وكيل)",
    re.IGNORECASE | re.DOTALL,
)
# Stricter pattern for "X for Y" / "X لـ Y" (Todo, calculator, etc.) — when the
# user names the app idea explicitly, this fires even without a strong verb.
# Allows optional intervening English/Arabic words (e.g. "تطبيق Python لـ Todo").
_BUILD_FOR_RE = re.compile(
    r"(?:تطبيق|برنامج|أداة|سكربت|app|script|tool|program)"
    r"(?:\s+[\w\u0600-\u06FF]+){0,4}\s*"
    r"(?:للـ|ل|لـ|for|to|that|يقوم بـ|يفعل|يعمل|تعمل|تعمل لـ|يحسب|يحسب الـ|يحسب|بسيط|بسيطة|صغير|صغيرة|small|simple|prints|يطبع|تطبع|لحساب|يحسب)"
    r"(?:\s+(?:من|from)?\s*\d+(?:\s*(?:إلى|الى|to|to \d+))?)?"
    r"\s+([\w\u0600-\u06FF][\w \u0600-\u06FF\-]{0,40})?",
    re.IGNORECASE,
)
_BUILD_NAME_RE = re.compile(
    r"(?:باسم|اسمه|بإسم|name[d]?)\s+[\"']?([A-Za-z_][A-Za-z0-9_\-]*)",
    re.IGNORECASE,
)
# Must NOT hijack skill creation (handled by detect_skill_install).
_SKILL_WORD_RE = re.compile(r"(مهارة|أداة|skill)", re.IGNORECASE)

_PLAN_INTENT_RE = re.compile(
    r"(خطط|خطة|مهمة طويلة|مهمة معقدة|على مراحل|بمراحل|مراحل العمل"
    r"|\bplan\b|\bmilestones?\b|\bstep.by.step\b|\bmulti.step\b|\broadmap\b)",
    re.IGNORECASE,
)

_SKILL_URL_INTENT_RE = re.compile(
    r"(ثبت|ثبتي|حمل|حملي|نزل|نزلي|أضف|اضف|ركب).{0,25}(مهارة|مهارات|أداة|skill)"
    r"|(install|download|fetch|add).{0,25}skill"
    r"|skills\.sh",
    re.IGNORECASE | re.DOTALL,
)
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


_SELF_CAP_INTENT_RE = re.compile(
    r"(قدراتك|قدراتك|ماذا تستطيع|ماذا يمكنك|ماذا تملك|أدواتك|ادواتك|مهاراتك"
    r"|من أنت\s.*تقدر|عرف بنفسك وقدراتك"
    r"|ما اسمك|من أنت|عرف نفسك|انت مين|أنت مين"
    r"|\bwhat can you do\b|\blist your tools\b|\bwhat tools do you have\b"
    r"|\bwho are you\b|\bwhat('s| is) your name\b|\byour name\b"
    r"|\byour (capabilities|skills)\b|\bwho are you\b.{0,30}\bwhat\b)",
    re.IGNORECASE | re.DOTALL,
)


def detect_my_capabilities(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect 'what can you do / list your tools' questions.

    كشف أسئلة القدرات — تُجاب بالخريطة الحية لا بالذاكرة.
    """
    if user_text and _SELF_CAP_INTENT_RE.search(user_text):
        return ("my_capabilities", {})
    return None


# FIX Phase 44 (2026-10-04): agent was claiming "لا أستطيع الوصول إلى قواعد
# البيانات" despite carrying query_body_kb + 4 memory layers. Detect ANY
# database/memory access question and force my_capabilities as proof.
_DATABASE_INTENT_RE = re.compile(
    r"(?:قواعد\s*(?:ال)?بيانات|قاعد[ةه]\s*(?:ال)?بيانات|قاعد[ةه]\s*معرفي"
    r"|knowledge\s*base|kb_|access\s*database|access\s*memory"
    r"|ذاكرت[كه]|ذاكرتك|ذاكر(?:ة|ت|ات)\s*(?:طويلة|دائمة|بصري)?"
    r"|persistent\s*memory|episodic\s*memory|semantic\s*memory"
    r"|الوصول\s*إلى\s*قواعد|تستطيع\s*الوصول|تستطيع\s*الوصول\s*إلى"
    r"|هل\s*لديك\s*قواعد|هل\s*لديك\s*قاعدة|عندي\s*قاعدة"
    r"|احفظ\s*معلوم|إضافة\s*معلوم|حفظ\s*معلوم|اضف\s*معلوم"
    r"|do\s*you\s*have\s*(?:a\s*)?(?:database|memory|persistent|knowledge|kb)"
    r"|can\s*you\s*access\s*(?:database|memory|persistent|knowledge|kb)"
    r"|can\s*you\s*store\s*information|can\s*you\s*save\s*information"
    r"|do\s*you\s*remember)",
    re.IGNORECASE | re.DOTALL,
)


def detect_database_intent(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect questions about database / memory access — force my_capabilities.

    كشف أسئلة الوصول إلى قواعد البيانات / الذاكرة — يجبر my_capabilities
    لإثبات القدرة فعلياً.
    """
    if user_text and _DATABASE_INTENT_RE.search(user_text):
        return ("my_capabilities", {})
    return None


# ============================================================================
# Phase 52 (2026-10-06): FORCE-EXECUTE detectors
# ============================================================================
# Review Grade C found T01/T02/T08/T09/T10 failures: the model hallucinates
# answers (time / math / capabilities / directory listings) WITHOUT calling
# tools. We cannot trust the model's intent → we DETECT the triggers ourselves
# and force the tool call, regardless of what the model emits.
#
# Priority: HIGHEST in decide_forced_calls — beats database / date / search /
# capabilities (weak intent detectors). Solves T01, T02, T08, T09, T10.

_MATH_FORCE_RE = re.compile(
    r"[\d]+\s*[+\-*/×÷^%]\s*[\d]+|[\d]+\s*\*\*\s*[\d]+",
    re.UNICODE,
)

_TIME_FORCE_RE = re.compile(
    r"(?:الساعة|الوقت|كم\s*الساعة|كم\s*الوقت|what\s*time|current\s*time|time\s*now|now)",
    re.IGNORECASE,
)

_LS_FORCE_RE = re.compile(
    r"(?:^|\s)(?:ls|dir|list\s+(?:files|directory|folder|contents))",
    re.IGNORECASE,
)


def detect_force_execute(user_text: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Detect prompts that REQUIRE tool calls (regardless of model intent).

    كشف الـ prompts التي تحتاج tool calls بشكل قاطع (حتى لو النموذج لم يطلبها).
    يحل T01, T02, T08, T09, T10 من الـ review Grade C (2026-10-06).

    Order matters: math FIRST (cheap check), then time, then ls.
    """
    if not user_text:
        return []
    text = user_text.strip()

    # Math expression — execute_python
    m = _MATH_FORCE_RE.search(text)
    if m:
        expr = m.group(0).replace("×", "*").replace("÷", "/").strip()
        # Verify it's actually math (not random numbers like "Version 5")
        if any(op in expr for op in ['+', '-', '*', '/', '^', '%', '**']):
            return [("execute_python", {"code": f"print({expr})", "timeout_seconds": 5})]

    # Time/date query — system_time
    if _TIME_FORCE_RE.search(text):
        return [("system_time", {})]

    # List directory — list_directory
    if _LS_FORCE_RE.search(text):
        # Extract path if present (after the verb)
        path_match = re.search(r"(?:ls|dir|list)\s+(?:of\s+)?(.+?)$", text)
        path = path_match.group(1).strip() if path_match else "."
        return [("list_directory", {"path": path})]

    return []


# FIX 2026-09-26 (user-observed failure S3 "احسب 25 * 47" returned 400):
# Arabic/English calc requests must trigger execute_python BEFORE file/url
# detectors (and before the model sees them — this avoids the 400 overflow
# that happens when the Arabic "احسب 25 * 47" consumes 13017 chars of context).
_CALC_INTENT_RE = re.compile(
    r"(احسب|احسبي|حساب|عملية\s*حساب|قاعدة\s*حساب"
    r"|كم\s*يساوي|يساوي\s*كم|ما\s*ناتج|ناتج\s*عملية"
    r"|what(?:'s| is) \d|calculate|compute|solve|evaluate)",
    re.IGNORECASE | re.DOTALL,
)

_MATH_EXPR_RE = re.compile(
    r"(\d+(?:\.\d+)?(?:\s*[+\-*/×÷^%]\s*\d+(?:\.\d+)?)+(?:\s*[+\-*/×÷^%]\s*\d+(?:\.\d+)?)*)",
)


def detect_calc_intent(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect arithmetic/calculation requests.

    كشف طلبات الحساب والرياضيات.
    Returns (execute_python, args) or None.
    """
    if not user_text:
        return None
    if _CALC_INTENT_RE.search(user_text) or _MATH_EXPR_RE.search(user_text):
        # Extract the math expression
        m = _MATH_EXPR_RE.search(user_text)
        if m:
            expr = m.group(1).replace("×", "*").replace("÷", "/").strip()
            code = f"print({expr})"
            return ("execute_python", {"code": code, "timeout_seconds": 10})
        # Fallback: pass the whole text and let execute_python extract
        return ("execute_python", {"code": f"# {user_text}\nprint('No expression detected')", "timeout_seconds": 5})
    return None


_IMAGE_WORD_RE = re.compile(
    r"(صورة|صوره|لقطة|لقطه|سكرين|سكرينشوت|image|picture|photo|screenshot|صوره\s)",
    re.IGNORECASE,
)
_SEE_INTENT_RE = re.compile(
    r"(شوف|اوصف|صِف|صف|ماذا ترى|ماذا في|describe|look at|what do you see"
    r"|analyze.{0,15}image|read.{0,15}screenshot)",
    re.IGNORECASE | re.DOTALL,
)
_IMAGE_PATH_RE = re.compile(
    r"([A-Za-z]:[\\/][\w\-. \\/]*\.(?:png|jpg|jpeg|webp|gif|bmp)"
    r"|[\w\-.\\/]*\.(?:png|jpg|jpeg|webp|gif|bmp))",
    re.IGNORECASE,
)


def detect_see_image(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect explicit look-at-image requests with a usable image path.

    كشف طلبات النظر إلى صورة صريحة مع مسار قابل للاستخدام.
    You have no eyes — see_image is how you look. Returns (see_image, args).
    """
    text = user_text or ""
    if not (_IMAGE_WORD_RE.search(text) and _SEE_INTENT_RE.search(text)):
        return None
    m = _IMAGE_PATH_RE.search(text)
    if not m:
        return None
    return ("see_image", {"image_path": m.group(1).strip()})


def detect_skill_url_install(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect install-skill-from-URL requests (skills.sh / GitHub / direct).

    كشف طلبات تثبيت مهارة من رابط. Name: explicit or URL-derived tail
    (.py stem / last path segment, sanitized). Returns (install_skill_from_url, args).
    """
    text = user_text or ""
    if not _SKILL_URL_INTENT_RE.search(text):
        return None
    url_m = _URL_RE.search(text)
    if not url_m:
        return None
    url = url_m.group(0).rstrip(".,;!")
    name = ""
    name_m = _SKILL_NAME_RE.search(text)
    if name_m:
        name = name_m.group(1)
    if not name:
        try:
            import urllib.parse as _up
            tail = _up.urlparse(url).path.rstrip("/").split("/")[-1]
        except Exception:
            tail = ""
        tail = re.sub(r"\.(py|md)$", "", tail, flags=re.IGNORECASE)
        name = re.sub(r"[^A-Za-z0-9_]+", "_", tail).strip("_")
    if not name:
        return None
    return ("install_skill_from_url", {"url": url, "name": name})


def detect_plan_goal(user_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Detect long-task planning requests; persist the plan shell as a goal.

    كشف طلبات التخطيط لمهام طويلة؛ حفظ هيكل الخطة كهدف.
    Title/description come VERBATIM from the request (no invented content).
    """
    text = (user_text or "").strip()
    if not text or not _PLAN_INTENT_RE.search(text):
        return None
    title = re.sub(r"\s+", " ", text)[:80]
    return ("track_goal", {"title": title, "description": text[:500], "priority": 6})


_REFUSAL_MARKERS = (
    "لا يمكنني الوصول", "لا أستطيع الوصول", "لا استطيع الوصول",
    "cannot access", "cannot directly access", "no internet access",
    "lack internet", "قيود الأمان", "security restriction",
    "انسخ والصق", "paste the code", "cannot browse", "can't browse",
)


def is_refusal_text(text: str) -> bool:
    """True when a model reply is a refusal/stall (AR/EN markers).

    كشف نص الرفض. Used to keep refusals OUT of follow-up context: appending
    a refusal as assistant history makes the model defend it (consistency
    lock) even after tools succeeded — FIX 2026-09-26, user-observed.
    """
    t = (text or "").lower()
    return any(m.lower() in t for m in _REFUSAL_MARKERS)


def neutral_bridge() -> str:
    """Neutral assistant stub replacing a refusal in follow-up context."""
    return "[Checking with tools… | جارٍ الفحص بالأدوات…]"


def detect_build_project(user_text: str) -> Optional[List[Tuple[str, Dict[str, Any]]]]:
    """Detect explicit project/app-building requests (outside the body).

    كشف طلبات بناء مشروع/تطبيق صريحة (خارج الجسد).
    Returns a list of forced starter calls [track_goal, run_shell mkdir]
    or None (no intent / skill request / no usable name).

    FIX 2026-09-26 (Phase 38): now also fires on the "تطبيق X لـ Y" pattern
    (Todo, calculator, etc.) where the user names the app without an explicit
    build verb. This rescues the common "ابني لي تطبيق Python لـ Todo" prompt
    that used to fall through to the model and get answered with markdown.

    Even when no name is found (e.g. "اكتب لي تطبيق بسيط"), returns a
    starter call with a generic name so the model is forced to continue
    with tool calls instead of just emitting code as text.
    """
    text = user_text or ""
    has_strong_intent = bool(_BUILD_INTENT_RE.search(text))
    has_app_name = bool(_BUILD_FOR_RE.search(text))
    if not (has_strong_intent or has_app_name):
        return None
    if _SKILL_WORD_RE.search(text):
        return None  # skill install has its own detector

    # Try explicit "باسم X" first, then "تطبيق لـ X" form.
    name_m = _BUILD_NAME_RE.search(text)
    name = name_m.group(1) if name_m else ""
    if not name:
        m2 = _BUILD_FOR_RE.search(text)
        if m2 and m2.group(1):
            name = re.sub(r"\W+", "_", m2.group(1)).strip("_")[:30]
    if not name:
        # Fallback: extract any word that looks like a project name from the
        # second half of the text, or default to a generic name.
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_\-]{2,30}", text)
        if words:
            name = words[-1][:30]
        else:
            name = "new_app"
    return [
        ("track_goal", {"title": f"Build {name}",
                        "description": (user_text or "")[:500], "priority": 7}),
        ("run_shell", {"command": f"mkdir -p {name}",
                        "cwd": "", "timeout_seconds": 15}),
    ]


def decide_forced_calls(user_text: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Decide deterministic fallback tool calls for an explicit request.

    تحديد استدعاءات الأدوات الحتمية لطلب صريح — دالة خالصة بلا I/O.

    Single priority chain shared by streaming + non-streaming paths, so both
    behave identically and every branch is unit-testable (a NameError here
    would crash live streams — the suite pins all branches).
    Order: database → date → search → capabilities → calc → file:// →
    file-op → sight → skill-install → skill-URL → skill-run → build → plan.
    FIX Phase 44 (2026-10-04): database/memory access questions are now
    HIGHEST priority — forces my_capabilities so the agent cannot refuse.
    """
    q = user_text or ""
    if not q:
        return []
    # Phase 52 (2026-10-06): force-execute math/time/ls regardless of model
    # intent (solves Grade C failures T01/T02/T08/T09/T10).
    _force_calls = detect_force_execute(q)
    if _force_calls:
        return _force_calls
    # Phase 44: database / memory access questions → force my_capabilities
    _db_intent = detect_database_intent(q)
    if _db_intent:
        return [_db_intent]
    if has_date_intent(q):
        return [("system_time", {})]
    if has_search_intent(q):
        return [("web_search", {"query": extract_search_topic(q), "max_results": 5})]
    if detect_my_capabilities(q):
        return [("my_capabilities", {})]
    # NEW: calc/math detector before file/url detectors (calc is common in Arabic)
    _calc_op = detect_calc_intent(q)
    if _calc_op:
        return [_calc_op]
    if detect_file_url(q):
        return [("read_file", {"path": normalize_file_url(q)})]
    _file_op = detect_file_op(q)
    if _file_op:
        return [_file_op]
    _see_op = detect_see_image(q)
    if _see_op:
        return [_see_op]
    _skill_op = detect_skill_install(q) or detect_skill_url_install(q) or detect_skill_run(q)
    if _skill_op:
        return [_skill_op]
    _build_calls = detect_build_project(q)
    if _build_calls:
        return _build_calls
    _plan_op = detect_plan_goal(q)
    if _plan_op:
        return [_plan_op]
    return []


def format_tools_description() -> str:
    """Format a brief tools list for prompt injection (no JSON schema).

    تنسيق قائمة الأدوات للحقن في الـ prompt.
    """
    lines = [
        "# Tools | الأدوات",
        "",
        "To use a tool, output: <tool_call name=\"TOOL_NAME\"><arg>value</arg></tool_call>",
        "",
    ]
    for spec in TOOL_SPECS:
        params = spec.parameters.get("properties", {})
        param_str = ", ".join(params.keys())
        danger = " ⚠️" if spec.dangerous else ""
        lines.append(f"- **{spec.name}**{danger}: {spec.description} | {spec.description_ar}")
        if param_str:
            lines.append(f"  - Args: {param_str}")
    return "\n".join(lines)


# ============================================================================
# Self-Test (Iron Law #15)
# ============================================================================

def _self_test() -> bool:
    """Verify the parser works correctly.

    التحقق من أن المحلل يعمل بشكل صحيح.
    """
    print("Running tool_calling self-tests...")
    print("تشغيل اختبارات المحلل الذاتية...")

    passed = 0
    failed = 0

    # Test 1: Parse single tool call
    sample = """Let me read the file.
<tool_call name="read_file">
<path>/tmp/test.txt</path>
</tool_call>
Done."""
    parsed = parse_tool_calls(sample)
    if parsed.has_tool_calls and len(parsed.tool_calls) == 1:
        if parsed.tool_calls[0].name == "read_file":
            if parsed.tool_calls[0].arguments.get("path") == "/tmp/test.txt":
                passed += 1
                print("  ✓ parse single tool call")
            else:
                failed += 1
                print(f"  ✗ wrong args: {parsed.tool_calls[0].arguments}")
        else:
            failed += 1
            print(f"  ✗ wrong name: {parsed.tool_calls[0].name}")
    else:
        failed += 1
        print(f"  ✗ parse failed: {parsed.to_dict()}")

    # Test 2: Multiple tool calls
    sample2 = """Two calls:
<tool_call name="list_directory">
<path>.</path>
</tool_call>
<tool_call name="execute_python">
<code>print("hi")</code>
</tool_call>"""
    parsed2 = parse_tool_calls(sample2)
    if len(parsed2.tool_calls) == 2:
        passed += 1
        print("  ✓ parse multiple tool calls")
    else:
        failed += 1
        print(f"  ✗ expected 2 calls, got {len(parsed2.tool_calls)}")

    # Test 3: No tool calls
    parsed3 = parse_tool_calls("Just regular text, no tools here.")
    if not parsed3.has_tool_calls:
        passed += 1
        print("  ✓ no tool calls detected correctly")
    else:
        failed += 1
        print(f"  ✗ false positive: {parsed3.to_dict()}")

    # Test 3b: UNCLOSED <tool_call> (Round 13 — real model output)
    sample3b = ('<tool_call name="system_status">\n'
                '<system_status></system_status>')
    parsed3b = parse_tool_calls(sample3b)
    if (parsed3b.has_tool_calls
            and parsed3b.tool_calls[0].name == "system_status"
            and "<tool_call" not in parsed3b.text):
        passed += 1
        print("  ✓ parse UNCLOSED tool_call (no leaked protocol text)")
    else:
        failed += 1
        print(f"  ✗ unclosed tool_call: {parsed3b.to_dict()}")

    # Test 4: Type coercion
    sample4 = """<tool_call name="execute_python">
<code>x = 1</code>
<timeout_seconds>10</timeout_seconds>
</tool_call>"""
    parsed4 = parse_tool_calls(sample4)
    if parsed4.tool_calls:
        timeout = parsed4.tool_calls[0].arguments.get("timeout_seconds")
        if isinstance(timeout, int) and timeout == 10:
            passed += 1
            print("  ✓ type coercion (string -> int)")
        else:
            failed += 1
            print(f"  ✗ coercion failed: {type(timeout)} = {timeout}")
    else:
        failed += 1
        print(f"  ✗ no parse")

    # Test 5: Execute parsed calls
    parsed5 = parse_tool_calls("""<tool_call name="execute_python">
<code>print(1+1)</code>
</tool_call>""")
    text, results = execute_tool_calls(parsed5)
    if results and results[0].success and "2" in results[0].output.get("stdout", ""):
        passed += 1
        print("  ✓ execute parsed tool call end-to-end")
    else:
        failed += 1
        print(f"  ✗ execute failed: {results[0].error if results else 'no results'}")

    # Test 6: Unclosed tool call (FIX 2026-09-26 Round 13).
    # OLD CONTRACT (rejected unclosed calls) was WRONG: live model output
    # stopped mid-format, the call never ran, and the raw <tool_call> text was
    # shown to the user. Now the call is recovered. A block with NO name is
    # still ignored (no guessing).
    parsed6 = parse_tool_calls("""<tool_call name="read_file">
<path>/tmp/x</path>
""")  # No closing tag
    parsed6b = parse_tool_calls("""<tool_call>
<path>/tmp/x</path>
""")  # No name attribute -> must stay ignored
    if (parsed6.has_tool_calls and parsed6.tool_calls[0].name == "read_file"
            and parsed6.tool_calls[0].arguments.get("path") == "/tmp/x"
            and not parsed6b.has_tool_calls):
        passed += 1
        print("  ✓ unclosed call recovered, nameless block ignored")
    else:
        failed += 1
        print(f"  ✗ unclosed handling: {parsed6.to_dict()} / {parsed6b.to_dict()}")

    # Test 7: Narrated markdown call (**Tool Call:** + ```json)
    parsed7 = parse_tool_calls(
        '**Tool Call:** write_file\n**Arguments:**\n```json\n'
        '{"path": "x.txt", "content": "hi"}\n```\nDone.'
    )
    if (parsed7.has_tool_calls and parsed7.tool_calls[0].name == "write_file"
            and parsed7.tool_calls[0].arguments.get("path") == "x.txt"
            and "<tool" not in parsed7.text.lower()
            and "write_file" not in parsed7.text):
        passed += 1
        print("  ✓ narrated markdown call parsed + stripped")
    else:
        failed += 1
        print(f"  ✗ narrated parse failed: {parsed7.to_dict()}")

    # Test 8: Sloppy JSON args (single-backslash Windows path as the model emits it)
    _bs = chr(92)
    sloppy = '{"path": "D:' + _bs + 'A' + _bs + 'x' + _bs + 'f.txt", "append": false}'
    args8 = parse_tool_arguments(sloppy, "write_file")
    if args8.get("path") == "D:" + _bs + "A" + _bs + "x" + _bs + "f.txt" and args8.get("append") is False:
        passed += 1
        print("  ✓ sloppy JSON args tolerated")
    else:
        failed += 1
        print(f"  ✗ sloppy args failed: {args8}")

    # Test 9: Narrated envelope with NESTED params + "function" key
    parsed9 = parse_tool_calls(
        'Plan:\n```json\n{"function": "track_goal", "params": '
        '{"title": "X", "steps": [{"a": 1}]}}\n```\nAfter.'
    )
    if (parsed9.has_tool_calls and parsed9.tool_calls[0].name == "track_goal"
            and parsed9.tool_calls[0].arguments.get("title") == "X"
            and "track_goal" not in parsed9.text):
        passed += 1
        print("  ✓ nested envelope parsed + stripped")
    else:
        failed += 1
        print(f"  ✗ envelope parse failed: {parsed9.to_dict()}")

    # Test 10: Backtick pseudo-call `track_goal("Name", [...])`
    parsed10 = parse_tool_calls(
        'Do it:\n`track_goal("NotesApp", ["a", "b"])`\n`list_goals("NotesApp")`\nDone.'
    )
    names10 = [tc.name for tc in parsed10.tool_calls]
    if ("track_goal" in names10 and "list_goals" in names10
            and "track_goal(" not in parsed10.text):
        passed += 1
        print("  ✓ backtick pseudo-calls parsed + stripped")
    else:
        failed += 1
        print(f"  ✗ backtick parse failed: {parsed10.to_dict()}")

    # Test 11: Prose mentions of unknown calls are NEVER executed
    parsed11 = parse_tool_calls('I used `frobnicate("x")` and `print("hi")` here.')
    if not parsed11.has_tool_calls:
        passed += 1
        print("  ✓ unknown backtick calls ignored")
    else:
        failed += 1
        print(f"  ✗ unknown executed: {parsed11.to_dict()}")

    # Tests 12-21: decide_forced_calls covers EVERY fallback branch.
    # (Regression guard: a NameError/dropped import here crashes live streams.)
    _chain_cases = [
        ("ما تاريخ اليوم؟", "system_time"),
        ("ابحث على الويب عن الذكاء الاصطناعي", "web_search"),
        ("ما هي كل أدواتك؟", "my_capabilities"),
        ("اقرأ file:///D:/A/x%20y/f.txt من فضلك", "read_file"),
        ("اقرأ الملف E:/a/b/README.md ملخص", "read_file"),
        ("شوف الصورة C:/img/shot.png واوصفها", "see_image"),
        ("ثبت مهارة باسم m1 بهذا الكود def run(): return 1", "install_skill"),
        ("ثبت مهارة من https://www.skills.sh/o/r/s باسم s1", "install_skill_from_url"),
        ("شغل المهارة m1 بالوسائط a تساوي 2", "run_skill"),
        ("أنشئ مشروع باسم app1 فيه ملف", "track_goal"),  # build → starter list
        ("خطط لمهمة طويلة من 3 مراحل", "track_goal"),  # plan → goal shell
        ("حدثني عن الطقس اليوم", None),  # no explicit intent → no forcing
    ]
    for qi, expected in _chain_cases:
        try:
            got = decide_forced_calls(qi)
        except Exception as e:
            failed += 1
            print(f"  ✗ decide raised on {qi[:40]!r}: {type(e).__name__}: {e}")
            continue
        first = got[0][0] if got else None
        if first == expected:
            passed += 1
            print(f"  ✓ decide: {qi[:38]!r} → {first}")
        else:
            failed += 1
            print(f"  ✗ decide: {qi[:38]!r} → {first} (expected {expected}, all={[n for n, _ in got]})")

    # Refusal quarantine helpers
    if (is_refusal_text("لا يمكنني الوصول إلى الملفات بسبب قيود الأمان")
            and is_refusal_text("I cannot directly access local files")
            and not is_refusal_text("Here is the file content you asked for")
            and isinstance(neutral_bridge(), str) and len(neutral_bridge()) > 0):
        passed += 1
        print("  ✓ refusal detection + neutral bridge")
    else:
        failed += 1
        print("  ✗ refusal helpers broken")

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()
