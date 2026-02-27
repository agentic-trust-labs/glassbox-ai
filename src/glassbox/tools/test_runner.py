"""
GlassBox Tool — Test Runner
==============================

Purpose:
    Run pytest and parse the output into structured results. This is how the
    test_validator agent verifies that a fix actually works.

Why structured results:
    Raw pytest output is a wall of text. Agents need structured data:
        - Did it pass? (bool)
        - How many tests? (int)
        - Which tests failed? (list of {test_name, message, file, line})
        - What was the full output? (str, for debugging)

    The TestRunner parses pytest's output into a TestResult dataclass that
    agents can inspect programmatically.

Test patterns (TP):
    TP1: Syntax check — Can the module still be imported after the fix?
         This catches the most common LLM error: invalid Python syntax.
         It's instant (python -c "import module") and catches ~30% of failures.

    TP2: Full test suite — Do all existing tests pass?
         Runs pytest with short traceback for quick feedback.

    TP3: Diff size check — Is the fix minimal?
         (Handled by test_validator agent, not this tool.)

Ported from:
    glassbox_agent/tools/test_runner.py — port with added documentation.
    Updated imports to use glassbox.use_cases.github_issues.models instead of
    the old glassbox_agent.core.models.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Test result models.
#
# These are defined HERE (in the tool) rather than in core/models.py because:
#   1. They are specific to test execution, not to the platform engine.
#   2. Core models only contain what the ENGINE reads (AgentContext, TriageResult, AuditEntry).
#   3. A security-audit use case wouldn't need TestResult — it would have
#      its own result types. These models belong with the tool that creates them.
# ---------------------------------------------------------------------------

@dataclass
class TestFailure:
    """
    One test failure from a pytest run.

    Fields:
        test_name → Name of the failing test function (e.g., "test_config_value").
        message   → The error message or assertion details.
        file      → File path of the test (e.g., "tests/test_config.py").
        line      → Line number where the failure occurred. 0 if unknown.
    """

    test_name: str
    message: str
    file: str = ""
    line: int = 0


@dataclass
class TestResult:
    """
    Structured result of a pytest run.

    Fields:
        passed     → Did all tests pass? (bool)
        total      → Total number of tests run.
        failures   → List of TestFailure objects for each failing test.
        output     → Raw pytest output (stdout + stderr). For debugging.
        diff_lines → Number of lines changed by the fix. Set by test_validator, not by runner.
    """

    passed: bool
    total: int = 0
    failures: list[TestFailure] = field(default_factory=list)
    output: str = ""
    diff_lines: int = 0


class TestRunner:
    """
    Runs pytest and parses output into structured TestResult.

    Constructor:
        repo_root → Absolute path to the repository root.
                     Tests are run with this as the working directory.
    """

    def __init__(self, repo_root: str):
        self._root = repo_root

    def syntax_check(self, module: str) -> tuple[bool, str]:
        """
        TP1: Check syntax by importing the module.

        This is the fastest sanity check after applying a fix.
        If the fix broke Python syntax (missing colon, unclosed bracket, bad indent),
        this catches it instantly without running the full test suite.

        Args:
            module → Python module to import (e.g., "glassbox").

        Returns:
            (True, "") if the module imports successfully.
            (False, error_message) if there's a syntax/import error.
        """

        cmd = f'python -c "import {module}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=self._root)
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()

    def run_tests(self, test_path: str = "tests/", extra_args: str = "") -> TestResult:
        """
        TP2: Run the full pytest suite and parse the results.

        Uses --tb=short for concise failure tracebacks (enough for LLM feedback,
        not overwhelming).

        Args:
            test_path  → Path to test directory or file, relative to repo root.
            extra_args → Additional pytest arguments (e.g., "-k test_config" to filter).

        Returns:
            TestResult with pass/fail status, failure details, and raw output.
        """

        cmd = f"python -m pytest {test_path} --tb=short {extra_args}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=self._root)
        output = result.stdout + "\n" + result.stderr
        return self._parse_output(output, result.returncode == 0)

    def _parse_output(self, output: str, passed: bool) -> TestResult:
        """
        Parse pytest output into a structured TestResult.

        Extracts:
            - Total test count from summary line ("X passed" / "X failed")
            - Individual failure details from "FAILED" lines
            - Falls back to last 15 lines of output if parsing fails

        This parsing is heuristic-based (regex on pytest output format).
        It handles the standard pytest output format. Custom formatters or
        plugins may produce different output that doesn't parse correctly —
        in that case, the raw output is still available in TestResult.output.
        """

        total = 0
        failures: list[TestFailure] = []

        # Parse summary line: "X passed" and/or "Y failed"
        summary_match = re.search(r"(\d+) passed", output)
        if summary_match:
            total += int(summary_match.group(1))
        failed_match = re.search(r"(\d+) failed", output)
        if failed_match:
            total += int(failed_match.group(1))

        # Parse individual failure lines: "FAILED tests/test_x.py::test_name - reason"
        for m in re.finditer(r"FAILED\s+([\w/.]+)::(\w+)\s*[-–]\s*(.*)", output):
            failures.append(TestFailure(
                file=m.group(1),
                test_name=m.group(2),
                message=m.group(3).strip(),
            ))

        # Fallback: if tests failed but we couldn't parse individual failures,
        # grab the last 15 lines as a best-effort error description.
        if not passed and not failures:
            lines = output.strip().split("\n")
            last_lines = "\n".join(lines[-15:])
            failures.append(TestFailure(test_name="unknown", message=last_lines))

        return TestResult(passed=passed, total=total, failures=failures, output=output)
