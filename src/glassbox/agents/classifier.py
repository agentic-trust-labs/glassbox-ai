"""
GlassBox Agent — Classifier
==============================

CORE AGENT. Requires owner approval to modify.

Purpose:
    Determine the difficulty of an incoming task (easy, medium, or hard) so the
    engine can route it to the appropriate pipeline.

    This is the FIRST agent that runs for every task. Its output (TriageResult)
    directly controls which pipeline executes. A wrong classification means:
        - Easy classified as hard → wasted effort (research report for a typo fix)
        - Hard classified as easy → broken PR, wasted retries, frustrated author

Classification criteria (from difficulty analysis):
    EASY (fully automated):
        - Single file affected
        - Clear bug pattern (typo, wrong value, wrong name, swapped args)
        - Confidence >= 0.85
        - Matches a known template

    MEDIUM (orchestrated multi-step):
        - 2-5 files affected
        - Requires planning/decomposition
        - May need human checkpoint
        - Confidence 0.5-0.85

    HARD (research report + conversation):
        - 5+ files affected OR cross-boundary changes
        - Ambiguous requirements
        - Confidence < 0.5
        - No clear fix path

How it works:
    1. Receives the issue title, body, and source file contents via ctx.config.
    2. Calls the LLM with a classification prompt.
    3. Parses the LLM response into a TriageResult.
    4. Returns {"event": "<difficulty>"} so the engine routes to the right pipeline.

Ported from:
    Old Manager.classify() in glassbox_agent/agents/manager.py.
    Stripped of class inheritance, template loading, and memory formatting.
    Those responsibilities moved to the pipeline (template loading) and
    memory store (reflection formatting).
"""

from __future__ import annotations

import json
from typing import Any

from glassbox.core.models import AgentContext, TriageResult
from glassbox.tools.llm import call_llm


# ---------------------------------------------------------------------------
# The classification prompt.
#
# This is the most important prompt in the system because it determines
# which pipeline runs. A misclassification cascades into everything else.
#
# The prompt asks the LLM to:
#   1. Assess difficulty based on files affected, boundary crossings, clarity.
#   2. Pick a template_id if a known bug pattern matches.
#   3. Rate confidence 0.0-1.0.
#   4. Explain reasoning (for the audit log — transparency!).
#
# The response MUST be valid JSON so we can parse it reliably.
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """You are the GlassBox Classifier. Determine the difficulty of this GitHub issue.

Issue #{issue_number}: {title}
{body}

Source file contents (if available):
{sources}

Available templates (known bug patterns): {template_list}

CLASSIFICATION CRITERIA:
- EASY: Single file, clear pattern (typo, wrong value, wrong name, swapped args), confidence >= 0.85
- MEDIUM: 2-5 files, needs planning, may need human checkpoint, confidence 0.5-0.85
- HARD: 5+ files OR cross-boundary, ambiguous requirements, confidence < 0.5

INSTRUCTIONS:
1. Assess how many files are likely affected.
2. Check if this matches a known template.
3. Rate your confidence 0.0-1.0.
4. If this is a question, duplicate, or feature request (not a bug/improvement), set difficulty to "skip".

{past_reflections}

Return ONLY valid JSON:
{{
  "difficulty": "easy|medium|hard|skip",
  "confidence": 0.95,
  "template_id": "typo_fix",
  "reasoning": "Single file typo in config value, high confidence, matches typo_fix template."
}}"""


def run(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Classify an issue by difficulty. This is the agent entry point.

    The engine calls this function when the state machine is in the "classifying" state.

    Reads from ctx.config:
        title          → Issue title (str)
        body           → Issue body (str)
        sources        → Dict of {file_path: file_contents} for relevant source files
        template_list  → Comma-separated list of available template IDs
        past_reflections → Formatted string of past failure reflections (from memory store)
        model          → LLM model to use for classification (default: gpt-4o-mini)
        temperature    → LLM temperature (default: 0.3 for deterministic classification)

    Returns:
        {"event": "<difficulty>", "detail": "<reasoning>", "triage": TriageResult}
        The "event" is one of: "easy", "medium", "hard", "skip"
        The engine uses this event to transition to the appropriate pipeline.
    """

    # Extract issue details from the context config.
    # These are populated by the use case's pipeline before calling the engine.
    title = ctx.config.get("title", "")
    body = ctx.config.get("body", "")
    sources = ctx.config.get("sources", {})
    template_list = ctx.config.get("template_list", "")
    past_reflections = ctx.config.get("past_reflections", "")
    model = ctx.config.get("model_classify", "gpt-4o-mini")
    temperature = ctx.config.get("temperature_classify", 0.3)

    # Format source file contents with line numbers for the LLM.
    # Line numbers help the LLM reference specific lines in its reasoning.
    source_text = _format_sources(sources)

    # Build the classification prompt with all available context.
    prompt = CLASSIFY_PROMPT.format(
        issue_number=ctx.issue_number,
        title=title,
        body=body,
        sources=source_text,
        template_list=template_list or "(none)",
        past_reflections=past_reflections,
    )

    # Call the LLM and parse the JSON response.
    raw_response = call_llm(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        json_mode=True,
    )

    # Parse the LLM's JSON response into a TriageResult.
    triage = _parse_response(raw_response)

    # Return the event for the engine's transition table.
    # The event name IS the difficulty: "easy", "medium", "hard", or "skip".
    # The engine looks up transitions["classifying"]["easy"] → "easy_localizing" (or similar).
    return {
        "event": triage.difficulty,
        "detail": triage.reasoning,
        "triage": triage,
    }


def _format_sources(sources: dict[str, str]) -> str:
    """
    Format source files with line numbers for inclusion in the LLM prompt.

    Each file gets a header with its path, and each line is prefixed with its
    line number. This helps the LLM reference specific lines accurately.

    Example output:
        --- src/glassbox/config.py ---
        1: # Config module.
        2: DEFAULT_THRESHOLD = 0.85
        3: DEFAULT_MODEL = "gpt-4o"
    """

    if not sources:
        return "(no source files available)"

    parts = []
    for file_path, content in sources.items():
        lines = content.split("\n")
        numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
        parts.append(f"--- {file_path} ---\n{numbered}")
    return "\n\n".join(parts)


def _parse_response(raw: str) -> TriageResult:
    """
    Parse the LLM's JSON response into a TriageResult dataclass.

    Handles common LLM quirks:
        - Response wrapped in markdown code blocks (```json ... ```)
        - Missing fields (filled with defaults)
        - Invalid JSON (returns a hard/low-confidence result as a safe fallback)

    The fallback to "hard" is intentional: if we can't even parse the classification,
    the issue is probably complex. Better to escalate than to attempt an easy fix
    on something we don't understand.
    """

    # Strip markdown code block wrappers if present.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove opening ```json or ``` and closing ```
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # If we can't parse the response, assume the issue is hard.
        # This is a SAFE fallback: hard issues get human review.
        return TriageResult(
            difficulty="hard",
            confidence=0.0,
            reasoning=f"Failed to parse classifier response: {raw[:200]}",
        )

    return TriageResult(
        difficulty=data.get("difficulty", "hard"),
        confidence=float(data.get("confidence", 0.0)),
        template_id=data.get("template_id", ""),
        reasoning=data.get("reasoning", ""),
    )
