"""
GlassBox Core — Data Contracts
================================

This file defines the typed data structures that flow between the engine and agents.

Why typed contracts?
    Without these, agents pass raw dicts around. A typo in a key name ("confidnce"
    instead of "confidence") causes a silent bug that only surfaces at runtime.
    Typed dataclasses catch these at development time via IDE autocomplete and linting.

What belongs here vs elsewhere:
    CORE models (here):
        AgentContext  → Every agent receives this. It's the agent's view of the world.
        TriageResult  → The classifier's output. The engine reads this to pick a pipeline.
        AuditEntry    → One row in the audit log. The "glass" in GlassBox.

    USE-CASE models (in use_cases/<name>/models.py):
        Fix, LineEdit, TestResult, Step, PlanResult, ReviewResult, EdgeCase, etc.
        These are specific to code-fixing use cases. A security-audit use case
        wouldn't have a Fix or LineEdit — it would have Finding or Vulnerability.

Design decisions:
    - We use dataclasses (stdlib) instead of Pydantic (external dep) for core models.
      Core has ZERO external dependencies. This keeps the kernel pure Python.
    - Use-case models CAN use Pydantic if they want — that's their choice.
    - All fields have type hints for IDE support and documentation.
    - Default values are provided where sensible to minimize boilerplate in callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """
    The world as an agent sees it. Passed to every agent function call.

    This is the ONLY argument that the engine provides to agents. Everything an agent
    needs to do its job should be accessible through this context object.

    Fields:
        issue_number → Which issue/task we're working on. Unique identifier.
        repo         → Repository in "owner/name" format (e.g., "agentic-trust-labs/glassbox-ai").
        state        → Current state in the state machine (e.g., "easy_fixing").
                        The agent can use this to adapt its behavior based on where we are.
        history      → List of previous state transitions and their results.
                        Each entry is a dict: {"state": str, "event": str, "result": dict}.
                        Agents can inspect this to avoid repeating failed strategies.
        config       → Use-case-specific settings (model names, temperatures, template dirs, etc.).
                        This comes from use_cases/<name>/settings.py, not from core.

    Why not just pass individual arguments?
        Because different agents need different subsets of information. The context
        object gives them access to everything without requiring the engine to know
        what each specific agent needs. It's the decoupling mechanism.
    """

    issue_number: int
    repo: str
    state: str
    history: list[dict] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class TriageResult:
    """
    Output of the Classifier agent. The engine reads this to route into the right pipeline.

    This is a CORE model because the engine's routing logic depends on it.
    The classifier returns this, and the engine checks `difficulty` to decide:
        "easy"   → route to easy_localizing (fully automated)
        "medium" → route to med_planning (orchestrated multi-step)
        "hard"   → route to hard_researching (research report + conversation)

    Fields:
        difficulty   → One of "easy", "medium", "hard". Determines the pipeline.
        confidence   → 0.0 to 1.0. How confident the classifier is.
                        If confidence < 0.7, the engine might escalate to a harder pipeline.
        template_id  → Which bug pattern template to use (e.g., "typo_fix", "wrong_value").
                        Empty string if no template matches.
        reasoning    → Human-readable explanation of why this difficulty was chosen.
                        This gets included in the audit log for transparency.
    """

    difficulty: str  # "easy", "medium", or "hard"
    confidence: float  # 0.0 to 1.0
    template_id: str = ""
    reasoning: str = ""


@dataclass
class AuditEntry:
    """
    One row in the audit log. This is the "glass" in GlassBox.

    Every time the engine transitions from one state to another, it creates one
    AuditEntry. The complete list of entries for an issue is the full story of
    what happened: which states were visited, what events triggered transitions,
    which agents ran, and what they decided.

    This log is:
        - Append-only: entries are never modified or deleted.
        - Automatic: the engine creates them; agents don't have to opt in.
        - Transparent: the log can be posted as a GitHub comment, stored in a DB,
          or included in compliance reports.

    Fields:
        timestamp   → ISO 8601 UTC timestamp of when this transition happened.
        from_state  → The state we were in before the transition.
        to_state    → The state we moved to after the transition.
        event       → The event that triggered the transition (e.g., "fixed", "failed").
        agent       → Name of the agent function that produced this event.
                       Empty string if no agent ran (e.g., timeout transitions).
        detail      → Optional human-readable detail about what the agent did.
                       Useful for debugging and for the author to understand progress.
    """

    timestamp: str
    from_state: str
    to_state: str
    event: str
    agent: str = ""
    detail: str = ""
