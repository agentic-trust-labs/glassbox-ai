"""Coder settings - all from env vars with sensible defaults."""
import os


def load_settings(issue_body="", repo_root=""):
    return {
        "model": os.environ.get("GLASSBOX_MODEL", "anthropic/claude-sonnet-4-20250514"),
        "step_limit": int(os.environ.get("GLASSBOX_STEP_LIMIT", "30")),
        "cost_limit": float(os.environ.get("GLASSBOX_COST_LIMIT", "3.0")),
        "max_retries": int(os.environ.get("GLASSBOX_MAX_RETRIES", "2")),
        "repo_root": repo_root or os.environ.get("GLASSBOX_REPO_ROOT", os.getcwd()),
        "task": issue_body,
    }
