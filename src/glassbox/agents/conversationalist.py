"""
GlassBox Agent — Conversationalist
=====================================

CORE AGENT. Requires owner approval to modify.

Purpose:
    Parse human comments into structured intent so the engine can act on them.

    When the engine is in "awaiting_author" state and the author replies on GitHub,
    this agent reads the comment and determines:
        - What does the author WANT? (approve, redirect, constrain, abort, ask question)
        - What GUIDANCE did they provide? (specific instructions, constraints)
        - Where should the engine RESUME? (which state to route to)

Why this is a CORE agent:
    Human-in-the-loop is fundamental to the platform. Every use case that interacts
    with humans needs intent parsing. A code review use case needs to understand
    "approve this PR" vs "request changes." A security audit needs to understand
    "investigate this further" vs "mark as false positive." The intent vocabulary
    is universal.

How it works:
    1. Receives the author's comment text via ctx.config.
    2. Parses intent using keyword matching (fast, no LLM needed for simple cases).
    3. Extracts actionable guidance text (strips quotes, @mentions, noise).
    4. Determines the route_to state based on intent + context.
    5. Returns {"event": "direction", "route_to": "<state>"} for the engine.

    The engine's _resolve_next_state() method reads "route_to" from the result
    to handle the "_route" placeholder in transitions.

Ported from:
    Old conversation.py (304 lines). Kept only parse_intent() and extract_guidance().
    Removed: phase tags, comment fetching, bot comment parsing, phase detection.
    Those were specific to the old linear pipeline and are now handled by
    the state machine (phase = current state) and tools/github_client.py (fetching).
"""

from __future__ import annotations

import re
from typing import Any

from glassbox.core.models import AgentContext


# ---------------------------------------------------------------------------
# Intent vocabulary.
#
# These are the possible things a human can mean when they comment.
# The vocabulary is intentionally small — we want to be confident in our
# parsing, not cover every edge case. When in doubt, default to "redirect"
# (the author is giving guidance, let them steer).
#
# APPROVE   → "Looks good, ship it" → route to creating_pr
# REDIRECT  → "Try a different approach" → route back to the working state
# CONSTRAIN → "Don't touch file X" → retry with constraints
# ABORT     → "Stop working on this" → route to done (manual)
# QUESTION  → "Why did you do X?" → answer, don't re-run anything
# ---------------------------------------------------------------------------

INTENT_APPROVE = "approve"
INTENT_REDIRECT = "redirect"
INTENT_CONSTRAIN = "constrain"
INTENT_ABORT = "abort"
INTENT_QUESTION = "question"
INTENT_UNKNOWN = "unknown"

# Keyword → intent mapping. Checked in priority order (abort first, then approve, etc.)
# This ordering is important: "stop" should win over "looks good" if both appear.
_INTENT_KEYWORDS: dict[str, list[str]] = {
    INTENT_ABORT: ["stop", "abort", "cancel", "close this", "don't fix", "do not fix", "never mind"],
    INTENT_APPROVE: ["lgtm", "looks good", "ship it", "approve", "merge", "go ahead", "proceed"],
    INTENT_REDIRECT: ["try", "instead", "different approach", "what if", "how about", "change"],
    INTENT_QUESTION: ["why", "how does", "what does", "can you explain", "?"],
    INTENT_CONSTRAIN: ["don't touch", "do not modify", "leave", "keep", "must not", "only change"],
}


def run(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Parse an author's comment into structured intent and guidance.

    This is the agent entry point called by the engine when in "awaiting_author" state.

    Reads from ctx.config:
        author_comment → The raw text of the author's comment (str)

    Returns:
        {
            "event": "direction",
            "route_to": "<state_name>",  → Where the engine should go next
            "intent": "<intent>",        → The parsed intent (approve/redirect/etc.)
            "guidance": "<text>",        → Actionable guidance extracted from comment
            "constraints": [str],        → List of constraints the author specified
            "detail": "<summary>",       → Human-readable summary for audit log
        }
    """

    author_comment = ctx.config.get("author_comment", "")

    # Step 1: Parse the intent from the comment text.
    intent, constraints = _parse_intent(author_comment)

    # Step 2: Extract the actionable guidance (strip quotes, @mentions, noise).
    guidance = _extract_guidance(author_comment)

    # Step 3: Determine where the engine should route based on intent.
    route_to = _determine_route(intent, ctx)

    return {
        "event": "direction",
        "route_to": route_to,
        "intent": intent,
        "guidance": guidance,
        "constraints": constraints,
        "detail": f"Author intent: {intent}. Route to: {route_to}.",
    }


def _parse_intent(body: str) -> tuple[str, list[str]]:
    """
    Parse the author's comment into an intent and list of constraints.

    Checks keywords in priority order: abort > approve > redirect > question > constrain.
    This ordering ensures that destructive intents (abort) are caught before constructive
    ones (approve), preventing accidental approvals when the author says "stop, this
    looks good but we shouldn't merge yet."

    Returns:
        (intent, constraints) — The parsed intent and any constraints found.
    """

    body_lower = body.lower()

    # Extract constraints (negative directives) from all lines.
    constraints: list[str] = []
    for line in body.split("\n"):
        line_lower = line.strip().lower()
        for keyword in _INTENT_KEYWORDS[INTENT_CONSTRAIN]:
            if keyword in line_lower:
                constraints.append(line.strip())
                break

    # Check intent by keyword priority.
    for intent in [INTENT_ABORT, INTENT_APPROVE, INTENT_REDIRECT, INTENT_QUESTION]:
        for keyword in _INTENT_KEYWORDS[intent]:
            if keyword in body_lower:
                return intent, constraints

    # If constraints found but no other intent, it's a constrain.
    if constraints:
        return INTENT_CONSTRAIN, constraints

    # Default: treat as redirect (author is giving guidance).
    return INTENT_REDIRECT, constraints


def _extract_guidance(body: str) -> str:
    """
    Extract the actionable part of the author's comment.

    Strips:
        - Quoted lines (lines starting with >) — these reference bot output
        - @mentions — these are just addressing the bot
        - Empty lines

    Keeps:
        - The author's own words — their actual guidance/instructions.
    """

    lines = []
    for line in body.split("\n"):
        stripped = line.strip()

        # Skip quoted lines (the author quoting the bot's previous comment).
        if stripped.startswith(">"):
            continue

        # Skip empty lines.
        if not stripped:
            continue

        # Strip leading @mentions (e.g., "@glassbox-agent try a different approach").
        if stripped.startswith("@"):
            stripped = re.sub(r"^@\S+\s*", "", stripped).strip()
            if not stripped:
                continue

        lines.append(stripped)

    return "\n".join(lines)


def _determine_route(intent: str, ctx: AgentContext) -> str:
    """
    Given the parsed intent, determine which state the engine should route to.

    Routing rules:
        APPROVE   → "creating_pr" (skip remaining work, create the PR)
        ABORT     → "done" (stop working, mark as manually handled)
        QUESTION  → "" (empty = don't transition, just answer the question)
        REDIRECT  → Go back to the last working state (from history)
        CONSTRAIN → Same as redirect but with constraints in context
        UNKNOWN   → "failed" (safety fallback)

    For REDIRECT and CONSTRAIN, we look at ctx.history to find the last
    non-retry, non-asking state — that's where the author wants us to retry from.
    """

    if intent == INTENT_APPROVE:
        return "creating_pr"

    if intent == INTENT_ABORT:
        return "done"

    if intent == INTENT_QUESTION:
        # Questions don't trigger a state transition — they get answered inline.
        # For now, route to "failed" as a placeholder. In a future version,
        # this could route to a "answering" state that posts an explanation.
        return "failed"

    # For redirect/constrain: find the last meaningful state in history.
    if ctx.history:
        for entry in reversed(ctx.history):
            state = entry.get("state", "")
            # Skip meta-states — we want the last "real" working state.
            if state not in {"retrying", "asking_author", "awaiting_author", "received", "classifying"}:
                return state

    # If we can't determine a route, fail safely.
    return "failed"
