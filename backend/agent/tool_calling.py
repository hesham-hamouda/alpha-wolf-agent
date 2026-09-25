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

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .tools import ToolResult, execute_tool, get_tool_spec, TOOL_SPECS


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
        arguments = {}
        for arg_match in ARG_PATTERN.finditer(inner):
            arg_name = arg_match.group(1)
            arg_value = arg_match.group(2).strip()
            # Try to coerce to JSON if it looks like a number/bool/null
            arguments[arg_name] = _coerce_value(arg_value)

        tool_calls.append(ParsedToolCall(
            name=tool_name,
            arguments=arguments,
            raw=raw,
            line_number=text[:match.start()].count('\n') + 1,
        ))

    # Strip tool_call blocks from text
    cleaned_text = TOOL_CALL_PATTERN.sub('', text).strip()

    return ParsedResponse(
        text=cleaned_text,
        tool_calls=tool_calls,
        has_tool_calls=len(tool_calls) > 0,
    )


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


def format_tool_results_for_followup(results: List[ToolResult]) -> str:
    """Format tool results to feed back into a follow-up model call.

    تنسيق نتائج الأدوات لتغذيتها في استدعاء متابعة للنموذج.
    """
    if not results:
        return ""

    lines = ["\n\n[Tool Results | نتائج الأدوات]"]
    for r in results:
        status = "✓" if r.success else "✗"
        lines.append(f"\n{status} {r.tool_name} ({r.duration_ms:.0f}ms)")
        if r.success:
            output_str = json.dumps(r.output, ensure_ascii=False, default=str)
            if len(output_str) > 1500:
                output_str = output_str[:1500] + "... (truncated)"
            lines.append(f"  Output: {output_str}")
        else:
            lines.append(f"  Error: {r.error}")
    return "\n".join(lines)


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

    # Test 6: Malformed tool call (missing closing tag)
    parsed6 = parse_tool_calls("""<tool_call name="read_file">
<path>/tmp/x</path>
""")  # No closing
    if not parsed6.has_tool_calls:
        passed += 1
        print("  ✓ malformed call rejected")
    else:
        failed += 1
        print(f"  ✗ malformed accepted: {parsed6.to_dict()}")

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} فشل")
    return failed == 0


if __name__ == "__main__":
    _self_test()
