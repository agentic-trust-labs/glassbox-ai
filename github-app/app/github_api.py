"""Direct GitHub API calls via httpx. No gh CLI dependency."""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

log = logging.getLogger("glassbox.github")

GITHUB_API = "https://api.github.com"


class GitHubAPI:
    """Lightweight GitHub API client using installation tokens."""

    def __init__(self, token: str):
        self.token = token
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=GITHUB_API,
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    async def post_comment(self, repo: str, issue_number: int, body: str) -> Optional[int]:
        """Post a comment on an issue. Returns comment ID or None."""
        client = await self._ensure_client()
        try:
            resp = await client.post(
                f"/repos/{repo}/issues/{issue_number}/comments",
                json={"body": body},
            )
            if resp.status_code == 201:
                comment_id = resp.json()["id"]
                log.info(f"Posted comment {comment_id} on {repo}#{issue_number}")
                return comment_id
            log.error(f"Comment failed: {resp.status_code} {resp.text[:200]}")
            return None
        except httpx.HTTPError as e:
            log.error(f"Comment error on {repo}#{issue_number}: {e}")
            return None

    async def update_comment(self, repo: str, comment_id: int, body: str) -> bool:
        """Update an existing comment. Returns True on success."""
        client = await self._ensure_client()
        try:
            resp = await client.patch(
                f"/repos/{repo}/issues/comments/{comment_id}",
                json={"body": body},
            )
            return resp.status_code == 200
        except httpx.HTTPError as e:
            log.error(f"Update comment error: {e}")
            return False

    async def add_reaction(self, repo: str, issue_number: int, reaction: str = "eyes") -> bool:
        """Add a reaction to an issue."""
        client = await self._ensure_client()
        try:
            resp = await client.post(
                f"/repos/{repo}/issues/{issue_number}/reactions",
                json={"content": reaction},
            )
            return resp.status_code in (200, 201)
        except httpx.HTTPError:
            return False

    def clone_url(self, repo: str) -> str:
        """Get authenticated clone URL."""
        return f"https://x-access-token:{self.token}@github.com/{repo}.git"

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
