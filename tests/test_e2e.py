"""
E2E Smoke Tests
==================

End-to-end tests that run a full pipeline through the engine with mocked agents.
These verify that the engine, transitions, and pipeline wiring all work together.

No LLM calls, no GitHub API — agents are replaced with simple mock functions
that return the expected events for a happy-path run.
"""

import pytest

from glassbox.core.engine import Engine
from glassbox.core.models import AgentContext
from glassbox.use_cases.github_issues.states import TRANSITIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def agent_returning(event: str, **extras):
    """Create a mock agent that returns a fixed event."""
    def _agent(ctx, **kwargs):
        return {"event": event, **extras}
    _agent.__name__ = f"mock_{event}"
    return _agent


def make_ctx(**overrides):
    defaults = {"issue_number": 1, "repo": "test/repo", "state": "received", "config": {"max_retries": 2}}
    defaults.update(overrides)
    return AgentContext(**defaults)


# ===================================================================
# 1. Easy pipeline E2E
# ===================================================================

class TestEasyE2E:
    def test_easy_happy_path(self):
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

        final, audit = engine.run(ctx)

        assert final == "done"
        assert len(audit) == 6
        # Verify the exact state sequence.
        expected = [
            ("received", "classifying"),
            ("classifying", "easy_localizing"),
            ("easy_localizing", "easy_fixing"),
            ("easy_fixing", "easy_testing"),
            ("easy_testing", "creating_pr"),
            ("creating_pr", "done"),
        ]
        for i, (from_s, to_s) in enumerate(expected):
            assert audit[i].from_state == from_s
            assert audit[i].to_state == to_s

    def test_easy_with_one_retry(self):
        """Easy pipeline with one test failure and successful retry."""
        call_count = {"easy_testing": 0}

        def flaky_test(ctx, **kwargs):
            call_count["easy_testing"] += 1
            if call_count["easy_testing"] == 1:
                return {"event": "failed", "detail": "Test assertion error"}
            return {"event": "passed"}

        def retry_agent(ctx, **kwargs):
            return {"event": "retry_ok"}

        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("easy"),
            "easy_localizing": agent_returning("found"),
            "easy_fixing": agent_returning("fixed"),
            "easy_testing": flaky_test,
            "retrying": retry_agent,
            "creating_pr": agent_returning("created"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        final, audit = engine.run(ctx)

        assert final == "done"
        # Should have extra steps: easy_testing(fail) → retrying → easy_testing(pass)
        states_from = [e.from_state for e in audit]
        assert "retrying" in states_from
        assert call_count["easy_testing"] == 2

    def test_easy_skip_goes_to_done(self):
        """Classifier returns 'skip' → directly to done."""
        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("skip"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        final, audit = engine.run(ctx)

        assert final == "done"
        assert len(audit) == 2


# ===================================================================
# 2. Medium pipeline E2E
# ===================================================================

class TestMediumE2E:
    def test_medium_two_steps(self):
        """Medium pipeline with 2 steps: plan → execute → test → execute → test → integrate → PR → done."""
        step_count = {"execute": 0, "test": 0}

        def step_executor(ctx, **kwargs):
            step_count["execute"] += 1
            return {"event": "done"}

        def step_tester(ctx, **kwargs):
            step_count["test"] += 1
            if step_count["test"] == 1:
                return {"event": "more_steps"}
            return {"event": "last_step"}

        def integrator(ctx, **kwargs):
            return {"event": "passed"}

        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("medium"),
            "med_planning": agent_returning("planned"),
            "med_step_executing": step_executor,
            "med_step_testing": step_tester,
            "med_integrating": integrator,
            "creating_pr": agent_returning("created"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        final, audit = engine.run(ctx)

        assert final == "done"
        assert step_count["execute"] == 2
        assert step_count["test"] == 2

    def test_medium_escalates_to_hard(self):
        """Medium planning decides it's too hard → escalates to hard pipeline."""
        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("medium"),
            "med_planning": agent_returning("too_hard"),
            "hard_researching": agent_returning("ready"),
            # hard_report_posted is a pause-like state (no agent, waits for author)
            # But it's not in PAUSE_STATES, so we need an agent.
            "hard_report_posted": agent_returning("author_responds"),
            "hard_author_guided": agent_returning("manual"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        final, audit = engine.run(ctx)

        assert final == "done"
        states_from = [e.from_state for e in audit]
        assert "med_planning" in states_from
        assert "hard_researching" in states_from


# ===================================================================
# 3. Hard pipeline E2E
# ===================================================================

class TestHardE2E:
    def test_hard_author_says_manual(self):
        """Hard pipeline: research → report → author says manual → done."""
        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("hard"),
            "hard_researching": agent_returning("ready"),
            "hard_report_posted": agent_returning("author_responds"),
            "hard_author_guided": agent_returning("manual"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        final, audit = engine.run(ctx)

        assert final == "done"

    def test_hard_author_says_try_fix(self):
        """Hard pipeline: author says try_fix → transitions to medium planning."""
        step_count = {"test": 0}

        def step_tester(ctx, **kwargs):
            step_count["test"] += 1
            return {"event": "last_step"}

        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("hard"),
            "hard_researching": agent_returning("ready"),
            "hard_report_posted": agent_returning("author_responds"),
            "hard_author_guided": agent_returning("try_fix"),
            "med_planning": agent_returning("planned"),
            "med_step_executing": agent_returning("done"),
            "med_step_testing": step_tester,
            "med_integrating": agent_returning("passed"),
            "creating_pr": agent_returning("created"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        final, audit = engine.run(ctx)

        assert final == "done"
        states_from = [e.from_state for e in audit]
        assert "hard_author_guided" in states_from
        assert "med_planning" in states_from


# ===================================================================
# 4. Context integrity across pipeline
# ===================================================================

class TestContextIntegrity:
    def test_history_accumulates(self):
        """ctx.history grows with each step."""
        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("skip"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        engine.run(ctx)

        assert len(ctx.history) == 2
        assert ctx.history[0]["state"] == "received"
        assert ctx.history[1]["state"] == "classifying"

    def test_final_ctx_state_matches(self):
        """ctx.state is updated to the final state after run()."""
        pipeline = {
            "received": agent_returning("classified"),
            "classifying": agent_returning("skip"),
        }
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)
        ctx = make_ctx()

        final, _ = engine.run(ctx)

        assert ctx.state == final
        assert ctx.state == "done"
