"""
GlassBox Agent — Fix Generator
=================================

Purpose:
    Generate a code fix for a bug described in a GitHub issue.
    This is the agent that actually writes code — the "hands" of the system.

How it works:
    1. Receives the issue description, triage result (from classifier), source file
       contents, and template instructions via ctx.config.
    2. Builds a detailed prompt with all available context: issue, template, source
       files with line numbers, and any feedback from previous failed attempts.
    3. Calls the LLM to generate a fix as structured JSON (line edits + test code).
    4. Returns the fix for the engine to apply and test.

Why line-number editing:
    The old system used string replacement (str.replace) to apply fixes. This failed
    constantly: "String not found" errors when the LLM's replacement text didn't
    exactly match the source. Line-number editing is deterministic — "replace lines
    12-14 with this text" always works, regardless of whitespace or formatting.

    The LLM sees numbered source lines (e.g., "12: old_code") and specifies edits
    as {file, start_line, end_line, new_text}. The code_editor tool applies these
    edits precisely.

Fix output format:
    The LLM returns JSON with:
        edits     → List of {file, start_line, end_line, new_text} line edits
        test_code → Optional pytest function to verify the fix
        summary   → One-line commit message
        strategy  → Brief description of the approach taken

    These fields are defined in use_cases/github_issues/models.py (Fix, LineEdit)
    because they're specific to code-fixing use cases.

Ported from:
    Old JuniorDev.generate_fix() in glassbox_agent/agents/junior_dev.py.
    Stripped of class inheritance and BaseAgent dependency. Now a plain function.
    The prompt structure is preserved because it works well for easy fixes.
"""

from __future__ import annotations

import json
from typing import Any

from glassbox.core.models import AgentContext
from glassbox.tools.llm import call_llm


# ---------------------------------------------------------------------------
# The fix generation prompt.
#
# This prompt is critical for fix quality. Key design choices:
#
#   1. "Fix ONLY the bug described" — prevents the LLM from refactoring
#      or "improving" unrelated code, which causes test failures.
#
#   2. "Usually only 1 edit of 1 line is needed" — anchors the LLM toward
#      minimal changes. Most easy bugs are single-line fixes.
#
#   3. "Line numbers must match the numbered source" — forces the LLM to
#      reference the exact source we showed it, reducing hallucination.
#
#   4. "Include a test that verifies the fix" — the test is used by the
#      test_validator agent to confirm the fix works.
#
#   5. Feedback section — if this is a retry (previous fix was rejected),
#      the feedback from the reviewer/tester is included so the LLM can
#      learn from the failure and try a different approach.
# ---------------------------------------------------------------------------

FIX_PROMPT = """You are the GlassBox Fix Generator. Fix ONLY the bug described below.

Issue #{issue_number}: {title}
{body}

Template: {template_id}
Template instructions:
{template_instructions}

Source files (with line numbers):
{all_sources}

{feedback}

Return ONLY valid JSON:
{{
  "edits": [
    {{
      "file": "src/glassbox/example.py",
      "start_line": 12,
      "end_line": 12,
      "new_text": "    corrected_value = 0.85\\n"
    }}
  ],
  "test_code": "def test_fix():\\n    ...",
  "summary": "one-line commit message",
  "strategy": "brief approach description"
}}

CRITICAL RULES:
- Change ONLY the specific value/string the issue describes. Do NOT touch any other lines.
- The "file" MUST be the full relative path like "src/glassbox/orchestrator.py"
- The "new_text" MUST preserve the EXACT original indentation and trailing newline
- Usually only 1 edit of 1 line is needed. Do NOT rewrite functions or add code.
- Line numbers must match the numbered source shown above
- Include a test that verifies the fix"""


def run(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Generate a code fix for the current issue.

    Called by the engine when in "easy_fixing" (or similar) state.

    Reads from ctx.config:
        title               → Issue title (str)
        body                → Issue body (str)
        sources             → Dict of {file_path: file_contents} for all relevant files
        template_id         → Bug pattern template ID (from classifier)
        template_instructions → Instructions from the template YAML (str)
        model               → LLM model for code generation (default: "gpt-4o")
        temperature_code    → LLM temperature for code gen (default: 1.0, higher = more creative)
        feedback            → Feedback from previous attempt if retrying (str, empty on first try)

    Returns:
        {
            "event": "fixed",
            "detail": "<commit message>",
            "fix": dict with edits, test_code, summary, strategy
        }
        On failure to parse LLM response:
        {
            "event": "failed",
            "detail": "<error description>"
        }
    """

    title = ctx.config.get("title", "")
    body = ctx.config.get("body", "")
    sources = ctx.config.get("sources", {})
    template_id = ctx.config.get("template_id", "unknown")
    template_instructions = ctx.config.get("template_instructions", "(no template)")
    model = ctx.config.get("model", "gpt-4o")
    temperature = ctx.config.get("temperature_code", 1.0)
    feedback = ctx.config.get("feedback", "")

    # Format all source files with line numbers.
    all_sources_text = _format_all_sources(sources)

    # Build feedback section (only present on retries).
    feedback_section = f"\nPREVIOUS ATTEMPT FEEDBACK (address these issues):\n{feedback}" if feedback else ""

    # Build the prompt.
    prompt = FIX_PROMPT.format(
        issue_number=ctx.issue_number,
        title=title,
        body=body,
        template_id=template_id,
        template_instructions=template_instructions,
        all_sources=all_sources_text,
        feedback=feedback_section,
    )

    # Call the LLM.
    raw_response = call_llm(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        json_mode=True,
    )

    # Parse the response into a structured fix.
    fix = _parse_fix_response(raw_response)
    if fix is None:
        return {
            "event": "failed",
            "detail": f"Failed to parse fix response: {raw_response[:200]}",
        }

    return {
        "event": "fixed",
        "detail": fix.get("summary", "fix applied"),
        "fix": fix,
    }


def _format_all_sources(sources: dict[str, str]) -> str:
    """
    Format all source files with line numbers for the fix prompt.

    Each file gets a separator header and 1-indexed line numbers.
    This is the same format the classifier uses, ensuring consistency
    across agents when they reference line numbers.
    """

    if not sources:
        return "(no source files available)"

    parts = []
    for file_path, content in sources.items():
        numbered = "\n".join(
            f"{i + 1}: {line}" for i, line in enumerate(content.split("\n"))
        )
        parts.append(f"-- {file_path} --\n{numbered}")
    return "\n\n".join(parts)


def _parse_fix_response(raw: str) -> dict | None:
    """
    Parse the LLM's JSON response into a fix dict.

    Expected structure:
        {
            "edits": [{"file": str, "start_line": int, "end_line": int, "new_text": str}],
            "test_code": str,
            "summary": str,
            "strategy": str
        }

    Returns None if the response can't be parsed.
    Handles markdown code block wrappers (```json ... ```).
    """

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    # Validate minimum structure: must have at least one edit.
    if not data.get("edits"):
        return None

    return data
