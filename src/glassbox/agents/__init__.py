"""
GlassBox Agents — Shared Agent Pool
=====================================

All agents live here in ONE place. No duplication.

Use cases BORROW agents by name. They don't own agents — they declare which ones
they need in their pipeline.py file, and the engine calls them.

Governance:
    CORE_AGENTS → These agents are essential for any use case. Changing them requires
                   owner approval (enforced via CODEOWNERS). They are:
                       classifier        → Routes tasks by difficulty (every use case needs this)
                       reviewer           → Adversarial review using a different model (trust guarantee)
                       conversationalist  → Parses human intent from comments (human-in-the-loop)

    All other agents are OPEN for contribution. Anyone can add a new agent file
    to this directory and register it in a use case's pipeline.

How to add a new agent:
    1. Create a new file: agents/my_agent.py
    2. Define a function: def run(ctx: AgentContext, **kwargs) -> dict
       The function MUST return a dict with at least {"event": "some_event_name"}.
    3. Register it in your use case's pipeline.py.
    That's it. No base class to inherit, no registry to update, no core changes.

Agent contract:
    Every agent is a plain Python function (not a class) with this signature:
        def run(ctx: AgentContext, **kwargs) -> dict[str, Any]

    The returned dict MUST contain:
        "event" → str: The event name that triggers the next state transition.
    It CAN also contain:
        "detail" → str: Human-readable description for the audit log.
        Any other keys → Passed along in ctx.history for downstream agents to read.

Discovery:
    The discover() function below lets pipelines load agents by name at runtime.
    This is used by use_cases/<name>/pipeline.py to build the state→agent mapping.
"""

from __future__ import annotations

from typing import Any, Callable


# ---------------------------------------------------------------------------
# Core agents: these require owner approval to modify.
# This set is the governance mechanism. It replaces the need for separate
# core/ and contrib/ subdirectories — one flat folder, one Python set.
# ---------------------------------------------------------------------------
CORE_AGENTS: set[str] = {"classifier", "reviewer", "conversationalist"}


def discover(name: str) -> Callable[..., dict[str, Any]]:
    """
    Import an agent by name and return its run() function.

    This is the agent discovery mechanism. Pipeline files use this to map
    state names to agent functions without hardcoding imports.

    Example:
        from glassbox.agents import discover
        pipeline = {
            "classifying": discover("classifier"),
            "easy_fixing": discover("fix_generator"),
        }

    How it works:
        discover("classifier") → imports glassbox.agents.classifier → returns classifier.run

    Raises:
        ImportError: If no agent module with that name exists.
        AttributeError: If the module doesn't have a run() function.
    """

    import importlib
    module = importlib.import_module(f".{name}", __package__)
    return module.run
