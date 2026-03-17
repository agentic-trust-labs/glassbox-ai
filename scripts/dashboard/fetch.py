"""Fetches issues, PRs, and workflow runs from GitHub API."""

import json
import subprocess
from typing import Dict, List, Tuple

from .config import REPO, WORKFLOW_NAME, AGENT_LABELS, AGENT_MENTIONS


class GitHubFetcher:
    """Fetches all agent-related data from the GitHub API via gh CLI."""

    def __init__(self, repo: str = REPO):
        self._repo = repo

    def _gh(self, endpoint: str, jq: str = "") -> str:
        cmd = ["gh", "api", endpoint, "--paginate"]
        if jq:
            cmd += ["--jq", jq]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[fetch] gh api error: {result.stderr[:200]}")
            return ""
        return result.stdout.strip()

    def fetch_issues(self) -> List[Dict]:
        """Fetch all issues (not PRs) from the repo."""
        raw = self._gh(
            f"repos/{self._repo}/issues?state=all&per_page=100&direction=asc",
            '.[] | select(.pull_request == null) | {number, title, state, created_at, labels: [.labels[].name], html_url}'
        )
        if not raw:
            return []
        issues = []
        for line in raw.strip().split("\n"):
            if line.strip():
                try:
                    issues.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return issues

    def fetch_prs(self) -> List[Dict]:
        """Fetch all PRs from the repo."""
        raw = self._gh(
            f"repos/{self._repo}/pulls?state=all&per_page=100&direction=asc",
            '.[] | {number, title, state, merged_at, head: .head.ref, html_url, body}'
        )
        if not raw:
            return []
        prs = []
        for line in raw.strip().split("\n"):
            if line.strip():
                try:
                    prs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return prs

    def fetch_workflow_runs(self) -> List[Dict]:
        """Fetch all Agent Fix workflow runs with timing data."""
        raw = self._gh(
            f"repos/{self._repo}/actions/runs?per_page=100",
            f'.workflow_runs[] | select(.name == "{WORKFLOW_NAME}") | '
            '{id, event, conclusion, created_at, display_title, html_url, '
            'run_started_at, updated_at}'
        )
        if not raw:
            return []
        runs = []
        for line in raw.strip().split("\n"):
            if line.strip():
                try:
                    run = json.loads(line)
                    # Calculate total duration in seconds
                    run["duration_s"] = self._calc_duration(
                        run.get("run_started_at"), run.get("updated_at")
                    )
                    runs.append(run)
                except json.JSONDecodeError:
                    continue
        return runs

    def fetch_run_jobs(self, run_id: int) -> List[Dict]:
        """Fetch jobs for a workflow run to get step-level timing."""
        raw = self._gh(
            f"repos/{self._repo}/actions/runs/{run_id}/jobs",
            '.jobs[] | {name, started_at, completed_at, steps: [.steps[] | {name, started_at, completed_at, conclusion}]}'
        )
        if not raw:
            return []
        jobs = []
        for line in raw.strip().split("\n"):
            if line.strip():
                try:
                    job = json.loads(line)
                    # Calculate step durations
                    for step in job.get("steps", []):
                        step["duration_s"] = self._calc_duration(
                            step.get("started_at"), step.get("completed_at")
                        )
                    jobs.append(job)
                except json.JSONDecodeError:
                    continue
        return jobs

    @staticmethod
    def _calc_duration(start: str, end: str) -> int:
        """Calculate duration in seconds between two ISO timestamps."""
        if not start or not end:
            return 0
        try:
            from datetime import datetime, timezone
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            s = datetime.strptime(start, fmt).replace(tzinfo=timezone.utc)
            e = datetime.strptime(end, fmt).replace(tzinfo=timezone.utc)
            return max(0, int((e - s).total_seconds()))
        except (ValueError, TypeError):
            return 0

    def fetch_issue_comments(self, issue_number: int) -> List[Dict]:
        """Fetch comments on a specific issue."""
        raw = self._gh(
            f"repos/{self._repo}/issues/{issue_number}/comments?per_page=100",
            '.[] | {user: .user.login, user_type: .user.type, created_at, body}'
        )
        if not raw:
            return []
        comments = []
        for line in raw.strip().split("\n"):
            if line.strip():
                try:
                    comments.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return comments

    def classify_issue(self, issue: Dict, prs: List[Dict]) -> Dict:
        """Classify an issue: trigger type, agent involvement, outcome."""
        labels = issue.get("labels", [])
        number = issue["number"]

        # Is this an agent-triggered issue?
        is_agent = any(lbl in AGENT_LABELS for lbl in labels)

        # Find linked PR
        linked_pr = None
        for pr in prs:
            body = pr.get("body") or ""
            branch = pr.get("head") or ""
            if f"#{number}" in body or f"issue-{number}" in branch:
                linked_pr = pr
                break

        # Determine trigger type
        trigger = "label" if is_agent else "none"

        # Determine outcome
        outcome = "not_triggered"
        if is_agent or linked_pr:
            if linked_pr:
                if linked_pr.get("merged_at"):
                    outcome = "merged"
                elif linked_pr["state"] == "closed":
                    outcome = "closed"
                else:
                    outcome = "open_pr"
            else:
                outcome = "failed"

        return {
            **issue,
            "is_agent": is_agent,
            "trigger": trigger,
            "linked_pr": linked_pr,
            "outcome": outcome,
        }

    def fetch_all(self) -> Dict:
        """Fetch everything and return a structured dict."""
        print("[fetch] Fetching issues...")
        issues = self.fetch_issues()
        print(f"[fetch] Got {len(issues)} issues")

        print("[fetch] Fetching PRs...")
        prs = self.fetch_prs()
        print(f"[fetch] Got {len(prs)} PRs")

        print("[fetch] Fetching workflow runs...")
        runs = self.fetch_workflow_runs()
        print(f"[fetch] Got {len(runs)} workflow runs")

        print("[fetch] Classifying issues...")
        classified = [self.classify_issue(i, prs) for i in issues]

        # Separate agent issues
        agent_issues = [i for i in classified if i["is_agent"] or i["outcome"] != "not_triggered"]

        # Fetch failure details for agent issues
        for issue in agent_issues:
            comments = self.fetch_issue_comments(issue["number"])
            # Find failure message
            failure_msg = ""
            for c in reversed(comments):
                body = c.get("body", "")
                if body.startswith("\u274c"):  # starts with red X emoji
                    failure_msg = body[:300]
                    break
            issue["failure_msg"] = failure_msg
            issue["comment_count"] = len(comments)
            # Check if @mention triggered
            for c in comments:
                body = c.get("body", "")
                if any(m in body for m in AGENT_MENTIONS) and c.get("user_type") == "User":
                    issue["trigger"] = "mention"
                    break

        # Fetch step-level timing for last 10 issue-event runs (for TAT dashboard)
        print("[fetch] Fetching step-level timing for recent runs...")
        issue_runs = [r for r in runs if r.get("event") == "issues" and r.get("conclusion") == "success"]
        issue_runs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        run_timings = []
        for run in issue_runs[:10]:
            jobs = self.fetch_run_jobs(run["id"])
            run_timings.append({
                "run_id": run["id"],
                "created_at": run.get("created_at", ""),
                "duration_s": run.get("duration_s", 0),
                "jobs": jobs,
            })
        print(f"[fetch] Got step timing for {len(run_timings)} runs")

        return {
            "issues": classified,
            "agent_issues": agent_issues,
            "prs": prs,
            "runs": runs,
            "run_timings": run_timings,
        }
