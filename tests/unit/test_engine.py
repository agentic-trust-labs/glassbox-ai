"""
Core Engine Tests
===================

Pure Python tests for the state machine engine.
No LLM calls, no GitHub API, no subprocess — just state transitions.

These tests verify:
    1. Every base transition fires correctly.
    2. Every github_issues transition fires correctly.
    3. Terminal states halt the engine.
    4. Pause states halt the engine.
    5. "_back" retry routing returns to the correct source state.
    6. "_route" author guidance routing works.
    7. Audit trail records every step.
    8. Unknown events fall through to "failed".
    9. Missing agent gracefully returns error.
"""

import pytest

from glassbox.core.engine import Engine
from glassbox.core.models import AgentContext, AuditEntry
from glassbox.core.state import BASE_TRANSITIONS, TERMINAL_STATES, PAUSE_STATES, BaseState
from glassbox.use_cases.github_issues.states import TRANSITIONS


# ---------------------------------------------------------------------------
# Helpers: tiny agent factories for testing.
# Each returns a function that, when called, returns {"event": <event>}.
# ---------------------------------------------------------------------------

def agent_returning(event: str, **extras):
    """Create a mock agent that returns a fixed event."""
    def _agent(ctx, **kwargs):
        return {"event": event, **extras}
    _agent.__name__ = f"mock_{event}"
    return _agent


def make_ctx(**overrides):
    """Create a minimal AgentContext for testing."""
    defaults = {"issue_number": 1, "repo": "test/repo", "state": "received"}
    defaults.update(overrides)
    return AgentContext(**defaults)


# ===================================================================
# 1. Base state enum sanity checks
# ===================================================================

class TestBaseState:
    def test_base_state_count(self):
        """8 base states defined."""
        assert len(BaseState) == 8

    def test_terminal_states_are_subsets(self):
        """Terminal states must be valid BaseState values."""
        for s in TERMINAL_STATES:
            assert s in {e.value for e in BaseState}

    def test_pause_states_are_subsets(self):
        """Pause states must be valid BaseState values."""
        for s in PAUSE_STATES:
            assert s in {e.value for e in BaseState}

    def test_terminal_and_pause_disjoint(self):
        """Terminal and pause states must not overlap."""
        assert TERMINAL_STATES.isdisjoint(PAUSE_STATES)


# ===================================================================
# 2. Base transitions
# ===================================================================

class TestBaseTransitions:
    def test_received_classified(self):
        assert BASE_TRANSITIONS["received"]["classified"] == "classifying"

    def test_retrying_retry_ok(self):
        assert BASE_TRANSITIONS["retrying"]["retry_ok"] == "_back"

    def test_retrying_exhausted(self):
        assert BASE_TRANSITIONS["retrying"]["exhausted"] == "asking_author"

    def test_asking_author_posted(self):
        assert BASE_TRANSITIONS["asking_author"]["posted"] == "awaiting_author"

    def test_awaiting_author_direction(self):
        assert BASE_TRANSITIONS["awaiting_author"]["direction"] == "_route"

    def test_awaiting_author_timeout(self):
        assert BASE_TRANSITIONS["awaiting_author"]["timeout"] == "failed"

    def test_creating_pr_created(self):
        assert BASE_TRANSITIONS["creating_pr"]["created"] == "done"


# ===================================================================
# 3. GitHub Issues merged transitions
# ===================================================================

class TestGitHubIssuesTransitions:
    def test_inherits_base(self):
        """Base transitions are present in merged TRANSITIONS."""
        for state, events in BASE_TRANSITIONS.items():
            for event, target in events.items():
                assert TRANSITIONS[state][event] == target

    def test_classifying_easy(self):
        assert TRANSITIONS["classifying"]["easy"] == "easy_localizing"

    def test_classifying_medium(self):
        assert TRANSITIONS["classifying"]["medium"] == "med_planning"

    def test_classifying_hard(self):
        assert TRANSITIONS["classifying"]["hard"] == "hard_researching"

    def test_classifying_skip(self):
        assert TRANSITIONS["classifying"]["skip"] == "done"

    def test_easy_full_path(self):
        """Easy pipeline: localizing → fixing → testing → PR → done."""
        assert TRANSITIONS["easy_localizing"]["found"] == "easy_fixing"
        assert TRANSITIONS["easy_fixing"]["fixed"] == "easy_testing"
        assert TRANSITIONS["easy_testing"]["passed"] == "creating_pr"
        assert TRANSITIONS["creating_pr"]["created"] == "done"

    def test_medium_full_path(self):
        """Medium pipeline: planning → executing → testing → integrating → PR → done."""
        assert TRANSITIONS["med_planning"]["planned"] == "med_step_executing"
        assert TRANSITIONS["med_step_executing"]["done"] == "med_step_testing"
        assert TRANSITIONS["med_step_testing"]["last_step"] == "med_integrating"
        assert TRANSITIONS["med_integrating"]["passed"] == "creating_pr"

    def test_medium_loop(self):
        """Medium pipeline loops back for more steps."""
        assert TRANSITIONS["med_step_testing"]["more_steps"] == "med_step_executing"

    def test_medium_escalation(self):
        """Medium can escalate to hard."""
        assert TRANSITIONS["med_planning"]["too_hard"] == "hard_researching"

    def test_hard_full_path(self):
        """Hard pipeline: researching → report → author → action."""
        assert TRANSITIONS["hard_researching"]["ready"] == "hard_report_posted"
        assert TRANSITIONS["hard_report_posted"]["author_responds"] == "hard_author_guided"
        assert TRANSITIONS["hard_author_guided"]["try_fix"] == "med_planning"
        assert TRANSITIONS["hard_author_guided"]["more_research"] == "hard_researching"
        assert TRANSITIONS["hard_author_guided"]["manual"] == "done"

    def test_transition_count(self):
        """17 states with transitions defined."""
        assert len(TRANSITIONS) == 17


# ===================================================================
# 4. Engine.step() — single step execution
# ===================================================================

class TestEngineStep:
    def test_step_calls_agent_and_transitions(self):
        """step() calls the agent and moves to the correct next state."""
        pipeline = {"classifying": agent_returning("easy")}
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="classifying")

        next_state, result = engine.step("classifying", ctx)

        assert next_state == "easy_localizing"
        assert result["event"] == "easy"

    def test_step_records_audit(self):
        """step() appends an AuditEntry."""
        pipeline = {"classifying": agent_returning("easy")}
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="classifying")

        engine.step("classifying", ctx)

        assert len(engine.audit) == 1
        entry = engine.audit[0]
        assert entry.from_state == "classifying"
        assert entry.to_state == "easy_localizing"
        assert entry.event == "easy"
        assert entry.agent == "mock_easy"

    def test_step_updates_context(self):
        """step() updates ctx.state and ctx.history."""
        pipeline = {"classifying": agent_returning("easy")}
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="classifying")

        engine.step("classifying", ctx)

        assert ctx.state == "easy_localizing"
        assert len(ctx.history) == 1
        assert ctx.history[0]["state"] == "classifying"
        assert ctx.history[0]["event"] == "easy"

    def test_step_no_agent_returns_same_state(self):
        """step() with no agent registered returns same state with error."""
        engine = Engine(transitions=TRANSITIONS, pipeline={})
        ctx = make_ctx(state="classifying")

        next_state, result = engine.step("classifying", ctx)

        assert next_state == "classifying"
        assert "no_agent" in result.get("event", "")

    def test_step_unknown_event_goes_to_failed(self):
        """step() with an event not in transitions goes to 'failed'."""
        pipeline = {"classifying": agent_returning("bogus_event")}
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="classifying")

        next_state, result = engine.step("classifying", ctx)

        assert next_state == "failed"

    def test_step_detail_in_audit(self):
        """step() records the agent's 'detail' field in the audit entry."""
        pipeline = {"classifying": agent_returning("easy", detail="Typo fix detected")}
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="classifying")

        engine.step("classifying", ctx)

        assert engine.audit[0].detail == "Typo fix detected"


# ===================================================================
# 5. Engine.run() — full loop execution
# ===================================================================

class TestEngineRun:
    def test_run_terminal_done(self):
        """Engine stops at terminal 'done' state."""
        pipeline = {
            "classifying": agent_returning("skip"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        # received → classifying → done (skip)
        # But we need an agent for "received" too.
        pipeline["received"] = agent_returning("classified")

        final, audit = engine.run(ctx, state="received")

        assert final == "done"
        assert len(audit) == 2  # received→classifying, classifying→done

    def test_run_terminal_failed(self):
        """Engine stops at terminal 'failed' state."""
        pipeline = {
            "classifying": agent_returning("bogus"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="classifying")

        final, audit = engine.run(ctx, state="classifying")

        assert final == "failed"

    def test_run_pause_awaiting_author(self):
        """Engine pauses at 'awaiting_author' state."""
        pipeline = {
            "asking_author": agent_returning("posted"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="asking_author")

        final, audit = engine.run(ctx, state="asking_author")

        assert final == "awaiting_author"
        assert len(audit) == 1

    def test_run_easy_pipeline_full(self):
        """Full easy pipeline: received → classifying → localizing → fixing → testing → PR → done."""
        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("easy"),
            "easy_localizing": agent_returning("found"),
            "easy_fixing": agent_returning("fixed"),
            "easy_testing": agent_returning("passed"),
            "creating_pr": agent_returning("created"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        final, audit = engine.run(ctx, state="received")

        assert final == "done"
        states_visited = [e.from_state for e in audit] + [audit[-1].to_state]
        assert states_visited == [
            "received", "classifying", "easy_localizing",
            "easy_fixing", "easy_testing", "creating_pr", "done",
        ]

    def test_run_state_store_called(self):
        """If state_store is provided, save() is called after every step."""
        calls = []

        class MockStore:
            def save(self, issue_number, state, audit):
                calls.append((issue_number, state))

        pipeline = {
            "classifying": agent_returning("skip"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline, state_store=MockStore())
        ctx = make_ctx(state="classifying")

        engine.run(ctx, state="classifying")

        assert len(calls) == 1
        assert calls[0] == (1, "done")


# ===================================================================
# 6. _back resolution (retry routing)
# ===================================================================

class TestBackResolution:
    def test_back_returns_to_source_state(self):
        """_back resolves to the last non-retry state in history."""
        pipeline = {
            "retrying": agent_returning("retry_ok"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="retrying")
        # Simulate history: easy_fixing failed, went to retrying
        ctx.history = [
            {"state": "easy_fixing", "event": "failed", "result": {"event": "failed"}},
        ]

        next_state, result = engine.step("retrying", ctx)

        assert next_state == "easy_fixing"

    def test_back_skips_retry_states_in_history(self):
        """_back skips past any 'retrying' entries in history."""
        pipeline = {
            "retrying": agent_returning("retry_ok"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="retrying")
        # Simulate: easy_fixing → retrying → easy_fixing → retrying (second retry)
        ctx.history = [
            {"state": "easy_fixing", "event": "failed", "result": {}},
            {"state": "retrying", "event": "retry_ok", "result": {}},
            {"state": "easy_fixing", "event": "failed", "result": {}},
        ]

        next_state, _ = engine.step("retrying", ctx)

        assert next_state == "easy_fixing"

    def test_back_no_history_goes_to_failed(self):
        """_back with empty history falls through to 'failed'."""
        pipeline = {
            "retrying": agent_returning("retry_ok"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="retrying")
        ctx.history = []

        next_state, _ = engine.step("retrying", ctx)

        assert next_state == "failed"


# ===================================================================
# 7. _route resolution (author guidance)
# ===================================================================

class TestRouteResolution:
    def test_route_follows_route_to(self):
        """_route reads route_to from the agent result via history."""
        pipeline = {
            "awaiting_author": agent_returning("direction", route_to="easy_fixing"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="awaiting_author")

        next_state, _ = engine.step("awaiting_author", ctx)

        assert next_state == "easy_fixing"

    def test_route_no_route_to_goes_to_failed(self):
        """_route without route_to falls through to 'failed'."""
        pipeline = {
            "awaiting_author": agent_returning("direction"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="awaiting_author")

        next_state, _ = engine.step("awaiting_author", ctx)

        assert next_state == "failed"

    def test_route_timeout(self):
        """awaiting_author + timeout → failed (not _route)."""
        pipeline = {
            "awaiting_author": agent_returning("timeout"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="awaiting_author")

        next_state, _ = engine.step("awaiting_author", ctx)

        assert next_state == "failed"


# ===================================================================
# 8. Audit trail integrity
# ===================================================================

class TestAuditTrail:
    def test_audit_is_append_only(self):
        """Each step appends exactly one entry."""
        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("skip"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        engine.run(ctx, state="received")

        assert len(engine.audit) == 2

    def test_audit_entries_have_timestamps(self):
        """Every audit entry has a non-empty timestamp."""
        pipeline = {"classifying": agent_returning("easy")}
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx(state="classifying")

        engine.step("classifying", ctx)

        assert engine.audit[0].timestamp != ""

    def test_audit_chain_is_consistent(self):
        """Each entry's to_state matches the next entry's from_state."""
        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("easy"),
            "easy_localizing": agent_returning("found"),
            "easy_fixing": agent_returning("fixed"),
            "easy_testing": agent_returning("passed"),
            "creating_pr": agent_returning("created"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        engine.run(ctx, state="received")

        for i in range(len(engine.audit) - 1):
            assert engine.audit[i].to_state == engine.audit[i + 1].from_state
