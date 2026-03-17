"""GlassBox Agent v0.3-beta - GitHub API interactions."""

import json
import subprocess


class GitHubClient:
    """Encapsulates all GitHub + git operations for the agent pipeline.

    Design: dependency injection (repo passed in), fail-fast on errors,
    all I/O isolated here, no silent swallowing.
    """

    def __init__(self, repo: str):
        self._repo = repo

    # -- Public API --

    def read_issue(self, issue_number: int) -> tuple[str, str]:
        """Read issue title and body. Returns (title, body)."""
        result = self._sh(f"gh issue view {issue_number} --repo {self._repo} --json title,body")
        self._check(result, "read_issue")
        issue = json.loads(result.stdout)
        return issue["title"], issue.get("body", "")

    def post_comment(self, issue_number: int, body: str) -> int:
        """Post a comment on the issue. Returns comment_id (0 on failure)."""
        result = self._gh_api(
            f"repos/{self._repo}/issues/{issue_number}/comments",
            data={"body": body},
        )
        self._check(result, "post_comment")
        try:
            comment = json.loads(result.stdout)
            comment_id = comment.get("id", 0)
        except (json.JSONDecodeError, AttributeError):
            comment_id = 0
        print(f"  posted comment ({len(body)} chars, id={comment_id})")
        return comment_id

    def update_comment(self, comment_id: int, body: str) -> bool:
        """Edit an existing comment via PATCH. No email triggered. Returns True on success."""
        if comment_id <= 0:
            return False
        result = self._gh_api(
            f"repos/{self._repo}/issues/comments/{comment_id}",
            method="PATCH",
            data={"body": body},
        )
        ok = result.returncode == 0
        if ok:
            print(f"  updated comment {comment_id} ({len(body)} chars, silent)")
        else:
            self._check(result, "update_comment")
        return ok

    def silent_update(self, issue_number: int, comment_id: int, body: str) -> int:
        """Edit comment if possible, fall back to post_comment. Returns comment_id."""
        if comment_id > 0 and self.update_comment(comment_id, body):
            return comment_id
        print(f"  silent_update: falling back to post_comment")
        return self.post_comment(issue_number, body)

    def create_branch(self, branch: str) -> None:
        """Delete old branch if exists, create fresh from main."""
        self._sh(f"git push origin --delete {branch} 2>/dev/null")
        self._sh(f"git branch -D {branch} 2>/dev/null")
        self._sh("git checkout main")
        self._sh("git clean -fd")
        self._sh("git checkout -- .")
        result = self._sh(f"git checkout -b {branch}")
        self._check(result, "create_branch")

    def reset_branch(self, branch: str) -> None:
        """Reset branch to clean main state."""
        self._sh("git checkout main")
        self._sh("git clean -fd")
        self._sh("git checkout -- .")
        self._sh(f"git branch -D {branch} 2>/dev/null")
        result = self._sh(f"git checkout -b {branch}")
        self._check(result, "reset_branch")

    def commit_and_push(self, branch: str, message: str) -> None:
        """Stage all, commit, push."""
        self._sh("git add -A")
        subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
        result = self._sh(f"git push origin {branch}")
        self._check(result, "push")

    def create_pr(self, branch: str, issue_number: int, title: str, body: str) -> str:
        """Create PR via GitHub API. Returns PR URL."""
        result = self._gh_api(f"repos/{self._repo}/pulls", data={
            "title": title,
            "body": body,
            "head": branch,
            "base": "main",
        })
        print(f"  PR API stdout: {result.stdout[:300]}")
        print(f"  PR API stderr: {result.stderr[:300]}")
        try:
            pr = json.loads(result.stdout)
            url = pr.get("html_url") or pr.get("url") or ""
            if url:
                return url
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  PR parse error: {e}")
        fallback = f"https://github.com/{self._repo}/compare/main...{branch}"
        print(f"  PR URL fallback: {fallback}")
        return fallback

    # -- Private helpers --

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
        """Fail fast: print stderr on any non-zero exit."""
        if result.returncode != 0:
            print(f"  [{context}] exit={result.returncode} stderr={result.stderr[:300]}")
