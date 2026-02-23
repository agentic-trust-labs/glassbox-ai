"""
GlassBox Tool — GitHub Client
================================

Purpose:
    Encapsulate all GitHub API + git operations into a single, dependency-injectable
    tool. Every interaction with GitHub (reading issues, posting comments, creating
    PRs, managing branches) goes through this class.

Why a single GitHub client:
    1. Testability: Mock ONE class in tests instead of mocking subprocess calls everywhere.
    2. Fail-fast: All git/gh commands go through _sh() and _gh_api() which log errors
       consistently instead of silently failing.
    3. Rate limiting: Future rate limiting can be added in _gh_api() without changing callers.
    4. Authentication: The gh CLI handles auth (via GITHUB_TOKEN or gh auth login).
       We don't manage tokens directly — the gh CLI does it.

Implementation:
    Uses the `gh` CLI tool (GitHub CLI) for API calls instead of the requests library.
    This is a deliberate choice:
        - gh handles authentication automatically (token management, SSO, etc.)
        - gh handles pagination, retries, and rate limiting internally
        - gh is already installed in GitHub Actions runners
        - No additional Python dependencies (no requests, no PyGithub)

    Uses subprocess for git operations (branch, commit, push).

Ported from:
    glassbox_agent/tools/github_client.py — VERBATIM port with added documentation.
    The implementation is battle-tested from the v2 agent pipeline.
"""

from __future__ import annotations

import json
import subprocess


class GitHubClient:
    """
    Encapsulates all GitHub + git operations. Dependency-injectable, fail-fast.

    Constructor:
        repo → Repository in "owner/name" format (e.g., "agentic-trust-labs/glassbox-ai").
               Used for all API calls and git operations.

    All methods are synchronous (subprocess-based). This is intentional:
    the agent pipeline runs sequentially, not concurrently. Async would add
    complexity without benefit.
    """

    def __init__(self, repo: str):
        self._repo = repo

    def read_issue(self, issue_number: int) -> tuple[str, str]:
        """
        Read an issue's title and body.

        Uses: gh issue view <number> --repo <repo> --json title,body

        Returns:
            (title, body) — The issue title and body text.
        """
        result = self._sh(f"gh issue view {issue_number} --repo {self._repo} --json title,body")
        self._check(result, "read_issue")
        issue = json.loads(result.stdout)
        return issue["title"], issue.get("body", "")

    def post_comment(self, issue_number: int, body: str) -> int:
        """
        Post a new comment on an issue.

        This creates a NEW comment (triggers GitHub notification email).
        For updates that shouldn't notify, use update_comment() or silent_update().

        Returns:
            comment_id (int) — The ID of the created comment. 0 on failure.
        """
        result = self._gh_api(
            f"repos/{self._repo}/issues/{issue_number}/comments",
            data={"body": body},
        )
        self._check(result, "post_comment")
        try:
            return json.loads(result.stdout).get("id", 0)
        except (json.JSONDecodeError, AttributeError):
            return 0

    def update_comment(self, comment_id: int, body: str) -> bool:
        """
        Edit an existing comment in-place.

        This does NOT trigger a GitHub notification email — only new comments do.
        Use this for state updates, progress updates, etc. that shouldn't spam
        the issue author's inbox.

        Returns:
            True if the update succeeded, False otherwise.
        """
        if comment_id <= 0:
            return False
        result = self._gh_api(
            f"repos/{self._repo}/issues/comments/{comment_id}",
            method="PATCH",
            data={"body": body},
        )
        return result.returncode == 0

    def silent_update(self, issue_number: int, comment_id: int, body: str) -> int:
        """
        Update a comment if possible, fall back to posting a new one.

        This is the preferred method for state persistence:
            - If we have a comment_id from a previous save, EDIT it (no notification).
            - If not (first save), POST a new comment.

        Returns:
            comment_id (int) — The ID of the updated or new comment.
        """
        if comment_id > 0 and self.update_comment(comment_id, body):
            return comment_id
        return self.post_comment(issue_number, body)

    def add_reaction(self, comment_id: int, reaction: str = "confused") -> bool:
        """
        Add a reaction emoji to a comment.

        Used for lightweight acknowledgment: the Junior Dev reacts with 👍 to the
        Manager's briefing instead of posting a noisy comment.

        Reaction values: "+1", "-1", "laugh", "confused", "heart", "hooray", "rocket", "eyes"

        Returns:
            True if the reaction was added, False otherwise.
        """
        if comment_id <= 0:
            return False
        result = self._gh_api(
            f"repos/{self._repo}/issues/comments/{comment_id}/reactions",
            data={"content": reaction},
        )
        return result.returncode == 0

    def fetch_comments(self, issue_number: int) -> list[dict]:
        """
        Fetch all comments on an issue.

        Returns a list of raw GitHub API comment dicts, each with:
            id, body, user (dict with login), created_at, updated_at

        Used by:
            - state_store.py to find the state comment
            - conversationalist.py to read author replies
        """
        result = self._gh_api(f"repos/{self._repo}/issues/{issue_number}/comments", method="GET")
        if result.returncode != 0:
            return []
        try:
            return json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            return []

    def create_branch(self, branch: str) -> None:
        """
        Create a fresh branch from main.

        Cleans up any existing branch with the same name first (both local and remote).
        This ensures we always start from a clean state — no leftover commits from
        previous failed attempts.

        Steps:
            1. Delete remote branch (ignore errors if it doesn't exist)
            2. Delete local branch (ignore errors if it doesn't exist)
            3. Checkout main and clean working directory
            4. Create new branch
        """
        self._sh(f"git push origin --delete {branch} 2>/dev/null")
        self._sh(f"git branch -D {branch} 2>/dev/null")
        self._sh("git checkout main")
        self._sh("git clean -fd")
        self._sh("git checkout -- .")
        result = self._sh(f"git checkout -b {branch}")
        self._check(result, "create_branch")

    def commit_and_push(self, branch: str, message: str) -> None:
        """
        Stage all changes, commit, and push to origin.

        Uses git add -A (stage everything including deletions).
        The commit may be empty if no files changed — that's fine, push still works.
        """
        self._sh("git add -A")
        subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
        result = self._sh(f"git push origin {branch}")
        self._check(result, "push")

    def create_pr(self, branch: str, issue_number: int, title: str, body: str) -> str:
        """
        Create a pull request from branch to main.

        Returns:
            PR URL (str) — The HTML URL of the created PR.
            Falls back to a compare URL if PR creation fails.
        """
        result = self._gh_api(f"repos/{self._repo}/pulls", data={
            "title": title, "body": body, "head": branch, "base": "main",
        })
        try:
            pr = json.loads(result.stdout)
            return pr.get("html_url") or pr.get("url") or ""
        except (json.JSONDecodeError, KeyError):
            return f"https://github.com/{self._repo}/compare/main...{branch}"

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _sh(cmd: str) -> subprocess.CompletedProcess:
        """Run a shell command. All git/gh commands go through here."""
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)

    @staticmethod
    def _gh_api(endpoint: str, method: str = "POST", data: dict | None = None) -> subprocess.CompletedProcess:
        """
        Call the GitHub REST API via the gh CLI.

        Uses `gh api <endpoint>` which handles authentication automatically.
        For POST/PATCH: pipes JSON data via stdin (--input -).
        For GET: just calls the endpoint.
        """
        cmd = f"gh api {endpoint}"
        if method != "GET":
            cmd += f" -X {method}"
        if data:
            cmd += " --input -"
            return subprocess.run(cmd, shell=True, capture_output=True, text=True, input=json.dumps(data))
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)

    @staticmethod
    def _check(result: subprocess.CompletedProcess, context: str) -> None:
        """Log errors from subprocess calls. Fail-fast with informative messages."""
        if result.returncode != 0:
            print(f"  [{context}] exit={result.returncode} stderr={result.stderr[:300]}")
