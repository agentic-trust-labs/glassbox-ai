"""Abuse prevention - per-installation daily rate limiting.

Exempt orgs get unlimited runs. Everyone else gets a daily cap.
Uses in-memory storage (resets on deploy/restart, which is fine for abuse prevention).
"""

from __future__ import annotations

import logging
from datetime import date, timezone, datetime
from typing import Any

log = logging.getLogger("glassbox.rate_limiter")

# Default configuration
DEFAULT_DAILY_LIMIT = 20
DEFAULT_EXEMPT_ORGS: set[str] = {"agentic-trust-labs"}


class RateLimiter:
    """Per-installation daily rate limiter with org exemptions."""

    def __init__(
        self,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
        exempt_orgs: set[str] | None = None,
    ):
        self._daily_limit = daily_limit
        self._exempt_orgs = exempt_orgs if exempt_orgs is not None else DEFAULT_EXEMPT_ORGS
        # {installation_id: {"date": date_str, "count": int, "org": str}}
        self._usage: dict[int, dict[str, Any]] = {}

    @property
    def daily_limit(self) -> int:
        return self._daily_limit

    @property
    def exempt_orgs(self) -> set[str]:
        return self._exempt_orgs

    def _today(self) -> str:
        """Current UTC date as string. Separated for testability."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _get_usage(self, installation_id: int) -> dict[str, Any]:
        """Get or create usage record, auto-resetting on new day."""
        today = self._today()
        record = self._usage.get(installation_id)
        if record is None or record["date"] != today:
            record = {"date": today, "count": 0, "org": record["org"] if record else ""}
            self._usage[installation_id] = record
        return record

    def check(self, installation_id: int, org: str) -> tuple[bool, int, int]:
        """Check if this installation can proceed.

        Returns:
            (allowed, used_today, daily_limit)
        """
        org_lower = org.lower()

        # Exempt orgs always pass
        if org_lower in {o.lower() for o in self._exempt_orgs}:
            return True, 0, self._daily_limit

        record = self._get_usage(installation_id)
        record["org"] = org
        return record["count"] < self._daily_limit, record["count"], self._daily_limit

    def consume(self, installation_id: int, org: str) -> tuple[bool, int, int]:
        """Check AND consume one unit if allowed.

        Returns:
            (allowed, used_today_after, daily_limit)
        """
        # Exempt orgs: always allowed, never tracked
        org_lower = org.lower()
        if org_lower in {o.lower() for o in self._exempt_orgs}:
            return True, 0, self._daily_limit

        allowed, used, limit = self.check(installation_id, org)
        if not allowed:
            log.warning(
                f"[rate_limit] BLOCKED installation={installation_id} org={org} "
                f"used={used}/{limit}"
            )
            return False, used, limit

        record = self._get_usage(installation_id)
        record["count"] += 1
        record["org"] = org
        remaining = limit - record["count"]

        log.info(
            f"[rate_limit] OK installation={installation_id} org={org} "
            f"used={record['count']}/{limit} remaining={remaining}"
        )
        return True, record["count"], limit

    def get_stats(self) -> dict[str, Any]:
        """Return current rate limiter stats for the health endpoint."""
        today = self._today()
        active = {
            iid: {"org": r["org"], "used": r["count"], "limit": self._daily_limit}
            for iid, r in self._usage.items()
            if r["date"] == today and r["count"] > 0
        }
        return {
            "daily_limit": self._daily_limit,
            "exempt_orgs": sorted(self._exempt_orgs),
            "active_today": active,
        }

    def format_limit_message(self, org: str, used: int, limit: int) -> str:
        """Format a user-friendly rate limit message for posting as a GitHub comment."""
        return (
            f"⚠️ **Rate Limit Reached**\n\n"
            f"The **{org}** organization has used **{used}/{limit}** agent runs today.\n\n"
            f"The daily limit resets at **midnight UTC**. "
            f"To request a higher limit, contact us at "
            f"[agentic-trust-labs/glassbox-ai](https://github.com/agentic-trust-labs/glassbox-ai/issues)."
        )
