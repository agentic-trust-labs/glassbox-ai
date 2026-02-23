"""
Event Contract Tests
======================

Verify that each agent's run() function returns a dict conforming to the
event contract defined in glassbox.agents.__init__:

    - Must contain "event" key (str)
    - Event value must be one of the agent's valid events
    - Must contain agent-specific required keys

These tests use mocked LLM calls — no API keys needed.
"""

import json
from unittest.mock import patch

import pytest

from glassbox.core.models import AgentContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ctx(**overrides):
    """Create a minimal AgentContext for contract testing."""
    defaults = {
        "issue_number": 1,
        "repo": "test/repo",
        "state": "classifying",
        "config": {
            "model": "gpt-4o",
            "model_classify": "gpt-4o-mini",
            "model_localize": "gpt-4o-mini",
            "review_model": "claude-3-5-sonnet-20241022",
            "temperature_classify": 0.3,
            "temperature_code": 1.0,
            "temperature_review": 0.3,
            "temperature_plan": 0.5,
            "temperature_localize": 0.3,
            "max_retries": 2,
            "templates_dir": "/tmp/templates",
            "reflections_path": "/tmp/reflections.json",
            "repo_root": "/tmp/repo",
            "module": "glassbox",
            "test_path": "tests/",
            "test_args": "",
            "max_diff_lines": 3,
        },
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


# ===================================================================
# Classifier contract
# ===================================================================

CLASSIFIER_VALID_EVENTS = {"easy", "medium", "hard", "skip"}


class TestClassifierContract:
    @patch("glassbox.agents.classifier.call_llm")
    def test_returns_event_key(self, mock_llm):
        """Classifier result must contain 'event' key."""
        from glassbox.agents.classifier import run

        mock_llm.return_value = json.dumps({
            "difficulty": "easy",
            "confidence": 0.95,
            "template_id": "typo_fix",
            "reasoning": "Simple typo.",
        })

        ctx = make_ctx(
            config={
                **make_ctx().config,
                "issue_title": "Fix typo",
                "issue_body": "There's a typo in config.",
                "source_files": {},
            }
        )
        result = run(ctx)
        assert "event" in result, "Classifier must return 'event' key"

    @patch("glassbox.agents.classifier.call_llm")
    def test_event_is_valid(self, mock_llm):
        """Classifier event must be one of: easy, medium, hard, skip."""
        from glassbox.agents.classifier import run

        mock_llm.return_value = json.dumps({
            "difficulty": "easy",
            "confidence": 0.95,
            "template_id": "typo_fix",
            "reasoning": "Simple typo.",
        })

        ctx = make_ctx(
            config={
                **make_ctx().config,
                "issue_title": "Fix typo",
                "issue_body": "There's a typo in config.",
                "source_files": {},
            }
        )
        result = run(ctx)
        assert result["event"] in CLASSIFIER_VALID_EVENTS, (
            f"Classifier event '{result['event']}' not in {CLASSIFIER_VALID_EVENTS}"
        )
