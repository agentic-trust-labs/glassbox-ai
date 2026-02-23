"""
GlassBox Agent — Researcher (Stub)
=====================================

Purpose:
    Produce a structured research report for HARD issues that can't be solved
    automatically. Instead of attempting a broken fix, the researcher analyzes
    the problem deeply and presents findings to the issue author.

Why research reports instead of fixes for hard issues:
    No agent solves hard problems autonomously (Devin's 2025 performance review
    confirms this). When an issue involves 5+ files, cross-boundary changes, or
    ambiguous requirements, attempting an automated fix leads to:
        - False confidence: the agent ships a broken PR that looks plausible
        - Wasted cycles: 3 retry loops that all fail the same way
        - Frustrated authors: they get a bad PR instead of useful analysis

    A research report is MORE valuable than a broken fix. It gives the author:
        - Root cause analysis
        - Hypotheses about what's wrong
        - Possible approaches with tradeoffs
        - Questions that need human judgment

    The author can then guide the agent ("try approach 2") or fix it manually
    with the research as a head start.

Current status: STUB
    This agent returns a placeholder research report. The full implementation
    (Phase 4) will:
        1. Analyze the codebase structure around the affected area.
        2. Identify dependencies, call chains, and data flows.
        3. Generate hypotheses about the root cause.
        4. Propose 2-3 approaches with tradeoffs.
        5. List questions for the author.

    For now, it returns a structured skeleton that the conversational loop
    can work with. The author comments, the conversationalist parses intent,
    and the engine routes accordingly (try_fix → med_planning, more_research →
    hard_researching, manual → done).
"""

from __future__ import annotations

from typing import Any

from glassbox.core.models import AgentContext


def run(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Generate a research report for a hard issue.

    Called by the engine when in "hard_researching" state.

    Reads from ctx.config:
        title  → Issue title (str)
        body   → Issue body (str)

    Returns:
        {"event": "ready", "detail": str, "report": str}
        The "ready" event transitions to "hard_report_posted" where the
        report is posted as a GitHub comment for the author to review.

    STUB: Returns a placeholder report. Full implementation in Phase 4.
    """

    title = ctx.config.get("title", "")
    body = ctx.config.get("body", "")

    # Stub report — structured skeleton for the conversational loop.
    report = _build_stub_report(ctx.issue_number, title, body)

    return {
        "event": "ready",
        "detail": f"Research report generated (stub) for issue #{ctx.issue_number}.",
        "report": report,
    }


def _build_stub_report(issue_number: int, title: str, body: str) -> str:
    """
    Build a placeholder research report.

    The report follows a structured format that the author can respond to:
        - Analysis: what we understand about the problem
        - Hypotheses: possible root causes
        - Approaches: ways to fix it, with tradeoffs
        - Questions: what we need the author to clarify

    The author's response is parsed by the conversationalist agent:
        "try approach 2" → engine routes to med_planning
        "investigate X more" → engine routes back to hard_researching
        "I'll handle it manually" → engine routes to done
    """

    return f"""## Research Report — Issue #{issue_number}

### Problem: {title}

### Analysis
(Stub) Full analysis will be generated in Phase 4. The issue description is:
{body[:500]}

### Hypotheses
1. (Stub) Root cause hypothesis 1
2. (Stub) Root cause hypothesis 2

### Possible Approaches
1. **Approach A**: (Stub) Description with tradeoffs
2. **Approach B**: (Stub) Description with tradeoffs

### Questions for Author
- Which approach do you prefer?
- Are there constraints I should know about?

---
*Reply to guide the next step:*
- *"try approach A"* → I'll create a step-by-step plan and start fixing
- *"investigate X more"* → I'll dig deeper into that area
- *"I'll handle it"* → I'll close this and you can fix manually"""
