"""GitHub App authentication with token caching.

Generates JWTs for app-level auth and caches installation tokens
to avoid redundant API calls (tokens are valid for 1 hour).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
import jwt

log = logging.getLogger("glassbox.auth")

GITHUB_API = "https://api.github.com"
TOKEN_TTL = 3300  # cache for 55 min (tokens valid for 60)


@dataclass
class _CachedToken:
    token: str
    expires_at: float


@dataclass
class AppAuth:
    """Handles GitHub App JWT generation and installation token exchange."""

    app_id: str
    private_key: str
    _client: httpx.AsyncClient = field(default=None, init=False, repr=False)
    _cache: dict[int, _CachedToken] = field(default_factory=dict, init=False, repr=False)

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=GITHUB_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    def _generate_jwt(self) -> str:
        """Generate a short-lived JWT for GitHub App authentication."""
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (10 * 60),
            "iss": self.app_id,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> Optional[str]:
        """Get an installation access token, using cache when possible."""
        # Check cache
        cached = self._cache.get(installation_id)
        if cached and cached.expires_at > time.time():
            return cached.token

        # Exchange JWT for installation token
        client = await self._ensure_client()
        token = self._generate_jwt()
        try:
            resp = await client.post(
                f"/app/installations/{installation_id}/access_tokens",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 201:
                data = resp.json()
                install_token = data["token"]
                self._cache[installation_id] = _CachedToken(
                    token=install_token,
                    expires_at=time.time() + TOKEN_TTL,
                )
                log.info(f"Installation token obtained for {installation_id}")
                return install_token

            log.error(f"Token exchange failed: {resp.status_code} {resp.text[:200]}")
            return None

        except httpx.HTTPError as e:
            log.error(f"Token exchange error: {e}")
            return None

    async def close(self):
        """Close the shared HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
