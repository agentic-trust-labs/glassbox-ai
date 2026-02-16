"""Event dispatch - routes webhook events to the appropriate handler."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import BackgroundTasks

from app.rate_limiter import RateLimiter

log = logging.getLogger("glassbox.handlers")

AGENT_LABEL = "glassbox-agent"
BOT_IDENTIFIERS = ("glassbox", "[bot]")

# Set by main.py during startup
_run_agent_fn = None  # async callable
_rate_limiter: RateLimiter | None = None
_post_comment_fn = None  # async callable(installation_id, repo, issue_number, body)


def configure(run_agent_fn, rate_limiter: RateLimiter = None, post_comment_fn=None):
    """Configure handlers module. Called once during app startup."""
    global _run_agent_fn, _rate_limiter, _post_comment_fn
    _run_agent_fn = run_agent_fn
    _rate_limiter = rate_limiter
    _post_comment_fn = post_comment_fn


def _is_bot(sender: str) -> bool:
    """Check if the sender is one of our bot accounts."""
    sender_lower = sender.lower()
    return any(ident in sender_lower for ident in BOT_IDENTIFIERS)


def _extract_common(payload: dict) -> dict[str, Any]:
    """Extract common fields from any issue/comment webhook payload."""
    return {
        "installation_id": payload["installation"]["id"],
        "repo": payload["repository"]["full_name"],
        "issue_number": payload["issue"]["number"],
        "issue_title": payload["issue"].get("title", ""),
        "sender": payload.get("sender", {}).get("login", ""),
    }


async def _check_rate_limit(ctx: dict[str, Any], payload: dict) -> dict | None:
    """Check rate limit. Returns error response dict if blocked, None if OK."""
    if not _rate_limiter:
        return None

    org = payload.get("organization", {}).get("login", "")
    if not org:
        org = payload.get("repository", {}).get("owner", {}).get("login", "")

    allowed, used, limit = _rate_limiter.consume(ctx["installation_id"], org)
    if allowed:
        return None

    # Rate limited - post comment and return blocked status
    msg = _rate_limiter.format_limit_message(org, used, limit)
    if _post_comment_fn:
        try:
            await _post_comment_fn(
                ctx["installation_id"], ctx["repo"], ctx["issue_number"], msg
            )
        except Exception as e:
            log.error(f"[dispatch] Failed to post rate limit comment: {e}")

    return {
        "status": "rate_limited",
        "event": "blocked",
        "issue": ctx["issue_number"],
        "used": used,
        "limit": limit,
    }


async def dispatch(event: str, payload: dict, background_tasks: BackgroundTasks) -> dict:
    """Route a webhook event to the correct handler. Returns response dict."""

    if event == "issues" and payload.get("action") == "labeled":
        label = payload.get("label", {}).get("name", "")
        if label == AGENT_LABEL:
            ctx = _extract_common(payload)
            blocked = await _check_rate_limit(ctx, payload)
            if blocked:
                return blocked
            log.info(f"[dispatch] Issue labeled: {ctx['repo']}#{ctx['issue_number']} '{ctx['issue_title']}'")
            background_tasks.add_task(_run_agent_fn, **ctx)
            return {"status": "queued", "event": "issue_labeled", "issue": ctx["issue_number"]}

    elif event == "issue_comment" and payload.get("action") == "created":
        body = payload.get("comment", {}).get("body", "")
        sender = payload.get("sender", {}).get("login", "")

        if ("@glassbox-agent" in body or "@glassbox_agent" in body) and not _is_bot(sender):
            ctx = _extract_common(payload)
            ctx["comment_id"] = payload["comment"]["id"]
            blocked = await _check_rate_limit(ctx, payload)
            if blocked:
                return blocked
            log.info(f"[dispatch] Mention by {sender}: {ctx['repo']}#{ctx['issue_number']}")
            background_tasks.add_task(_run_agent_fn, **ctx)
            return {"status": "queued", "event": "issue_comment", "issue": ctx["issue_number"]}

    elif event == "installation":
        action = payload.get("action", "unknown")
        account = payload.get("installation", {}).get("account", {}).get("login", "unknown")
        repos = payload.get("repositories", [])
        repo_names = [r.get("full_name", r.get("name", "?")) for r in repos[:5]]
        log.info(f"[dispatch] Installation {action} by {account}: {repo_names}")
        return {"status": "ok", "event": f"installation_{action}", "account": account}

    return {"status": "ignored", "event": event}
