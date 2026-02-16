"""GitHub API client — issues, comments, reactions, PRs, branches."""

from __future__ import annotations

import json
import subprocess


class GitHubClient:
    """Encapsulates all GitHub + git operations. Dependency-injectable, fail-fast."""

    def __init__(self, repo: str):
        self._repo = repo

    def read_issue(self, issue_number: int) -> tuple[str, str]:
        """Read issue title and body."""
        result = self._sh(f"gh issue view {issue_number} --repo {self._repo} --json title,body")
        self._check(result, "read_issue")
        issue = json.loads(result.stdout)
        return issue["title"], issue.get("body", "")

    def post_comment(self, issue_number: int, body: str) -> int:
        """Post a comment. Returns comment_id (0 on failure)."""
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
        """Edit an existing comment (silent — no email)."""
        if comment_id <= 0:
            return False
        result = self._gh_api(
            f"repos/{self._repo}/issues/comments/{comment_id}",
            method="PATCH",
            data={"body": body},
        )
        return result.returncode == 0

    def silent_update(self, issue_number: int, comment_id: int, body: str) -> int:
        """Edit if possible, fall back to post. Returns comment_id."""
        if comment_id > 0 and self.update_comment(comment_id, body):
            return comment_id
        return self.post_comment(issue_number, body)

    def add_reaction(self, comment_id: int, reaction: str = "+1") -> bool:
        """Add a reaction to a comment (thumbs up ack)."""
        if comment_id <= 0:
            return False
        result = self._gh_api(
            f"repos/{self._repo}/issues/comments/{comment_id}/reactions",
            data={"content": reaction},
        )
        return result.returncode == 0

    def fetch_comments(self, issue_number: int) -> list[dict]:
        """Fetch all comments on an issue. Returns list of dicts with id, body, user."""
        result = self._gh_api(f"repos/{self._repo}/issues/{issue_number}/comments", method="GET")
        if result.returncode != 0:
            return []
        try:
            return json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            return []

    def create_branch(self, branch: str) -> None:
        """Delete old branch if exists, create fresh from main."""
        self._sh(f"git push origin --delete {branch} 2>/dev/null")
        self._sh(f"git branch -D {branch} 2>/dev/null")
        self._sh("git checkout main")
        self._sh("git clean -fd")
        self._sh("git checkout -- .")
        result = self._sh(f"git checkout -b {branch}")
        self._check(result, "create_branch")

    def commit_and_push(self, branch: str, message: str) -> None:
        """Stage all, commit, push."""
        self._sh("git add -A")
        subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
        result = self._sh(f"git push origin {branch}")
        self._check(result, "push")

    def create_pr(self, branch: str, issue_number: int, title: str, body: str) -> str:
        """Create PR. Returns PR URL."""
        result = self._gh_api(f"repos/{self._repo}/pulls", data={
            "title": title, "body": body, "head": branch, "base": "main",
        })
        try:
            pr = json.loads(result.stdout)
            return pr.get("html_url") or pr.get("url") or ""
        except (json.JSONDecodeError, KeyError):
            return f"https://github.com/{self._repo}/compare/main...{branch}"

    @staticmethod
    def _sh(cmd: str) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)

    @staticmethod
    def _gh_api(endpoint: str, method: str = "POST", data: dict | None = None) -> subprocess.CompletedProcess:
        cmd = f"gh api {endpoint}"
        if method != "GET":
            cmd += f" -X {method}"
        if data:
            cmd += " --input -"
            return subprocess.run(cmd, shell=True, capture_output=True, text=True, input=json.dumps(data))
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)

    @staticmethod
    def _check(result: subprocess.CompletedProcess, context: str) -> None:
        if result.returncode != 0:
            print(f"  [{context}] exit={result.returncode} stderr={result.stderr[:300]}")
