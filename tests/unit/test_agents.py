"""
Agent Unit Tests
==================

Tests for individual agent functions with mocked LLM calls.
No real OpenAI API calls — everything is patched.

Each test verifies:
    - The agent returns the correct event for a given mock LLM response.
    - The agent handles malformed LLM output gracefully.
    - The agent includes required fields in its result dict.
"""

import json
from unittest.mock import patch

import pytest

from glassbox.core.models import AgentContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ctx(**overrides):
    """Create a minimal AgentContext for testing."""
    defaults = {
        "issue_number": 42,
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
# 1. Classifier agent
# ===================================================================

class TestClassifier:
    @patch("glassbox.agents.classifier.call_llm")
    def test_classifier_easy(self, mock_llm):
        """Classifier returns 'easy' event when LLM classifies as easy."""
        from glassbox.agents.classifier import run

        mock_llm.return_value = json.dumps({
            "difficulty": "easy",
            "confidence": 0.95,
            "template_id": "typo_fix",
            "reasoning": "Single file typo fix, high confidence.",
        })

        ctx = make_ctx()
        ctx.config["title"] = "Typo in config"
        ctx.config["body"] = "DEFAULT_VALUE should be 0.85"
        ctx.config["sources"] = {"src/config.py": "DEFAULT_VALUE = 0.80\n"}
        ctx.config["template_list"] = "typo_fix, wrong_value"
        ctx.config["past_reflections"] = ""

        result = run(ctx)

        assert result["event"] == "easy"
        assert "triage" in result

    @patch("glassbox.agents.classifier.call_llm")
    def test_classifier_skip(self, mock_llm):
        """Classifier returns 'skip' when LLM says to skip."""
        from glassbox.agents.classifier import run

        mock_llm.return_value = json.dumps({
            "difficulty": "skip",
            "confidence": 0.9,
            "template_id": "",
            "reasoning": "This is a question, not a bug.",
        })

        ctx = make_ctx()
        ctx.config["title"] = "How do I install?"
        ctx.config["body"] = "What are the requirements?"
        ctx.config["sources"] = {}
        ctx.config["template_list"] = "typo_fix"
        ctx.config["past_reflections"] = ""

        result = run(ctx)

        assert result["event"] == "skip"

    @patch("glassbox.agents.classifier.call_llm")
    def test_classifier_malformed_json(self, mock_llm):
        """Classifier handles malformed LLM JSON gracefully (falls back to hard)."""
        from glassbox.agents.classifier import run

        mock_llm.return_value = "not valid json {{"

        ctx = make_ctx()
        ctx.config["title"] = "Bug"
        ctx.config["body"] = "Something broken"
        ctx.config["sources"] = {}
        ctx.config["template_list"] = "typo_fix"
        ctx.config["past_reflections"] = ""

        result = run(ctx)

        assert result["event"] == "hard"  # Safe fallback


# ===================================================================
# 2. Fix Generator agent
# ===================================================================

class TestFixGenerator:
    @patch("glassbox.agents.fix_generator.call_llm")
    def test_fix_generator_success(self, mock_llm):
        """Fix generator returns 'fixed' with valid edit JSON."""
        from glassbox.agents.fix_generator import run

        mock_llm.return_value = json.dumps({
            "edits": [{"file": "src/config.py", "start_line": 12, "end_line": 12, "new_text": "    VALUE = 0.85\n"}],
            "test_code": "def test_fix(): assert True",
            "summary": "Fix default value",
            "strategy": "Changed value on line 12",
        })

        ctx = make_ctx(state="easy_fixing")
        ctx.config["title"] = "Wrong default"
        ctx.config["body"] = "Should be 0.85"
        ctx.config["sources"] = {"src/config.py": "VALUE = 0.80\n"}
        ctx.config["template_id"] = "wrong_value"
        ctx.config["template_instructions"] = "Fix the number"
        ctx.config["feedback"] = ""

        result = run(ctx)

        assert result["event"] == "fixed"
        assert "fix" in result

    @patch("glassbox.agents.fix_generator.call_llm")
    def test_fix_generator_malformed(self, mock_llm):
        """Fix generator handles malformed JSON gracefully."""
        from glassbox.agents.fix_generator import run

        mock_llm.return_value = "broken json"

        ctx = make_ctx(state="easy_fixing")
        ctx.config["title"] = "Bug"
        ctx.config["body"] = "Broken"
        ctx.config["sources"] = {}
        ctx.config["template_id"] = ""
        ctx.config["template_instructions"] = ""
        ctx.config["feedback"] = ""

        result = run(ctx)

        assert result["event"] == "failed"


# ===================================================================
# 3. Test Validator agent
# ===================================================================

class TestTestValidator:
    @patch("glassbox.tools.test_runner.TestRunner")
    def test_validator_pass(self, MockRunner):
        """Test validator returns 'passed' when all tests pass."""
        from glassbox.agents.test_validator import run
        from glassbox.tools.test_runner import TestResult

        instance = MockRunner.return_value
        instance.syntax_check.return_value = (True, "")
        instance.run_tests.return_value = TestResult(passed=True, total=10)

        ctx = make_ctx(state="easy_testing")

        result = run(ctx)

        assert result["event"] == "passed"

    @patch("glassbox.tools.test_runner.TestRunner")
    def test_validator_syntax_fail(self, MockRunner):
        """Test validator returns 'failed' on syntax error."""
        from glassbox.agents.test_validator import run

        instance = MockRunner.return_value
        instance.syntax_check.return_value = (False, "SyntaxError: unexpected EOF")

        ctx = make_ctx(state="easy_testing")

        result = run(ctx)

        assert result["event"] == "failed"
        assert "TP1" in result.get("detail", "")


# ===================================================================
# 4. Planner agent
# ===================================================================

class TestPlanner:
    @patch("glassbox.agents.planner.call_llm")
    def test_planner_success(self, mock_llm):
        """Planner returns 'planned' with steps."""
        from glassbox.agents.planner import run

        mock_llm.return_value = json.dumps({
            "steps": [
                {"description": "Fix the import", "files": ["src/main.py"], "checkpoint": False},
                {"description": "Update the test", "files": ["tests/test_main.py"], "checkpoint": False},
            ],
            "reasoning": "Two-step fix",
        })

        ctx = make_ctx(state="med_planning")
        ctx.config["title"] = "Multi-file bug"
        ctx.config["body"] = "Import is wrong and test is stale"

        result = run(ctx)

        assert result["event"] == "planned"
        assert "steps" in result
        assert len(result["steps"]) == 2

    @patch("glassbox.agents.planner.call_llm")
    def test_planner_too_hard(self, mock_llm):
        """Planner escalates to hard when it returns too_hard=true."""
        from glassbox.agents.planner import run

        mock_llm.return_value = json.dumps({
            "steps": [],
            "reasoning": "This requires architectural changes across 10+ files.",
            "too_hard": True,
        })

        ctx = make_ctx(state="med_planning")
        ctx.config["title"] = "Complex refactor"
        ctx.config["body"] = "Need to change 10 files"

        result = run(ctx)

        assert result["event"] == "too_hard"

    @patch("glassbox.agents.planner.call_llm")
    def test_planner_malformed(self, mock_llm):
        """Planner escalates to hard on malformed response (safe fallback)."""
        from glassbox.agents.planner import run

        mock_llm.return_value = "not json"

        ctx = make_ctx(state="med_planning")
        ctx.config["title"] = "Bug"
        ctx.config["body"] = "Details"

        result = run(ctx)

        assert result["event"] == "too_hard"


# ===================================================================
# 5. Localizer agent
# ===================================================================

class TestLocalizer:
    @patch("glassbox.agents.localizer.call_llm")
    def test_localizer_found(self, mock_llm):
        """Localizer returns 'found' with ranked files."""
        from glassbox.agents.localizer import run

        mock_llm.return_value = json.dumps({
            "files": [
                {"path": "src/config.py", "relevance": 0.95, "reason": "Contains the value"},
            ],
        })

        ctx = make_ctx(state="easy_localizing")
        ctx.config["title"] = "Wrong default"
        ctx.config["body"] = "Should be 0.85"
        ctx.config["file_list"] = ["src/config.py", "src/main.py"]

        result = run(ctx)

        assert result["event"] == "found"
        assert "files" in result
        assert result["files"][0]["path"] == "src/config.py"

    @patch("glassbox.agents.localizer.call_llm")
    def test_localizer_not_found(self, mock_llm):
        """Localizer returns 'not_found' when no files match."""
        from glassbox.agents.localizer import run

        mock_llm.return_value = json.dumps({"files": []})

        ctx = make_ctx(state="easy_localizing")
        ctx.config["title"] = "Mystery bug"
        ctx.config["body"] = "No idea where"
        ctx.config["file_list"] = []

        result = run(ctx)

        assert result["event"] == "not_found"


# ===================================================================
# 6. Conversationalist agent (no LLM — pure keyword parsing)
# ===================================================================

class TestConversationalist:
    def test_redirect_intent(self):
        """Conversationalist parses redirect intent from author comment."""
        from glassbox.agents.conversationalist import run

        ctx = make_ctx(state="hard_author_guided")
        ctx.config["author_comment"] = "Try changing the import path instead"
        ctx.history = [
            {"state": "easy_fixing", "event": "failed", "result": {}},
        ]

        result = run(ctx)

        assert result["event"] == "direction"
        assert result["route_to"] == "easy_fixing"

    def test_abort_intent(self):
        """Conversationalist routes to 'done' when author says stop."""
        from glassbox.agents.conversationalist import run

        ctx = make_ctx(state="hard_author_guided")
        ctx.config["author_comment"] = "stop, I'll handle this manually"

        result = run(ctx)

        assert result["event"] == "direction"
        assert result["route_to"] == "done"

    def test_approve_intent(self):
        """Conversationalist routes to creating_pr on approval."""
        from glassbox.agents.conversationalist import run

        ctx = make_ctx(state="hard_author_guided")
        ctx.config["author_comment"] = "LGTM, approve this"

        result = run(ctx)

        assert result["event"] == "direction"
        assert result["route_to"] == "creating_pr"
