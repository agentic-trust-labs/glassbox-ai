"""App factory - wires all modules together, manages lifecycle."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth import AppAuth
from app.config import Settings, load_settings
from app.github_api import GitHubAPI
from app.handlers import configure as configure_handlers
from app.rate_limiter import RateLimiter
from app.runner import AgentRunner
from app.webhook import configure as configure_webhook
from app.webhook import router as webhook_router

log = logging.getLogger("glassbox.main")

# Module-level state (set during lifespan)
_settings: Settings = None
_runner: AgentRunner = None
_rate_limiter: RateLimiter = None
_auth: AppAuth = None
_start_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate config, wire modules. Shutdown: close connections."""
    global _settings, _runner, _rate_limiter, _auth, _start_time

    # Load and validate config (fails fast if missing)
    _settings = load_settings()
    _start_time = time.time()

    logging.basicConfig(
        level=getattr(logging, _settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Starting GlassBox Agent webhook server")
    log.info(f"  app_id={_settings.github_app_id}")
    log.info(f"  webhook_secret={'configured' if _settings.github_webhook_secret else 'NOT SET'}")
    log.info(f"  max_concurrent_runs={_settings.max_concurrent_runs}")
    log.info(f"  agent_timeout={_settings.agent_timeout}s")

    # Initialize auth, runner, and rate limiter
    _auth = AppAuth(
        app_id=_settings.github_app_id,
        private_key=_settings.github_app_private_key,
    )
    _runner = AgentRunner(settings=_settings, auth=_auth)
    _rate_limiter = RateLimiter(
        daily_limit=_settings.rate_limit_daily,
        exempt_orgs=set(_settings.rate_limit_exempt_orgs.split(",")) if _settings.rate_limit_exempt_orgs else {"agentic-trust-labs"},
    )
    log.info(f"  rate_limit={_rate_limiter.daily_limit}/day exempt={_rate_limiter.exempt_orgs}")

    # Wire modules
    configure_webhook(_settings.github_webhook_secret, dispatch_fn=_dispatch)
    configure_handlers(
        run_agent_fn=_runner.run,
        rate_limiter=_rate_limiter,
        post_comment_fn=_post_rate_limit_comment,
    )

    log.info("Server ready")
    yield

    # Shutdown
    log.info("Shutting down...")
    await _auth.close()
    active = _runner.stats["active_runs"]
    if active > 0:
        log.warning(f"{active} agent runs still active during shutdown")
    log.info("Shutdown complete")


async def _dispatch(event, payload, background_tasks):
    """Bridge between webhook router and handlers module."""
    from app.handlers import dispatch
    return await dispatch(event, payload, background_tasks)


async def _post_rate_limit_comment(installation_id: int, repo: str, issue_number: int, body: str):
    """Post a rate-limit comment using a fresh installation token."""
    token = await _auth.get_installation_token(installation_id)
    if not token:
        log.error(f"Cannot post rate limit comment: no token for installation {installation_id}")
        return
    api = GitHubAPI(token)
    try:
        await api.post_comment(repo, issue_number, body)
    finally:
        await api.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="GlassBox Agent",
        description="GitHub App webhook server for autonomous code fixing",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Mount webhook router
    app.include_router(webhook_router)

    # Health endpoint
    @app.get("/health")
    async def health():
        runner_stats = _runner.stats if _runner else {}
        uptime = time.time() - _start_time if _start_time else 0
        return {
            "status": "ok",
            "version": "0.4.0-rate-limiter",
            "uptime_seconds": int(uptime),
            "uptime_human": _format_uptime(uptime),
            "app_id": _settings.github_app_id if _settings else "not loaded",
            "webhook_secret": "configured" if (_settings and _settings.github_webhook_secret) else "not set",
            "runner": runner_stats,
            "rate_limiter": _rate_limiter.get_stats() if _rate_limiter else {},
        }

    return app


def _format_uptime(seconds: float) -> str:
    """Format uptime as human-readable string."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


# Create the app instance (used by uvicorn)
app = create_app()


if __name__ == "__main__":
    import uvicorn
    port = 8080
    try:
        settings = load_settings()
        port = settings.port
    except Exception:
        pass
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
