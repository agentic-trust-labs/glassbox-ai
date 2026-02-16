"""GlassBox Agent - GitHub App webhook server.

Receives GitHub webhook events, authenticates as the GitHub App,
and runs the agent pipeline on the target repo.

Deploy to Railway/Render/Fly.io. Set these env vars:
    GITHUB_APP_ID        - GitHub App ID
    GITHUB_APP_PRIVATE_KEY - GitHub App private key (PEM, newlines as \n)
    GITHUB_WEBHOOK_SECRET  - Webhook secret for signature verification
    OPENAI_API_KEY         - OpenAI API key for the agent
"""

import hashlib
import hmac
import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from auth import get_installation_token

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("glassbox-app")

# ── Config ──────────────────────────────────────────────────────────

APP_ID = os.environ.get("GITHUB_APP_ID", "")
PRIVATE_KEY = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
AGENT_LABEL = "glassbox-agent"
PORT = int(os.environ.get("PORT", "8080"))


# ── App ─────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("GlassBox Agent webhook server starting")
    log.info(f"  APP_ID={APP_ID[:6]}... WEBHOOK_SECRET={'set' if WEBHOOK_SECRET else 'NOT SET'}")
    yield
    log.info("Shutting down")


app = FastAPI(title="GlassBox Agent", lifespan=lifespan)


# ── Signature verification ──────────────────────────────────────────


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify X-Hub-Signature-256 from GitHub."""
    if not WEBHOOK_SECRET:
        return True  # skip in dev
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Webhook endpoint ────────────────────────────────────────────────


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
):
    body = await request.body()

    # Verify signature
    if WEBHOOK_SECRET and not verify_signature(body, x_hub_signature_256 or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = x_github_event

    # Route to handler
    if event == "issues" and payload.get("action") == "labeled":
        label = payload.get("label", {}).get("name", "")
        if label == AGENT_LABEL:
            background_tasks.add_task(handle_issue, payload)
            return {"status": "queued", "event": "issue_labeled"}

    elif event == "issue_comment" and payload.get("action") == "created":
        comment_body = payload.get("comment", {}).get("body", "")
        if "@glassbox-agent" in comment_body or "@glassbox_agent" in comment_body:
            # Don't respond to our own comments
            sender = payload.get("sender", {}).get("login", "")
            if "glassbox" not in sender.lower() and "[bot]" not in sender:
                background_tasks.add_task(handle_comment, payload)
                return {"status": "queued", "event": "issue_comment"}

    elif event == "installation":
        action = payload.get("action")
        log.info(f"Installation {action}: {payload.get('installation', {}).get('account', {}).get('login')}")
        return {"status": "ok", "event": f"installation_{action}"}

    return {"status": "ignored"}


@app.get("/health")
async def health():
    return {"status": "ok", "app_id": APP_ID[:6] if APP_ID else "not set"}


# ── Handlers ────────────────────────────────────────────────────────


async def handle_issue(payload: dict):
    """Handle issue labeled with glassbox-agent."""
    installation_id = payload["installation"]["id"]
    repo_full = payload["repository"]["full_name"]
    issue_number = payload["issue"]["number"]
    clone_url = payload["repository"]["clone_url"]

    log.info(f"[issue] {repo_full}#{issue_number} - labeled {AGENT_LABEL}")
    await run_agent(installation_id, repo_full, clone_url, issue_number)


async def handle_comment(payload: dict):
    """Handle issue comment mentioning @glassbox-agent."""
    installation_id = payload["installation"]["id"]
    repo_full = payload["repository"]["full_name"]
    issue_number = payload["issue"]["number"]
    clone_url = payload["repository"]["clone_url"]
    comment_id = payload["comment"]["id"]

    log.info(f"[comment] {repo_full}#{issue_number} - @glassbox-agent mentioned")
    await run_agent(
        installation_id, repo_full, clone_url, issue_number,
        comment_id=comment_id,
    )


# ── Agent runner ────────────────────────────────────────────────────


async def run_agent(
    installation_id: int,
    repo_full: str,
    clone_url: str,
    issue_number: int,
    comment_id: int = None,
):
    """Clone repo, run GlassBox Agent, clean up."""
    # Get installation token
    token = await get_installation_token(APP_ID, PRIVATE_KEY, installation_id)
    if not token:
        log.error(f"[agent] Failed to get installation token for {repo_full}")
        return

    workdir = tempfile.mkdtemp(prefix="glassbox-")
    try:
        # Post ack comment
        log.info(f"[agent] Posting ack on {repo_full}#{issue_number}")
        ack_result = subprocess.run(
            [
                "gh", "api",
                f"repos/{repo_full}/issues/{issue_number}/comments",
                "-f", f"body=🤖 **GlassBox Agent** picked up **#{issue_number}**\n\nAnalyzing and generating fix...\n\n_This may take 30-60 seconds._",
            ],
            capture_output=True, text=True,
            env={**os.environ, "GH_TOKEN": token},
        )
        ack_comment_id = ""
        if ack_result.returncode == 0:
            import json
            ack_comment_id = str(json.loads(ack_result.stdout).get("id", ""))

        # Clone target repo
        auth_url = clone_url.replace("https://", f"https://x-access-token:{token}@")
        log.info(f"[agent] Cloning {repo_full}")
        subprocess.run(
            ["git", "clone", "--depth", "1", auth_url, "repo"],
            cwd=workdir, capture_output=True, check=True,
        )

        repo_dir = os.path.join(workdir, "repo")

        # Agent code is baked into the Docker image at /app/src
        # Only install target repo deps if present
        target_reqs = os.path.join(repo_dir, "requirements.txt")
        if os.path.exists(target_reqs):
            log.info("[agent] Installing target repo dependencies")
            subprocess.run(
                ["pip", "install", "-q", "-r", target_reqs],
                capture_output=True,
            )

        # Configure git in repo dir
        subprocess.run(
            ["git", "config", "user.name", "glassbox-agent[bot]"],
            cwd=repo_dir, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "noreply@glassbox-agent.dev"],
            cwd=repo_dir, capture_output=True,
        )

        # Run the agent
        cmd = ["python", "-m", "glassbox_agent.cli", str(issue_number)]
        if comment_id:
            cmd.extend(["--comment-id", str(comment_id)])

        env = {
            **os.environ,
            "OPENAI_API_KEY": OPENAI_API_KEY,
            "GH_TOKEN": token,
            "ACK_COMMENT_ID": ack_comment_id,
            "PYTHONPATH": os.environ.get("PYTHONPATH", "/app/src"),
            "GITHUB_REPOSITORY": repo_full,
        }

        log.info(f"[agent] Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, cwd=repo_dir, env=env,
            capture_output=True, text=True, timeout=300,
        )

        if result.returncode == 0:
            log.info(f"[agent] Success on {repo_full}#{issue_number}")
        else:
            log.error(f"[agent] Failed on {repo_full}#{issue_number}")
            log.error(f"[agent] stdout: {result.stdout[-500:]}")
            log.error(f"[agent] stderr: {result.stderr[-500:]}")

            # Post failure comment
            subprocess.run(
                [
                    "gh", "api",
                    f"repos/{repo_full}/issues/{issue_number}/comments",
                    "-f", f"body=🦉 **GlassBox Manager**\n\nAgent encountered an error. Logs have been captured for analysis.\n\n`{result.stderr[-200:]}`",
                ],
                capture_output=True,
                env={**os.environ, "GH_TOKEN": token},
            )

    except subprocess.TimeoutExpired:
        log.error(f"[agent] Timeout on {repo_full}#{issue_number}")
    except Exception as e:
        log.error(f"[agent] Exception on {repo_full}#{issue_number}: {e}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        log.info(f"[agent] Cleaned up {workdir}")


# ── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
