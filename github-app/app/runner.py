"""Agent runner - clones repo, executes the agent pipeline, cleans up.

Handles the full lifecycle of an agent run:
1. Acquire concurrency semaphore
2. Post ack comment on the issue
3. Clone target repo
4. Install target repo dependencies
5. Run glassbox.cli
6. Post error comment on failure
7. Clean up temp directory
8. Release semaphore
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional

from app.auth import AppAuth
from app.config import Settings
from app.github_api import GitHubAPI

log = logging.getLogger("glassbox.runner")


@dataclass
class RunContext:
    """Immutable context for a single agent run."""
    repo: str
    issue_number: int
    issue_title: str
    installation_id: int
    sender: str
    comment_id: Optional[int] = None


@dataclass
class AgentRunner:
    """Manages agent execution with concurrency control and lifecycle tracking."""

    settings: Settings
    auth: AppAuth
    _semaphore: asyncio.Semaphore = field(init=False)
    _active_runs: dict[str, dict] = field(default_factory=dict, init=False)
    _total_runs: int = field(default=0, init=False)
    _total_success: int = field(default=0, init=False)
    _total_failed: int = field(default=0, init=False)

    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_runs)

    @property
    def stats(self) -> dict:
        """Current runner statistics for health endpoint."""
        return {
            "active_runs": len(self._active_runs),
            "active_details": list(self._active_runs.values()),
            "max_concurrent": self.settings.max_concurrent_runs,
            "total_runs": self._total_runs,
            "total_success": self._total_success,
            "total_failed": self._total_failed,
        }

    async def run(
        self,
        installation_id: int,
        repo: str,
        issue_number: int,
        issue_title: str = "",
        sender: str = "",
        comment_id: int = None,
    ):
        """Execute an agent run with concurrency control."""
        ctx = RunContext(
            repo=repo,
            issue_number=issue_number,
            issue_title=issue_title,
            installation_id=installation_id,
            sender=sender,
            comment_id=comment_id,
        )
        run_key = f"{repo}#{issue_number}"

        # Check if already running for this issue
        if run_key in self._active_runs:
            log.warning(f"[runner] Already running for {run_key}, skipping")
            return

        async with self._semaphore:
            self._total_runs += 1
            self._active_runs[run_key] = {
                "repo": repo,
                "issue": issue_number,
                "started": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            }
            try:
                await self._execute(ctx)
                self._total_success += 1
            except Exception as e:
                self._total_failed += 1
                log.error(f"[runner] Unhandled error on {run_key}: {e}", exc_info=True)
            finally:
                self._active_runs.pop(run_key, None)

    async def _execute(self, ctx: RunContext):
        """Core execution: auth, clone, run, cleanup."""
        run_key = f"{ctx.repo}#{ctx.issue_number}"

        # Get installation token
        token = await self.auth.get_installation_token(ctx.installation_id)
        if not token:
            log.error(f"[runner] Auth failed for {run_key}")
            return

        api = GitHubAPI(token)
        workdir = tempfile.mkdtemp(prefix="glassbox-")

        try:
            # Post ack
            ack_body = (
                f"🤖 **GlassBox Agent** picked up **#{ctx.issue_number}**\n\n"
                f"Analyzing and generating fix...\n\n"
                f"_This may take 30-60 seconds._"
            )
            ack_id = await api.post_comment(ctx.repo, ctx.issue_number, ack_body)
            log.info(f"[runner] Ack posted on {run_key} (comment={ack_id})")

            # Clone target repo
            clone_url = api.clone_url(ctx.repo)
            log.info(f"[runner] Cloning {ctx.repo}")
            proc = await asyncio.to_thread(
                subprocess.run,
                ["git", "clone", "--depth", "1", clone_url, "repo"],
                cwd=workdir, capture_output=True, text=True,
            )
            if proc.returncode != 0:
                log.error(f"[runner] Clone failed: {proc.stderr[:300]}")
                await api.post_comment(ctx.repo, ctx.issue_number,
                    "🦉 **GlassBox Manager**\n\nFailed to clone repository.")
                return

            repo_dir = os.path.join(workdir, "repo")

            # Install target repo deps
            target_reqs = os.path.join(repo_dir, "requirements.txt")
            if os.path.exists(target_reqs):
                log.info(f"[runner] Installing {ctx.repo} dependencies")
                await asyncio.to_thread(
                    subprocess.run,
                    ["pip", "install", "-q", "-r", target_reqs],
                    capture_output=True,
                )

            # Configure git identity
            for cmd in [
                ["git", "config", "user.name", "glassbox-agent[bot]"],
                ["git", "config", "user.email", "noreply@glassbox-agent.dev"],
            ]:
                await asyncio.to_thread(
                    subprocess.run, cmd, cwd=repo_dir, capture_output=True,
                )

            # Build agent command
            agent_cmd = ["python", "-m", "glassbox.cli", str(ctx.issue_number)]
            if ctx.comment_id:
                agent_cmd.extend(["--comment-id", str(ctx.comment_id)])

            env = {
                **os.environ,
                "OPENAI_API_KEY": self.settings.openai_api_key,
                "GH_TOKEN": token,
                "ACK_COMMENT_ID": str(ack_id or ""),
                "PYTHONPATH": self.settings.agent_pythonpath,
                "GITHUB_REPOSITORY": ctx.repo,
            }

            # Run agent
            log.info(f"[runner] Executing agent on {run_key}")
            result = await asyncio.to_thread(
                subprocess.run,
                agent_cmd, cwd=repo_dir, env=env,
                capture_output=True, text=True,
                timeout=self.settings.agent_timeout,
            )

            if result.returncode == 0:
                log.info(f"[runner] Success on {run_key}")
            else:
                log.error(f"[runner] Agent failed on {run_key}")
                log.error(f"[runner] stderr: {result.stderr[-500:]}")
                error_snippet = result.stderr[-200:].replace("`", "'")
                await api.post_comment(ctx.repo, ctx.issue_number,
                    f"🦉 **GlassBox Manager**\n\n"
                    f"Agent encountered an error.\n\n```\n{error_snippet}\n```")

        except subprocess.TimeoutExpired:
            log.error(f"[runner] Timeout ({self.settings.agent_timeout}s) on {run_key}")
            await api.post_comment(ctx.repo, ctx.issue_number,
                "🦉 **GlassBox Manager**\n\nAgent timed out. The issue may be too complex for automated fixing.")

        except Exception as e:
            log.error(f"[runner] Exception on {run_key}: {e}", exc_info=True)
            try:
                await api.post_comment(ctx.repo, ctx.issue_number,
                    f"🦉 **GlassBox Manager**\n\nInternal error: `{str(e)[:200]}`")
            except Exception:
                pass

        finally:
            await api.close()
            shutil.rmtree(workdir, ignore_errors=True)
            log.info(f"[runner] Cleaned up {run_key}")
