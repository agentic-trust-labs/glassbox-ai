"""
GlassBox Core — State Definitions
===================================

This file defines the BASE states and transitions that every use case inherits.

Why base states?
    Every use case — whether it's fixing GitHub issues, reviewing PRs, or auditing
    security — goes through the same lifecycle: something arrives, gets classified,
    might need retrying, might need human input, and eventually succeeds or fails.
    These universal lifecycle states live here in core.

    Use-case-specific states (like EASY_FIXING or MED_PLANNING) do NOT live here.
    They live in their respective use_cases/<name>/states.py files.

How transitions work:
    The TRANSITIONS dict maps: state → {event → next_state}

    When an agent runs at a given state, it returns a dict with an "event" key.
    The engine looks up: TRANSITIONS[current_state][event] → next_state.

    Two special next_state values:
        "_back"   → Return to whatever state triggered the retry (engine resolves this)
        "_route"  → Route based on the author's parsed intent (engine resolves this)

    These placeholders exist because the actual target depends on runtime context
    (which state failed, what the author said), not on static configuration.

State categories:
    TERMINAL states → The machine stops permanently: done or failed.
    PAUSE states    → The machine pauses, waiting for external input (e.g., author reply).
                      A webhook or cron job resumes the machine later by calling engine.run()
                      again with the new state.
    ACTIVE states   → The machine keeps stepping automatically.
"""

from __future__ import annotations

from enum import Enum


class BaseState(str, Enum):
    """
    Platform-level states that any use case needs.

    These 8 states represent the universal lifecycle of any task:
        RECEIVED         → A new task has arrived (issue labeled, webhook fired, etc.)
        CLASSIFYING      → Determining the difficulty/type of the task
        RETRYING         → A previous step failed; attempting again with a different strategy
        ASKING_AUTHOR    → The agent needs human guidance; posting a question
        AWAITING_AUTHOR  → Question posted; paused until the human responds
        CREATING_PR      → All work done; packaging the result (PR, report, etc.)
        DONE             → Terminal success state
        FAILED           → Terminal failure state (exhausted retries, author gave up, etc.)

    Use cases extend this with their own states. For example, the GitHub Issues use case
    adds EASY_LOCALIZING, EASY_FIXING, MED_PLANNING, HARD_RESEARCHING, etc.
    Those use-case states are defined in use_cases/github_issues/states.py.
    """

    RECEIVED = "received"
    CLASSIFYING = "classifying"
    RETRYING = "retrying"
    ASKING_AUTHOR = "asking_author"
    AWAITING_AUTHOR = "awaiting_author"
    CREATING_PR = "creating_pr"
    DONE = "done"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Base transitions: how the universal lifecycle states connect to each other.
#
# Use cases merge their own transitions ON TOP of these base transitions.
# For example, github_issues/states.py does:
#     TRANSITIONS = {**BASE_TRANSITIONS, "classifying": {"easy": "easy_localizing", ...}}
#
# This means the use case OVERRIDES "classifying" to route into its own states,
# but inherits "retrying", "asking_author", etc. unchanged.
# ---------------------------------------------------------------------------

BASE_TRANSITIONS: dict[str, dict[str, str]] = {
    # When a task is received, the classifier determines difficulty.
    # The classifier agent returns {"event": "classified"} to trigger this.
    "received": {"classified": "classifying"},

    # When retrying a failed step:
    #   "retry_ok"  → go back to the state that failed (engine resolves "_back")
    #   "exhausted" → all retries used up, ask the human for help
    "retrying": {"retry_ok": "_back", "exhausted": "asking_author"},

    # When asking the author for guidance:
    #   "posted" → the question has been posted, now we wait
    "asking_author": {"posted": "awaiting_author"},

    # When waiting for the author's response:
    #   "direction" → the author responded with guidance (engine resolves "_route")
    #   "timeout"   → no response after 48h, mark as failed
    "awaiting_author": {"direction": "_route", "timeout": "failed"},

    # When creating the final output (PR, report, etc.):
    #   "created" → success! we're done.
    "creating_pr": {"created": "done"},
}


# ---------------------------------------------------------------------------
# State categories used by the engine to decide whether to keep looping.
# ---------------------------------------------------------------------------

# Terminal states: the machine stops permanently. No more transitions possible.
TERMINAL_STATES: set[str] = {"done", "failed"}

# Pause states: the machine stops temporarily. An external event (webhook, cron)
# resumes it later by calling engine.run() with the new state.
PAUSE_STATES: set[str] = {"awaiting_author"}
