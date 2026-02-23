"""
GlassBox Core — State Machine Engine
======================================

This is the heart of GlassBox. The engine does exactly three things:
    1. Look up which agent function to call for the current state.
    2. Call that agent and read the "event" from its result.
    3. Look up the next state from the transitions table and log the transition.

That's it. The engine knows NOTHING about:
    - GitHub, LLMs, code editing, or any specific domain.
    - What agents actually do internally.
    - What use case is running.

It only knows:
    - A transitions dict: state → {event → next_state}
    - A pipeline dict: state → agent_function
    - How to log every transition (audit trail).

This separation is what makes GlassBox a platform:
    Swap the transitions and pipeline, and the same engine runs a completely
    different use case (code review, security audit, documentation generation).

Usage example:
    from glassbox.core.engine import Engine
    from glassbox.core.models import AgentContext
    from glassbox.use_cases.github_issues.states import TRANSITIONS
    from glassbox.use_cases.github_issues.pipeline import build_pipeline

    engine = Engine(
        transitions=TRANSITIONS,
        pipeline=build_pipeline(),
    )
    ctx = AgentContext(issue_number=42, repo="org/repo", state="received")
    final_state, audit_log = engine.run(ctx)

How the retry mechanism works:
    When an agent returns {"event": "failed"}, the transition table sends us to
    "retrying". The retry agent checks how many times we've retried (from ctx.history)
    and either returns {"event": "retry_ok"} (try again) or {"event": "exhausted"}.

    The special transition "_back" means "return to whatever state we were retrying."
    The engine resolves this by looking at ctx.history to find the last non-retry state.

How the author-interaction mechanism works:
    When we hit "awaiting_author", the engine PAUSES (returns that state).
    Later, when the author comments on the GitHub issue, a webhook fires.
    The webhook handler calls engine.run(ctx, state="awaiting_author") to resume.
    The conversationalist agent parses the author's intent and returns an event
    like {"event": "direction"}, which the engine resolves via "_route" to the
    appropriate next state based on the author's guidance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .models import AgentContext, AuditEntry
from .state import PAUSE_STATES, TERMINAL_STATES


# ---------------------------------------------------------------------------
# Type alias for agent functions.
#
# An agent is ANY callable that:
#   - Takes an AgentContext as its first argument
#   - Returns a dict with at least {"event": "some_event_name"}
#
# The "event" value is looked up in the transitions table to determine the
# next state. Agents can include additional keys in the dict for debugging,
# logging, or passing data to downstream agents via ctx.history.
#
# Examples of valid agent functions:
#   def classify(ctx: AgentContext, **kwargs) -> dict:
#       return {"event": "easy", "detail": "Single file typo fix"}
#
#   def generate_fix(ctx: AgentContext, **kwargs) -> dict:
#       return {"event": "fixed", "detail": "Applied 1 line edit", "fix": fix_obj}
# ---------------------------------------------------------------------------
AgentFn = Callable[..., dict[str, Any]]


class Engine:
    """
    The GlassBox state machine engine.

    Runs state transitions by calling agent functions and following transition rules.
    Logs every transition into an append-only audit trail.

    Constructor args:
        transitions  → Dict mapping state → {event → next_state}.
                        This comes from merging BASE_TRANSITIONS with use-case transitions.
                        Example: {"classifying": {"easy": "easy_localizing", "hard": "hard_researching"}}

        pipeline     → Dict mapping state → agent_function.
                        This tells the engine WHICH agent to call at WHICH state.
                        Example: {"classifying": classify, "easy_fixing": generate_fix}

        state_store  → Optional. Any object with a save(issue_number, state, audit) method.
                        Used to persist state between runs (e.g., for webhook-resumed flows).
                        If None, state only lives in memory (fine for single-run CLI usage).
    """

    def __init__(
        self,
        transitions: dict[str, dict[str, str]],
        pipeline: dict[str, AgentFn],
        state_store: Any | None = None,
    ):
        self.transitions = transitions
        self.pipeline = pipeline
        self.state_store = state_store

        # The audit log: an ordered list of every state transition.
        # This is the "glass" in GlassBox — full transparency of what happened.
        self.audit: list[AuditEntry] = []

    def step(self, state: str, ctx: AgentContext) -> tuple[str, dict]:
        """
        Execute ONE state transition.

        1. Look up the agent function for the current state.
        2. Call the agent function with the context.
        3. Read the "event" key from the agent's return value.
        4. Look up the next state from transitions[state][event].
        5. Append an AuditEntry to the audit log.
        6. Update the context with the new state and transition history.

        Returns:
            (next_state, agent_result) — The state we moved to, and the agent's full output.

        If no agent is registered for this state, returns the same state with
        an error result. This prevents the engine from crashing on misconfigured pipelines.
        """

        # Step 1: Find the agent function for this state.
        # If no agent is registered, we can't proceed — return an error event.
        agent_fn = self.pipeline.get(state)
        if not agent_fn:
            return state, {"event": "no_agent", "error": f"No agent registered for state '{state}'"}

        # Step 2: Call the agent. The agent does its work (LLM call, tool usage, etc.)
        # and returns a dict with at least {"event": "some_event_name"}.
        result = agent_fn(ctx)

        # Step 3: Extract the event from the agent's result.
        # Default to "done" if the agent forgot to include an event key.
        event = result.get("event", "done")

        # Step 4: Look up the next state from the transitions table.
        # If the event isn't in the transitions for this state, fail gracefully.
        # We pass the agent's result so _resolve_next_state can read "route_to"
        # for _route resolution (the result isn't in ctx.history yet at this point).
        next_state = self._resolve_next_state(state, event, ctx, result)

        # Step 5: Record this transition in the audit log.
        # This is automatic — agents don't have to opt in to auditing.
        self.audit.append(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            from_state=state,
            to_state=next_state,
            event=event,
            agent=getattr(agent_fn, "__name__", "unknown"),
            detail=result.get("detail", ""),
        ))

        # Step 6: Update context so downstream agents can see what happened.
        ctx.state = next_state
        ctx.history.append({"state": state, "event": event, "result": result})

        return next_state, result

    def run(self, ctx: AgentContext, state: str = "received") -> tuple[str, list[AuditEntry]]:
        """
        Run the state machine until it reaches a terminal or pause state.

        This is the main loop. It calls step() repeatedly until:
            - We reach a TERMINAL state (done, failed) → machine stops permanently.
            - We reach a PAUSE state (awaiting_author) → machine pauses for external input.

        After each step, if a state_store is configured, the current state and
        audit log are persisted. This allows the machine to resume later (e.g.,
        after a webhook fires when the author replies).

        Args:
            ctx   → The agent context. Modified in-place during execution.
            state → The state to start from. Defaults to "received" for new tasks.
                     Pass a different state to resume a paused machine.

        Returns:
            (final_state, audit_log) — The state we ended on, and the full audit trail.
        """

        # Initialize the context's state field to match where we're starting.
        ctx.state = state

        # The main loop: keep stepping until we can't continue.
        while state not in TERMINAL_STATES and state not in PAUSE_STATES:
            state, _ = self.step(state, ctx)

            # Persist after every step so we don't lose progress if the process crashes.
            if self.state_store:
                self.state_store.save(ctx.issue_number, state, self.audit)

        return state, self.audit

    def _resolve_next_state(
        self, current_state: str, event: str, ctx: AgentContext, current_result: dict | None = None,
    ) -> str:
        """
        Resolve the next state from the transitions table, handling special placeholders.

        Special values:
            "_back"  → Return to the state that triggered the retry.
                        Found by scanning ctx.history backwards for the last non-retry state.
            "_route" → Route based on external guidance (author intent, etc.).
                        The agent's result should include a "route_to" key with the target state.
                        If not present, falls back to "failed".

        Args:
            current_state  → The state we're currently in.
            event          → The event returned by the agent.
            ctx            → Agent context with history of previous steps.
            current_result → The current agent's result dict. Needed because _route reads
                              "route_to" from the result, but the result hasn't been appended
                              to ctx.history yet when this method is called.

        If the event isn't found in the transitions for the current state, returns "failed".
        This is a safety net — misconfigured transitions don't crash the engine.
        """

        next_state = self.transitions.get(current_state, {}).get(event, "failed")

        # Handle "_back": return to whatever state we were retrying from.
        # We scan history backwards to find the last state that wasn't "retrying".
        if next_state == "_back":
            for entry in reversed(ctx.history):
                if entry["state"] != "retrying":
                    return entry["state"]
            # If somehow there's no non-retry state in history, fail.
            return "failed"

        # Handle "_route": the agent tells us where to go via "route_to" in its result.
        # This is used by the conversationalist agent when parsing author intent.
        # We check the CURRENT result first (since it hasn't been added to history yet),
        # then fall back to the last history entry.
        if next_state == "_route":
            if current_result:
                route_to = current_result.get("route_to", "")
                if route_to:
                    return route_to
            if ctx.history:
                last_result = ctx.history[-1].get("result", {})
                route_to = last_result.get("route_to", "")
                if route_to:
                    return route_to
            return "failed"

        return next_state
