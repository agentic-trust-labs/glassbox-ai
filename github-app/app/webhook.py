"""Webhook endpoint with signature verification and event routing."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

log = logging.getLogger("glassbox.webhook")

router = APIRouter()

# Set by main.py during app startup
_webhook_secret: str = ""
_dispatch_fn = None  # async callable(event_type, payload)


def configure(webhook_secret: str, dispatch_fn):
    """Configure webhook module. Called once during app startup."""
    global _webhook_secret, _dispatch_fn
    _webhook_secret = webhook_secret
    _dispatch_fn = dispatch_fn


def _verify_signature(payload: bytes, signature: Optional[str]) -> bool:
    """Verify X-Hub-Signature-256 from GitHub using constant-time comparison."""
    if not _webhook_secret:
        log.warning("Webhook secret not set - skipping signature verification")
        return True
    if not signature:
        return False
    expected = "sha256=" + hmac.new(
        _webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
):
    """Receive and verify GitHub webhook events, dispatch to handlers."""
    body = await request.body()

    # Verify signature
    if not _verify_signature(body, x_hub_signature_256):
        log.warning(f"Invalid signature for delivery {x_github_delivery}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = x_github_event or "unknown"
    delivery_id = x_github_delivery or "unknown"

    log.info(f"Webhook received: event={event} delivery={delivery_id[:12]}")

    if _dispatch_fn is None:
        log.error("Dispatch function not configured")
        raise HTTPException(status_code=500, detail="Server not configured")

    result = await _dispatch_fn(event, payload, background_tasks)
    return result
