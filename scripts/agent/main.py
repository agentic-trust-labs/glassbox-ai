#!/usr/bin/env python3
"""GlassBox Agent v0.3-beta - orchestrator entry point.

5-message protocol:
  1. ANALYSIS  - aspects, challenges, edge cases (think before coding)
  2. APPROACH  - IDE-style diff, verbose
  3. PERFORMANCE - graded checklist + debate
  4. CI RUNNING - branch pushed, tests passing
  5. PR CREATED - link, summary, transparency
"""

import os
import sys
import traceback

from openai import OpenAI

from .config import REPO, MAX_RETRIES, AGENT_LABEL, AGENT_NAME
from .github import GitHubClient
from .locator import Locator
from .memory import Memory
from .messenger import Messenger
from .analyzer import Analyzer
from .coder import Coder
from .reviewer import Reviewer
from .runner import Runner


class AgentPipeline:
    """Orchestrates the 5-message agent flow."""

    def __init__(self, issue_number: int):
        self.issue_number = issue_number
        self.branch = f"agent/issue-{issue_number}"
        self.ack_comment_id = int(os.environ.get("ACK_COMMENT_ID", "0"))

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.client = OpenAI(api_key=api_key)

        repo_root = os.getcwd()
        self.gh = GitHubClient(REPO)
        self.locator = Locator(repo_root)
        self.memory = Memory()
        self.messenger = Messenger()
        self.analyzer = Analyzer(self.client, self.memory)
        self.coder = Coder(self.client)
        self.reviewer = Reviewer(self.client)
        self.runner = Runner()

    def run(self):
        """Execute the full 5-message pipeline."""
        n = self.issue_number

        # ── Read issue ──
        issue_title, issue_body = self.gh.read_issue(n)
        print(f"Issue #{n}: {issue_title}")

        # ── Phase 1: ANALYSIS (Message 1) - silent update, no email ──
        print("\n Phase 1: ANALYSIS")
        repo_map = self.locator.get_repo_map()
        sources = self.locator.get_relevant_sources()
        analysis = self.analyzer.analyze(n, issue_title, issue_body, sources, repo_map)
        msg1 = self.messenger.msg1_analysis(n, issue_title, analysis)
        self.ack_comment_id = self.gh.silent_update(n, self.ack_comment_id, msg1)

        # ── Phase 2-3: CODE + REVIEW (retry loop) ──
        self.gh.create_branch(self.branch)
        prev_error = None

        for attempt in range(1, MAX_RETRIES + 2):
            print(f"\n Attempt {attempt}/{MAX_RETRIES + 1}")

            # Reset to clean state on retry
            if attempt > 1:
                self.gh.reset_branch(self.branch)
            sources = self.locator.get_relevant_sources()

            # Phase 2: APPROACH (Message 2)
            print("  Phase 2: APPROACH")
            try:
                fix = self.coder.generate_fix(n, issue_title, issue_body, sources, analysis, prev_error)
            except Exception as e:
                self.gh.post_comment(n, f"❌ **OpenAI API error (attempt {attempt}):** `{str(e)[:200]}`")
                if attempt > MAX_RETRIES:
                    sys.exit(1)
                continue

            if not fix.changes:
                self.gh.post_comment(n, "❌ **Agent couldn't generate changes.** Manual fix needed.")
                sys.exit(1)

            msg2 = self.messenger.msg2_approach(fix)
            self.ack_comment_id = self.gh.silent_update(n, self.ack_comment_id, msg1 + "\n\n---\n\n" + msg2)

            # Apply fix (BEFORE debate — tests are truth, debate is opinion)
            ok, err = self.runner.apply_fix(fix, sources)
            if not ok:
                prev_error = f"Apply failed: {err}"
                if attempt > MAX_RETRIES:
                    self.gh.post_comment(n, f"❌ **Fix failed after {attempt} attempts.** Could not apply.\n\n{err}")
                    sys.exit(1)
                continue

            # Syntax check
            ok, err = self.runner.syntax_check()
            if not ok:
                self.memory.save_reflection(
                    issue_number=n,
                    issue_title=issue_title,
                    failure_modes=["F1", "F10"],
                    reflection=f"Syntax/import failed: {err[:200]}",
                )
                prev_error = f"Syntax error: {err}"
                if attempt > MAX_RETRIES:
                    self.gh.post_comment(n, f"❌ **Syntax error after {attempt} attempts.**\n\n{err}")
                    sys.exit(1)
                continue

            # Run tests
            ok, output, test_count = self.runner.run_tests()
            if not ok:
                last_lines = "\n".join(output.strip().split("\n")[-20:])
                self.memory.save_reflection(
                    issue_number=n,
                    issue_title=issue_title,
                    failure_modes=["F5", "F12"],
                    reflection=f"Tests failed: {last_lines[:200]}",
                )
                prev_error = f"Tests failed:\n{last_lines}"
                if attempt > MAX_RETRIES:
                    self.gh.post_comment(n, f"❌ **Tests failed after {attempt} attempts.** Manual fix needed.\n\n```\n{last_lines}\n```")
                    sys.exit(1)
                continue

            # Phase 3: PERFORMANCE (Message 3) - debate WITH test results
            print("  Phase 3: PERFORMANCE")
            test_summary = "\n".join(output.strip().split("\n")[-5:])
            review = self.reviewer.review(fix, analysis, sources, issue_title, test_output=test_summary)
            msg3 = self.messenger.msg3_performance(review, attempt)
            self.ack_comment_id = self.gh.silent_update(n, self.ack_comment_id, msg1 + "\n\n---\n\n" + msg2 + "\n\n---\n\n" + msg3)

            if not review.approved:
                failed_edges = [g.id for v in review.votes for g in v.grades if not g.passed and g.id.startswith("E")]
                self.memory.save_reflection(
                    issue_number=n,
                    issue_title=issue_title,
                    failure_modes=["F6", "F13"],
                    reflection=f"Debate rejected: {review.votes[0].reason if review.votes else 'unknown'}",
                    edge_case_missed=", ".join(failed_edges[:3]),
                )
                prev_error = f"Debate rejected ({sum(1 for v in review.votes if v.approve)}/3):\n" + "\n".join(
                    f"@{v.agent}: {v.reason}" for v in review.votes
                )
                if attempt > MAX_RETRIES:
                    self.gh.post_comment(n, "❌ **Debate could not approve after all attempts.** Manual fix needed.")
                    sys.exit(1)
                continue

            # All passed + debate approved
            print(f"  ✅ Tests passed + debate approved on attempt {attempt}")
            break

        # ── Phase 4: CI RUNNING (Message 4) - silent update, no email ──
        print("\n Phase 4: CI RUNNING")
        commit_msg = f"fix: {fix.summary} (#{n})"
        self.gh.commit_and_push(self.branch, commit_msg)
        msg4 = self.messenger.msg4_ci_running(self.branch, n, fix.summary, test_count)
        self.ack_comment_id = self.gh.silent_update(n, self.ack_comment_id, msg1 + "\n\n---\n\n" + msg2 + "\n\n---\n\n" + msg3 + "\n\n---\n\n" + msg4)

        # ── Phase 5: PR CREATED (Message 5) - NEW comment, triggers email ──
        print("\n Phase 5: PR CREATED")
        pr_body = (
            f"Closes #{n}\n\n"
            f"## Changes\n{fix.summary}\n\n"
            f"## Strategy\n{fix.strategy}\n\n"
            f"## Generated by\n"
            f"🤖 **{AGENT_LABEL}** - 5-message protocol\n\n"
            f"## Tests\n✅ {test_count}\n"
        )
        pr_url = self.gh.create_pr(self.branch, n, f"fix: {fix.summary}", pr_body)
        msg5 = self.messenger.msg5_pr_created(pr_url, fix, n, attempt)
        self.gh.post_comment(n, msg5)
        print(f"\n  Done! PR: {pr_url}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.agent.main <issue_number>")
        sys.exit(1)

    issue_number = int(sys.argv[1])
    pipeline = AgentPipeline(issue_number)
    pipeline.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        # Post error to issue so it's visible in the thread
        if len(sys.argv) >= 2:
            try:
                n = int(sys.argv[1])
                gh = GitHubClient(REPO)
                gh.post_comment(n, f"❌ **{AGENT_NAME} crashed:** `{type(e).__name__}: {str(e)[:300]}`\n\nManual fix needed.")
            except Exception:
                pass
        sys.exit(1)
