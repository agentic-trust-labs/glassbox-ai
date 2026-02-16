"""GitHub App authentication - JWT generation and installation token exchange."""

import time
from typing import Optional

import httpx
import jwt


def generate_jwt(app_id: str, private_key: str) -> str:
    """Generate a JWT for GitHub App authentication (RS256, 10 min expiry)."""
    now = int(time.time())
    payload = {
        "iat": now - 60,  # issued at (60s clock skew buffer)
        "exp": now + (10 * 60),  # expires in 10 minutes
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(
    app_id: str, private_key: str, installation_id: int
) -> Optional[str]:
    """Exchange JWT for an installation access token."""
    token = generate_jwt(app_id, private_key)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if resp.status_code == 201:
            return resp.json()["token"]
        print(f"[auth] Failed to get installation token: {resp.status_code} {resp.text}")
        return None
