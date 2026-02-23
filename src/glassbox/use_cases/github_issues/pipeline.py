"""
GlassBox Use Case — GitHub Issues Pipeline
=============================================

This file is the WIRING DIAGRAM for the GitHub Issues use case.
It maps each state to the agent function that should run at that state.

How it works:
    The engine receives a pipeline dict: {state_name: agent_function}.
    When the engine is in a given state, it looks up the agent function and calls it.

    Example:
        pipeline = {"classifying": classifier.run, "easy_fixing": fix_generator.run, ...}
        engine = Engine(transitions=TRANSITIONS, pipeline=pipeline)

    The engine doesn't know or care WHAT the agents do — it just calls the function
    at the right time based on the state machine.

Why build_pipeline() instead of a static dict:
    Some agent functions need runtime configuration (which model to use, file paths, etc.).
    build_pipeline() creates the dict with all the wiring ready to go.

    Also, using a factory function means we import agent modules lazily — only when
    the pipeline is actually built, not at module import time. This keeps startup fast
    and avoids circular import issues.

Agent mapping for this use case:
    State                → Agent              → What it does
    ─────────────────────────────────────────────────────────────
    received             → (no agent)         → Engine auto-transitions on "classified" event
    classifying          → classifier         → Routes to easy/medium/hard
    easy_localizing      → localizer          → Finds relevant files
    easy_fixing          → fix_generator      → Generates code fix
    easy_testing         → test_validator     → Runs tests
    med_planning         → planner            → Decomposes into steps
    med_step_executing   → fix_generator      → Executes one step
    med_step_testing     → test_validator     → Tests one step
    med_checkpoint       → (pause)            → Waits for author review
    med_integrating      → test_validator     → Runs integration tests
    hard_researching     → researcher         → Generates research report
    hard_report_posted   → (pause)            → Waits for author response
    hard_author_guided   → conversationalist  → Parses author's guidance
    retrying             → (retry logic)      → Decides: retry or give up
    asking_author        → (post question)    → Posts question to GitHub
    awaiting_author      → (pause)            → Waits for author
    creating_pr          → (create PR)        → Creates the pull request

Note: Some states don't have agents — they're handled by the engine's
built-in logic or are pause states that wait for external events.
"""

from __future__ import annotations

from typing import Any, Callable

from glassbox.core.models import AgentContext


# Type alias for agent functions.
AgentFn = Callable[..., dict[str, Any]]


def build_pipeline() -> dict[str, AgentFn]:
    """
    Build the state → agent function mapping for the GitHub Issues use case.

    Returns a dict that the Engine constructor accepts as the `pipeline` argument.

    Agents are imported lazily (inside this function) to:
        1. Avoid circular imports at module level.
        2. Keep import time fast (only import when actually building the pipeline).
        3. Allow tests to import this module without triggering all agent imports.
    """

    # Import agents from the shared pool.
    # Each agent module has a run() function that takes AgentContext and returns a dict.
    from glassbox.agents import classifier
    from glassbox.agents import localizer
    from glassbox.agents import fix_generator
    from glassbox.agents import test_validator
    from glassbox.agents import planner
    from glassbox.agents import researcher
    from glassbox.agents import conversationalist

    return {
        # --- CLASSIFICATION ---
        # The classifier determines difficulty and returns {"event": "easy|medium|hard|skip"}.
        "classifying": classifier.run,

        # --- EASY PIPELINE ---
        # Linear: localize → fix → test. Each agent returns an event that drives the next transition.
        "easy_localizing": localizer.run,
        "easy_fixing": fix_generator.run,
        "easy_testing": test_validator.run,

        # --- MEDIUM PIPELINE ---
        # The planner decomposes into steps. fix_generator and test_validator handle each step.
        # The same agents are reused — different states, same functions.
        "med_planning": planner.run,
        "med_step_executing": fix_generator.run,
        "med_step_testing": test_validator.run,
        "med_integrating": test_validator.run,

        # --- HARD PIPELINE ---
        # The researcher produces a report. The conversationalist parses author guidance.
        "hard_researching": researcher.run,
        "hard_author_guided": conversationalist.run,

        # --- COMMON ---
        # Retrying: a simple function that checks retry count and returns retry_ok or exhausted.
        "retrying": _retry_agent,
        # Asking author: posts a question to GitHub and returns "posted".
        "asking_author": _ask_author_agent,
        # Creating PR: creates the PR and returns "created".
        "creating_pr": _create_pr_agent,
    }


def _retry_agent(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Simple retry logic: check how many times we've retried and decide what to do.

    This is a lightweight "agent" — it doesn't call an LLM, just checks history.

    Retry policy:
        - Max 2 retries per state (configurable via ctx.config["max_retries"]).
        - On each retry, include the failure details as feedback so the fix_generator
          can try a DIFFERENT approach (exploration-exploitation, not same-mistake loops).
        - After exhausting retries, ask the author for help.

    Returns:
        {"event": "retry_ok"} → Go back to the failed state and try again.
        {"event": "exhausted"} → All retries used up, ask the human.
    """

    max_retries = ctx.config.get("max_retries", 2)

    # Count how many times we've been in "retrying" state for this run.
    retry_count = sum(1 for entry in ctx.history if entry.get("state") == "retrying")

    if retry_count >= max_retries:
        return {
            "event": "exhausted",
            "detail": f"Exhausted {max_retries} retries. Asking author for guidance.",
        }

    # Find the last failure's details to pass as feedback.
    last_failure = ""
    for entry in reversed(ctx.history):
        if entry.get("event") == "failed":
            result = entry.get("result", {})
            last_failure = result.get("detail", "Unknown failure")
            break

    # Store the failure feedback in config so the fix_generator can read it on retry.
    ctx.config["feedback"] = last_failure

    return {
        "event": "retry_ok",
        "detail": f"Retry {retry_count + 1}/{max_retries}. Previous failure: {last_failure[:100]}",
    }


def _ask_author_agent(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Post a question to the GitHub issue asking the author for guidance.

    This is triggered when:
        - The localizer can't find relevant files ("not_found")
        - All retries are exhausted ("exhausted")

    The question includes what we tried and what went wrong, so the author
    has context for their response.

    Returns:
        {"event": "posted"} → Transitions to awaiting_author (pause state).
    """

    # Build a summary of what happened from history.
    failures = []
    for entry in ctx.history:
        if entry.get("event") == "failed":
            detail = entry.get("result", {}).get("detail", "unknown error")
            failures.append(detail)

    question = "I need your guidance on this issue.\n\n"
    if failures:
        question += "**What I tried:**\n"
        for i, f in enumerate(failures, 1):
            question += f"{i}. {f[:200]}\n"
        question += "\n**What would you like me to try next?**\n"
        question += "- Reply with guidance and I'll try again\n"
        question += "- Reply 'stop' if you'd like to handle this manually\n"
    else:
        question += "I couldn't determine how to proceed. Could you provide more details?\n"

    # The actual GitHub comment posting is handled by the engine's state_store
    # or by the use case's integration layer. We just return the question text.
    return {
        "event": "posted",
        "detail": "Posted question to author.",
        "question": question,
    }


def _create_pr_agent(ctx: AgentContext, **kwargs: Any) -> dict[str, Any]:
    """
    Create a pull request with the fix.

    This is the final step of a successful pipeline. It:
        1. Creates a branch (fix/issue-{number}).
        2. Commits the changes.
        3. Creates a PR linking to the issue.

    The actual git operations are handled by tools/github_client.py.
    This agent just orchestrates the steps and returns the PR URL.

    Returns:
        {"event": "created", "detail": "PR URL", "pr_url": str}
    """

    # Import here to avoid circular imports.
    from glassbox.tools.github_client import GitHubClient

    repo = ctx.repo
    issue_number = ctx.issue_number
    branch = f"fix/issue-{issue_number}"

    # Get the commit message from the fix result in history.
    commit_message = f"fix: resolve issue #{issue_number}"
    for entry in reversed(ctx.history):
        result = entry.get("result", {})
        if "fix" in result:
            fix = result["fix"]
            if isinstance(fix, dict) and fix.get("summary"):
                commit_message = fix["summary"]
            break

    try:
        github = GitHubClient(repo=repo)
        github.create_branch(branch)
        github.commit_and_push(branch, commit_message)

        pr_body = f"Fixes #{issue_number}\n\n"
        pr_body += f"**Commit:** {commit_message}\n"
        pr_body += f"**Pipeline:** {ctx.state}\n"
        pr_body += f"**Audit trail:** {len(ctx.history)} steps\n"

        pr_url = github.create_pr(
            branch=branch,
            issue_number=issue_number,
            title=commit_message,
            body=pr_body,
        )

        return {
            "event": "created",
            "detail": f"PR created: {pr_url}",
            "pr_url": pr_url,
        }
    except Exception as e:
        return {
            "event": "created",  # Still "created" to avoid infinite retry on PR creation.
            "detail": f"PR creation had issues: {e}. Branch {branch} was pushed.",
            "pr_url": f"https://github.com/{repo}/compare/main...{branch}",
        }
