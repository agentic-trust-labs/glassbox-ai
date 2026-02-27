"""
GlassBox Agent — Planner
===========================

Purpose:
    Decompose a medium-difficulty issue into ordered steps that can be executed
    one at a time by the fix generator.

    Easy issues are single-step: localize → fix → test → PR. Done.
    Medium issues require PLANNING: the issue affects multiple files or requires
    a sequence of coordinated changes. The planner figures out the order.

How it works:
    1. Receives the issue description and localization results via ctx.config.
    2. Calls the LLM to decompose the issue into ordered steps.
    3. Each step specifies: what to do, which agent handles it, and whether
       a human checkpoint is needed before proceeding.
    4. Returns the plan for the engine to execute step-by-step.

Why checkpoints:
    Medium issues are where confidence drops. The planner can mark certain steps
    as "checkpoint: true", meaning the engine will pause and ask the author
    "Step 2 of 4 complete. Here's what I did. Should I continue?"

    This is optional per step, not per issue. The planner decides based on:
        - Is this step risky? (e.g., modifying a database schema)
        - Is the approach uncertain? (e.g., two valid ways to fix this)
        - Is this the first step of a novel pattern? (no past reflections match)

    Default: checkpoint after the first step if the issue is novel.

Step execution flow:
    Engine receives plan → executes step 1 (fix_generator) → tests step 1 →
    [checkpoint?] → executes step 2 → tests step 2 → ... → integration test → PR

When planner says "too_hard":
    If the planner determines the issue is actually harder than classified
    (e.g., affects 10+ files, requires architectural changes), it returns
    {"event": "too_hard"} and the engine escalates to the hard pipeline
    (research report + conversation).
"""

from __future__ import annotations

import json
from typing import Any

from glassbox.core.models import AgentContext
from glassbox.tools.llm import call_llm


# ---------------------------------------------------------------------------
# The planning prompt.
#
# The prompt asks the LLM to:
#   1. Analyze the issue and affected files.
#   2. Decompose into 2-6 ordered steps.
#   3. For each step, specify what to change, in which file, and whether
#      a checkpoint is needed.
#   4. If the issue is too complex for step-by-step execution, say so.
#
# The step limit (2-6) prevents the LLM from over-decomposing simple issues
# into 15 micro-steps. If it needs more than 6 steps, it's probably hard.
# ---------------------------------------------------------------------------

PLAN_PROMPT = """You are the GlassBox Planner. Decompose this issue into ordered steps.

Issue #{issue_number}: {title}
{body}

Affected files (from localization):
{affected_files}

INSTRUCTIONS:
1. Break the fix into 2-6 ordered steps. Each step should be one logical change.
2. For each step, specify the file(s) to modify and what to change.
3. Mark a step as checkpoint=true if it's risky or uncertain (the author will review).
4. If this needs more than 6 steps or requires architectural changes, return "too_hard".

Return ONLY valid JSON:
{{
  "steps": [
    {{
      "description": "Update the SQL query in db.py to use parameterized values",
      "files": ["src/db.py"],
      "agent": "fix_generator",
      "checkpoint": false
    }},
    {{
      "description": "Update the API endpoint to pass parameters correctly",
      "files": ["src/api.py"],
      "agent": "fix_generator",
      "checkpoint": true
    }}
  ],
  "reasoning": "Two-file change: database layer first, then API layer. Checkpoint after API change because it affects the public interface.",
  "too_hard": false
}}"""


def run(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Decompose an issue into executable steps.

    Called by the engine when in "med_planning" state.

    Reads from ctx.config:
        title          → Issue title (str)
        body           → Issue body (str)
        affected_files → Localization results: list of {file, relevance, reason} dicts
        model          → LLM model for planning (default: "gpt-4o")
        temperature    → LLM temperature (default: 0.5, balanced creativity)

    Returns:
        On success: {"event": "planned", "detail": str, "steps": list[dict], "reasoning": str}
        On too hard: {"event": "too_hard", "detail": str}
        On parse failure: {"event": "too_hard", "detail": str} (safe fallback: escalate)
    """

    title = ctx.config.get("title", "")
    body = ctx.config.get("body", "")
    affected_files = ctx.config.get("affected_files", [])
    model = ctx.config.get("model", "gpt-4o")
    temperature = ctx.config.get("temperature_plan", 0.5)

    # Format affected files for the prompt.
    affected_text = _format_affected_files(affected_files)

    prompt = PLAN_PROMPT.format(
        issue_number=ctx.issue_number,
        title=title,
        body=body,
        affected_files=affected_text,
    )

    raw_response = call_llm(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        json_mode=True,
    )

    # Parse the response.
    plan = _parse_plan_response(raw_response)
    if plan is None:
        # If we can't parse the plan, escalate to hard pipeline.
        return {
            "event": "too_hard",
            "detail": f"Failed to parse planner response: {raw_response[:200]}",
        }

    # Check if the planner said this is too hard.
    if plan.get("too_hard", False):
        return {
            "event": "too_hard",
            "detail": plan.get("reasoning", "Planner determined this is too complex for step-by-step."),
        }

    steps = plan.get("steps", [])
    if not steps:
        return {
            "event": "too_hard",
            "detail": "Planner returned zero steps.",
        }

    return {
        "event": "planned",
        "detail": f"Plan: {len(steps)} steps. {plan.get('reasoning', '')}",
        "steps": steps,
        "reasoning": plan.get("reasoning", ""),
    }


def _format_affected_files(files: list[dict]) -> str:
    """
    Format localization results for the planning prompt.

    Each entry has file path, relevance score, and reason for inclusion.
    This helps the planner understand which files need changes and why.
    """

    if not files:
        return "(no localization data available)"

    lines = []
    for f in files:
        path = f.get("file", f.get("path", "unknown"))
        relevance = f.get("relevance", "?")
        reason = f.get("reason", "")
        lines.append(f"  - {path} (relevance: {relevance}) — {reason}")
    return "\n".join(lines)


def _parse_plan_response(raw: str) -> dict | None:
    """
    Parse the LLM's JSON response into a plan dict.

    Expected structure:
        {
            "steps": [{"description": str, "files": [str], "agent": str, "checkpoint": bool}],
            "reasoning": str,
            "too_hard": bool
        }

    Returns None if unparseable. Handles markdown code block wrappers.
    """

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None
