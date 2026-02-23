"""
GlassBox Agent — Localizer
==============================

Purpose:
    Identify which files in the codebase are relevant to the issue being fixed.
    This narrows the search space for the fix generator so it doesn't have to
    reason about the entire codebase.

Why localization matters:
    An LLM has a limited context window. If you dump the entire codebase into the
    prompt, you waste tokens on irrelevant files and risk exceeding the context limit.
    Localization solves this by ranking files by relevance, so only the top N
    (typically 3-5) are included in the fix generator's prompt.

    Research backing: "Line-level localization > file-level" (arXiv:2411.10213).
    The Agentless approach (UIUC) uses hierarchical localization: directory → file →
    function → line. We start with file-level and can refine later.

How it works:
    1. Receives the issue description and a list of all source files via ctx.config.
    2. Calls the LLM to rank files by relevance to the issue.
    3. Returns a ranked list with relevance scores and explanations.

    The output feeds into:
        - fix_generator (which files to include in the fix prompt)
        - planner (which files are affected, for decomposition)

    For EASY issues, the classifier often already identifies the file (from the
    issue body or template). The localizer confirms or refines this.

    For MEDIUM issues, localization is critical — multiple files are affected,
    and the order in which they're fixed matters.

    For HARD issues, localization feeds into the research report.
"""

from __future__ import annotations

import json
from typing import Any

from glassbox.core.models import AgentContext
from glassbox.tools.llm import call_llm


# ---------------------------------------------------------------------------
# The localization prompt.
#
# The prompt shows the LLM the full file list of the repo (names only, not
# contents) and asks it to pick the most relevant files for the issue.
#
# This is a CHEAP LLM call (small prompt, small response) compared to
# fix generation. It runs before the expensive calls to keep costs down.
# ---------------------------------------------------------------------------

LOCALIZE_PROMPT = """You are the GlassBox Localizer. Identify which files are relevant to this issue.

Issue #{issue_number}: {title}
{body}

Repository files:
{file_list}

INSTRUCTIONS:
1. Rank the top 1-5 most relevant files for this issue.
2. For each file, explain WHY it's relevant.
3. Score relevance 0.0-1.0 (1.0 = definitely needs changes, 0.5 = might need changes).
4. If the issue mentions a specific file, that file should be ranked first.

Return ONLY valid JSON:
{{
  "files": [
    {{
      "path": "src/glassbox/config.py",
      "relevance": 0.95,
      "reason": "Issue mentions config value; this file defines it."
    }}
  ]
}}"""


def run(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Localize an issue to specific files.

    Called by the engine when in "easy_localizing" (or similar) state.

    Reads from ctx.config:
        title       → Issue title (str)
        body        → Issue body (str)
        file_list   → List of all source file paths in the repo (list[str])
                       Typically from tools/file_reader.list_files()
        model       → LLM model for localization (default: "gpt-4o-mini", cheap is fine)
        temperature → LLM temperature (default: 0.3, deterministic)

    Returns:
        On files found:
            {"event": "found", "detail": str, "files": list[dict]}
            Each file dict has: path, relevance (float), reason (str)
        On no files found:
            {"event": "not_found", "detail": str}
            This triggers the engine to ask the author for guidance.
    """

    title = ctx.config.get("title", "")
    body = ctx.config.get("body", "")
    file_list = ctx.config.get("file_list", [])
    model = ctx.config.get("model_localize", "gpt-4o-mini")
    temperature = ctx.config.get("temperature_localize", 0.3)

    # Format the file list as a simple newline-separated list.
    # We only show file names (not contents) to keep the prompt small and cheap.
    file_list_text = "\n".join(f"  {f}" for f in file_list) if file_list else "(no files found)"

    prompt = LOCALIZE_PROMPT.format(
        issue_number=ctx.issue_number,
        title=title,
        body=body,
        file_list=file_list_text,
    )

    raw_response = call_llm(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        json_mode=True,
    )

    # Parse the response.
    files = _parse_localization(raw_response)

    if not files:
        return {
            "event": "not_found",
            "detail": "Localizer could not identify relevant files.",
        }

    # Format detail for the audit log.
    file_summary = ", ".join(f"{f['path']} ({f['relevance']:.1f})" for f in files[:3])

    return {
        "event": "found",
        "detail": f"Localized to {len(files)} files: {file_summary}",
        "files": files,
    }


def _parse_localization(raw: str) -> list[dict]:
    """
    Parse the LLM's JSON response into a list of file entries.

    Each entry has: path (str), relevance (float), reason (str).
    Returns empty list if unparseable.
    """

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    files = data.get("files", [])

    # Validate and normalize each entry.
    result = []
    for f in files:
        if not f.get("path"):
            continue
        result.append({
            "path": f["path"],
            "relevance": float(f.get("relevance", 0.5)),
            "reason": f.get("reason", ""),
        })

    # Sort by relevance descending (most relevant first).
    result.sort(key=lambda x: x["relevance"], reverse=True)
    return result
