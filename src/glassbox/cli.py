"""
GlassBox CLI — Entry Point
==============================

The thin command-line interface for running GlassBox.

This file is intentionally small (~60 lines of logic). Its ONLY job is:
    1. Parse command-line arguments (issue number, repo, use case).
    2. Load the use case's settings, states, and pipeline.
    3. Create an Engine and run it.
    4. Print the result.

All actual work happens in the engine (core/engine.py), agents (agents/),
and tools (tools/). The CLI just wires them together.

Usage:
    # Run with default use case (github_issues):
    PYTHONPATH=src python -m glassbox.cli 42

    # Run with explicit repo:
    PYTHONPATH=src python -m glassbox.cli 42 --repo agentic-trust-labs/glassbox-ai

    # Run with a different use case (future):
    PYTHONPATH=src python -m glassbox.cli 42 --use-case code_review

Why this replaces the old cli.py:
    The old cli.py (223 lines) hardcoded the Manager → JuniorDev → Tester → PR
    pipeline with extensive inline logic for retries, comment formatting, and
    error handling. All of that is now handled by the engine (state machine),
    agents (individual functions), and tools (GitHub client, etc.).

    This CLI just says: "load the pipeline, create an engine, run."
"""

from __future__ import annotations

import argparse
import sys

from glassbox.core.engine import Engine
from glassbox.core.models import AgentContext


def main() -> None:
    """
    Main entry point for the GlassBox CLI.

    Parses arguments, loads the appropriate use case, creates an Engine,
    runs the state machine, and prints the audit trail.
    """

    parser = argparse.ArgumentParser(
        description="GlassBox — Transparent AI Agent Platform",
        usage="python -m glassbox.cli ISSUE_NUMBER [--repo REPO] [--use-case USE_CASE]",
    )
    parser.add_argument(
        "issue_number",
        type=int,
        help="GitHub issue number to process.",
    )
    parser.add_argument(
        "--repo",
        default="",
        help="GitHub repository in owner/name format. Defaults to GITHUB_REPOSITORY env var.",
    )
    parser.add_argument(
        "--use-case",
        default="github_issues",
        help="Which use case to run. Default: github_issues.",
    )

    args = parser.parse_args()

    # Load the use case's settings, transitions, and pipeline.
    # Currently only github_issues is supported. Future use cases will be
    # loaded dynamically based on the --use-case argument.
    transitions, pipeline, config = _load_use_case(args.use_case)

    # Override repo from CLI argument if provided.
    if args.repo:
        config["repo"] = args.repo

    # Create the agent context — the world as agents see it.
    ctx = AgentContext(
        issue_number=args.issue_number,
        repo=config.get("repo", ""),
        state="received",
        config=config,
    )

    # Create and run the engine.
    engine = Engine(
        transitions=transitions,
        pipeline=pipeline,
    )

    print(f"GlassBox v0.5.0-alpha — Processing issue #{args.issue_number}")
    print(f"Use case: {args.use_case}")
    print(f"Repo: {ctx.repo}")
    print("---")

    final_state, audit = engine.run(ctx)

    # Print the audit trail — the full story of what happened.
    print("\nAudit Trail:")
    for entry in audit:
        print(f"  {entry.from_state} → {entry.to_state} [{entry.event}] ({entry.agent})")
        if entry.detail:
            print(f"    {entry.detail[:120]}")

    print(f"\nFinal state: {final_state}")

    # Exit with non-zero code if the pipeline failed.
    if final_state == "failed":
        sys.exit(1)


def _load_use_case(name: str) -> tuple[dict, dict, dict]:
    """
    Load a use case by name.

    Returns:
        (transitions, pipeline, config) — The three things the Engine needs.

    Currently only supports "github_issues". Future use cases will be
    discovered dynamically from the use_cases/ directory.

    Raises:
        SystemExit if the use case is not found.
    """

    if name == "github_issues":
        from glassbox.use_cases.github_issues.states import TRANSITIONS
        from glassbox.use_cases.github_issues.pipeline import build_pipeline
        from glassbox.use_cases.github_issues.settings import load_settings

        return TRANSITIONS, build_pipeline(), load_settings()

    print(f"Error: Unknown use case '{name}'. Available: github_issues")
    sys.exit(1)


if __name__ == "__main__":
    main()
