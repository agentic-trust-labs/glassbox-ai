"""
GlassBox Use Case — GitHub Issues States
===========================================

This file defines the use-case-specific states and transitions for the
GitHub Issues use case. These EXTEND the base states from core/state.py.

How state extension works:
    The base states (RECEIVED, CLASSIFYING, RETRYING, etc.) handle the universal
    lifecycle that every use case shares. This file adds the states specific to
    fixing GitHub issues:

    EASY pipeline states:
        easy_localizing  → Finding which file(s) contain the bug
        easy_fixing      → Generating a code fix
        easy_testing     → Running tests to verify the fix

    MEDIUM pipeline states:
        med_planning       → Decomposing the issue into ordered steps
        med_step_executing → Executing one step of the plan
        med_step_testing   → Testing one step's changes
        med_checkpoint     → Pausing for human review (optional per step)
        med_integrating    → Running integration tests after all steps

    HARD pipeline states:
        hard_researching    → Analyzing the problem deeply
        hard_report_posted  → Research report posted, waiting for author guidance
        hard_author_guided  → Author has responded, deciding next action

Transition merging:
    TRANSITIONS = {**BASE_TRANSITIONS, ...use_case_transitions...}

    This merges base transitions (retrying, asking_author, etc.) with use-case
    transitions (classifying → easy/medium/hard routing, easy_fixing → easy_testing, etc.)

    The "classifying" state is OVERRIDDEN here to route into our specific pipelines.
    In BASE_TRANSITIONS, "classifying" isn't defined (it has no base transitions).
    Here, we define: classifying → {easy: easy_localizing, medium: med_planning, hard: hard_researching}

State flow diagrams:

    EASY:
        received → classifying → easy_localizing → easy_fixing → easy_testing → creating_pr → done
                                       ↓                ↓              ↓
                                  asking_author      retrying       retrying

    MEDIUM:
        received → classifying → med_planning → med_step_executing → med_step_testing
                                      ↑              ↓                    ↓
                                 med_checkpoint ← ← ←        more_steps: → med_step_executing
                                      ↓                      last_step:  → med_integrating → creating_pr → done
                                 med_planning (redirect)

    HARD:
        received → classifying → hard_researching → hard_report_posted → hard_author_guided
                                       ↑                                      ↓
                                       ← ← ← ← ← ← ← ← ← ← ← (more_research)
                                                                    ↓
                                                              try_fix → med_planning
                                                              manual  → done
"""

from glassbox.core.state import BASE_TRANSITIONS


# ---------------------------------------------------------------------------
# Use-case-specific state names.
#
# These are strings (not an Enum) because:
#   1. They need to merge seamlessly with BASE_TRANSITIONS keys (which are strings).
#   2. Adding a new state is just adding a string, not modifying an Enum class.
#   3. The engine only cares about string matching, not type safety on state names.
#
# We define them as a set for documentation and validation purposes.
# The engine doesn't read this set — it reads TRANSITIONS.
# ---------------------------------------------------------------------------

GITHUB_ISSUES_STATES: set[str] = {
    # Easy pipeline
    "easy_localizing",
    "easy_fixing",
    "easy_testing",
    # Medium pipeline
    "med_planning",
    "med_step_executing",
    "med_step_testing",
    "med_checkpoint",
    "med_integrating",
    # Hard pipeline
    "hard_researching",
    "hard_report_posted",
    "hard_author_guided",
}


# ---------------------------------------------------------------------------
# Merged transitions: base + GitHub Issues specific.
#
# The engine receives this TRANSITIONS dict and uses it to look up:
#     next_state = TRANSITIONS[current_state][event]
#
# Events are returned by agents in their result dict: {"event": "fixed"}.
# The event name determines which transition fires.
# ---------------------------------------------------------------------------

TRANSITIONS: dict[str, dict[str, str]] = {
    # Inherit all base transitions (retrying, asking_author, awaiting_author, creating_pr).
    **BASE_TRANSITIONS,

    # CLASSIFICATION: The classifier agent returns one of: easy, medium, hard, skip.
    # This is where the three pipelines diverge.
    "classifying": {
        "easy": "easy_localizing",       # Route to easy pipeline
        "medium": "med_planning",        # Route to medium pipeline
        "hard": "hard_researching",      # Route to hard pipeline
        "skip": "done",                  # Not a fixable issue (question, duplicate, etc.)
    },

    # --- EASY PIPELINE ---
    # Linear: localize → fix → test → PR. Fully automated, no human checkpoints.

    # Localizer found the file(s) → proceed to fix. Didn't find → ask the author.
    "easy_localizing": {
        "found": "easy_fixing",
        "not_found": "asking_author",
    },

    # Fix generated → test it. Fix generation failed → retry.
    "easy_fixing": {
        "fixed": "easy_testing",
        "failed": "retrying",
    },

    # Tests passed → create PR. Tests failed → retry the fix.
    "easy_testing": {
        "passed": "creating_pr",
        "failed": "retrying",
    },

    # --- MEDIUM PIPELINE ---
    # Multi-step: plan → execute step → test step → [checkpoint] → next step → integrate → PR.

    # Planner decomposed the issue into steps → start executing.
    # Planner decided it's actually too hard → escalate to hard pipeline.
    "med_planning": {
        "planned": "med_step_executing",
        "too_hard": "hard_researching",
    },

    # One step executed → test it. Step failed → retry.
    "med_step_executing": {
        "done": "med_step_testing",
        "failed": "retrying",
    },

    # Step tests: if more steps remain → execute next. Last step → integration test.
    # Step test failed → retry this step.
    "med_step_testing": {
        "more_steps": "med_step_executing",
        "last_step": "med_integrating",
        "failed": "retrying",
    },

    # Human checkpoint (optional): author reviews progress.
    # "ok" → continue with next step. "redirect" → re-plan based on feedback.
    "med_checkpoint": {
        "ok": "med_step_executing",
        "redirect": "med_planning",
    },

    # Integration test: all steps applied, run full test suite.
    # Passed → create PR. Failed → retry from the beginning.
    "med_integrating": {
        "passed": "creating_pr",
        "failed": "retrying",
    },

    # --- HARD PIPELINE ---
    # Research-first: analyze → report → wait for author → act on guidance.

    # Research complete → post the report.
    "hard_researching": {
        "ready": "hard_report_posted",
    },

    # Report posted, author responded → parse their guidance.
    "hard_report_posted": {
        "author_responds": "hard_author_guided",
    },

    # Author guidance: try to fix it → go to medium planning.
    # Want more research → go back to researching.
    # Will handle manually → mark as done.
    "hard_author_guided": {
        "try_fix": "med_planning",
        "more_research": "hard_researching",
        "manual": "done",
    },
}
