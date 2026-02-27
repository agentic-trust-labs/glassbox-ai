"""
GlassBox Agent — Test Validator
==================================

Purpose:
    Verify that a code fix actually works by running tests and checking results.
    This is the "skeptic" of the system — it doesn't trust the fix generator's
    claim that the fix works; it VERIFIES by running actual tests.

How it works:
    1. Receives the fix (edits applied) and test configuration via ctx.config.
    2. Runs three checks (the "TP" pattern from the old system):
        TP1: Syntax check — can Python still import the module after the fix?
        TP2: Full test suite — do all existing tests still pass?
        TP3: Diff size check — is the fix minimal? (More than 3 lines is suspicious for easy bugs)
    3. Returns passed/failed with details.

    If tests fail, the engine routes to "retrying" where the fix generator gets
    another attempt with the failure details as feedback.

Why TP1/TP2/TP3:
    TP1 (syntax) catches the most common LLM error: generating syntactically invalid code.
    Things like unclosed brackets, wrong indentation, or invalid Python. This check is
    instant (just import the module) and catches ~30% of failures before running the
    full test suite.

    TP2 (test suite) runs the actual pytest suite. This catches regressions — the fix
    might solve the reported bug but break something else.

    TP3 (diff size) is a heuristic: easy bugs should be 1-3 line changes. If the fix
    is 10+ lines, the LLM probably went overboard (refactoring, adding comments, etc.)
    and the fix is likely fragile. This is a warning, not a hard failure.

Ported from:
    Old Tester.validate() in glassbox_agent/agents/tester.py.
    Stripped of class inheritance. Uses tools/test_runner.py for actual test execution.
"""

from __future__ import annotations

from typing import Any

from glassbox.core.models import AgentContext


def run(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Validate a fix by running tests. Returns passed or failed.

    Called by the engine when in "easy_testing" (or similar) state.

    Reads from ctx.config:
        fix          → The fix dict with edits (from fix_generator)
        module       → Python module to syntax-check (default: "glassbox")
        test_path    → Path to test directory (default: "tests/")
        test_args    → Extra pytest arguments (str, default: "")
        repo_root    → Absolute path to repo root (for test runner)
        max_diff_lines → Maximum acceptable diff size (default: 3 for easy bugs)

    Returns:
        On success: {"event": "passed", "detail": "All tests passed", "test_result": dict}
        On failure: {"event": "failed", "detail": "<failure description>", "test_result": dict}
    """

    # Import here to avoid circular imports at module level.
    # The test_runner is a tool, not a core dependency.
    from glassbox.tools.test_runner import TestRunner

    fix = ctx.config.get("fix", {})
    module = ctx.config.get("module", "glassbox")
    test_path = ctx.config.get("test_path", "tests/")
    test_args = ctx.config.get("test_args", "")
    repo_root = ctx.config.get("repo_root", ".")
    max_diff_lines = ctx.config.get("max_diff_lines", 3)

    runner = TestRunner(repo_root=repo_root)

    # TP1: Syntax check — can the module still be imported?
    # This is the fastest check and catches the most common LLM errors.
    syntax_ok, syntax_error = runner.syntax_check(module)
    if not syntax_ok:
        return {
            "event": "failed",
            "detail": f"TP1 Syntax check FAILED: {syntax_error}",
            "test_result": {
                "passed": False,
                "tp1_syntax": False,
                "tp1_error": syntax_error,
            },
        }

    # TP2: Full test suite — do all existing tests still pass?
    test_result = runner.run_tests(test_path=test_path, extra_args=test_args)

    # TP3: Diff size check — is the fix minimal?
    # Count total lines changed across all edits.
    edits = fix.get("edits", [])
    total_diff_lines = sum(
        e.get("end_line", 0) - e.get("start_line", 0) + 1
        for e in edits
    )

    # Build the result dict with all check details.
    result = {
        "passed": test_result.passed,
        "tp1_syntax": True,
        "tp2_passed": test_result.passed,
        "tp2_total": test_result.total,
        "tp2_failures": [
            {"test_name": f.test_name, "message": f.message}
            for f in test_result.failures
        ],
        "tp3_diff_lines": total_diff_lines,
        "tp3_within_limit": total_diff_lines <= max_diff_lines,
        "output": test_result.output,
    }

    if not test_result.passed:
        # Format failure details for feedback to the fix generator on retry.
        failure_summary = "; ".join(
            f"{f.test_name}: {f.message[:100]}" for f in test_result.failures[:5]
        )
        return {
            "event": "failed",
            "detail": f"TP2 Tests FAILED ({len(test_result.failures)} failures): {failure_summary}",
            "test_result": result,
        }

    # All checks passed. Include a note about diff size if it's larger than expected.
    detail = f"All {test_result.total} tests passed."
    if not result["tp3_within_limit"]:
        detail += f" Warning: diff is {total_diff_lines} lines (expected <= {max_diff_lines})."

    return {
        "event": "passed",
        "detail": detail,
        "test_result": result,
    }
