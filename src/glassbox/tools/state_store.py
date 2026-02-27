"""
GlassBox Tool — State Store
==============================

CORE TOOL. Requires owner approval to modify.

Purpose:
    Persist and load the state machine's current state and audit log so that
    the engine can resume after being paused (e.g., waiting for author response).

Why state persistence matters:
    The engine runs as a CLI command or webhook handler. When it hits
    "awaiting_author" state, the process EXITS. Hours or days later, when
    the author comments, a webhook fires and a NEW process starts. That new
    process needs to know: "What state was this issue in? What happened so far?"

    The state store solves this by saving the state after every engine.step().

Two backends (for now):

    1. GitHub Hidden Comment (default for GitHub Issues use case):
       Embeds state as a hidden HTML comment in the issue:
           <!-- glassbox-state: {"state": "awaiting_author", "audit": [...]} -->
       Pros: Zero infrastructure. State lives with the issue. Works with GitHub API.
       Cons: Limited size (GitHub comment body limit is ~65535 chars).

    2. JSON File (for local development and testing):
       Writes state to a JSON file: data/state/{issue_number}.json
       Pros: Simple. No API calls. Easy to inspect.
       Cons: Not shared across machines. Lost if the file is deleted.

    Future: SQLite, Redis, PostgreSQL backends for production use.

State format:
    {
        "issue_number": 42,
        "state": "awaiting_author",
        "audit": [
            {"timestamp": "...", "from_state": "classifying", "to_state": "easy_localizing", ...},
            ...
        ]
    }
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from typing import Any

from glassbox.core.models import AuditEntry


# ---------------------------------------------------------------------------
# The hidden HTML comment format for GitHub state embedding.
#
# This tag is invisible to users viewing the issue but readable via the API.
# The engine looks for this pattern in issue comments to resume state.
#
# Example:
#   <!-- glassbox-state: {"state":"awaiting_author","audit":[...]} -->
# ---------------------------------------------------------------------------
_STATE_TAG_RE = re.compile(r"<!--\s*glassbox-state:\s*(\{.*?\})\s*-->", re.DOTALL)


class GitHubStateStore:
    """
    Persist state as a hidden HTML comment in a GitHub issue.

    This is the default state store for the GitHub Issues use case.
    It uses the GitHub client tool to read/write comments.

    How it works:
        save() → Posts (or updates) a comment with <!-- glassbox-state: {...} -->
        load() → Fetches all comments, finds the one with the state tag, parses it.

    The comment is updated in-place (edit, not new comment) to avoid notification
    spam. GitHub sends an email for new comments but NOT for edits.
    """

    def __init__(self, github_client: Any):
        """
        Args:
            github_client → An instance of tools.github_client.GitHubClient.
                             We accept Any to avoid a hard import dependency.
        """
        self._github = github_client
        # Track the comment ID so we can update in-place instead of posting new.
        self._comment_ids: dict[int, int] = {}  # issue_number → comment_id

    def save(self, issue_number: int, state: str, audit: list[AuditEntry]) -> None:
        """
        Save the current state and audit log to a GitHub issue comment.

        If a state comment already exists for this issue, it's updated in-place.
        If not, a new comment is posted.

        The comment body looks like:
            <!-- glassbox-state: {"state":"easy_fixing","audit":[...]} -->
            *GlassBox is working on this issue. Current state: easy_fixing*
        """

        # Serialize the state and audit log to JSON.
        state_data = {
            "issue_number": issue_number,
            "state": state,
            "audit": [asdict(entry) for entry in audit],
        }
        state_json = json.dumps(state_data, separators=(",", ":"))

        # Build the comment body with hidden state tag + visible status line.
        body = f"<!-- glassbox-state: {state_json} -->\n"
        body += f"*GlassBox is working on this issue. Current state: `{state}`*"

        # Update existing comment or post new.
        comment_id = self._comment_ids.get(issue_number, 0)
        new_id = self._github.silent_update(issue_number, comment_id, body)
        self._comment_ids[issue_number] = new_id

    def load(self, issue_number: int) -> tuple[str, list[AuditEntry]]:
        """
        Load the state and audit log from a GitHub issue's comments.

        Scans all comments on the issue for the <!-- glassbox-state: ... --> tag.
        Uses the LAST matching comment (in case there are multiple from retries).

        Returns:
            (state, audit_log) — The saved state and audit entries.
            ("", []) if no state comment is found.
        """

        comments = self._github.fetch_comments(issue_number)

        # Scan comments in reverse order (latest first).
        for comment in reversed(comments):
            body = comment.get("body", "")
            match = _STATE_TAG_RE.search(body)
            if match:
                try:
                    data = json.loads(match.group(1))
                    state = data.get("state", "")
                    audit = [
                        AuditEntry(**entry)
                        for entry in data.get("audit", [])
                    ]
                    # Remember the comment ID for future updates.
                    self._comment_ids[issue_number] = comment.get("id", 0)
                    return state, audit
                except (json.JSONDecodeError, TypeError):
                    continue

        return "", []


class FileStateStore:
    """
    Persist state as a JSON file on disk.

    This is the state store for local development and testing.
    Files are saved to: {data_dir}/state/{issue_number}.json

    Simpler than GitHubStateStore — no API calls, no comment parsing.
    Useful when running the engine locally without GitHub integration.
    """

    def __init__(self, data_dir: str = "data"):
        """
        Args:
            data_dir → Base directory for state files. Default: "data/" in repo root.
        """
        self._state_dir = os.path.join(data_dir, "state")

    def save(self, issue_number: int, state: str, audit: list[AuditEntry]) -> None:
        """
        Save state to a JSON file.

        Creates the directory if it doesn't exist.
        Overwrites the file on each save (we only need the latest state).
        """

        os.makedirs(self._state_dir, exist_ok=True)
        file_path = os.path.join(self._state_dir, f"{issue_number}.json")

        state_data = {
            "issue_number": issue_number,
            "state": state,
            "audit": [asdict(entry) for entry in audit],
        }

        with open(file_path, "w") as f:
            json.dump(state_data, f, indent=2)

    def load(self, issue_number: int) -> tuple[str, list[AuditEntry]]:
        """
        Load state from a JSON file.

        Returns:
            (state, audit_log) — The saved state and audit entries.
            ("", []) if the file doesn't exist.
        """

        file_path = os.path.join(self._state_dir, f"{issue_number}.json")

        if not os.path.exists(file_path):
            return "", []

        with open(file_path) as f:
            data = json.load(f)

        state = data.get("state", "")
        audit = [AuditEntry(**entry) for entry in data.get("audit", [])]
        return state, audit
