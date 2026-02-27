"""
GlassBox Use Case — GitHub Issues Settings
=============================================

Configuration for the GitHub Issues use case.

This file is the ONLY place where use-case-specific configuration lives.
It provides defaults that work out of the box, but can be overridden via
environment variables or a local .env file.

Settings hierarchy (highest priority wins):
    1. Environment variables (GLASSBOX_MODEL, GLASSBOX_REPO, etc.)
    2. Values in this file (defaults)

This file is safe to .gitignore if you want private configuration:
    - Different model choices for your deployment
    - Custom temperature tuning
    - Organization-specific repo paths

Why not in core/settings.py:
    Core has NO settings. The engine takes transitions and pipeline as arguments —
    it doesn't read config files. Settings are a use-case concern, not a platform concern.
    A security-audit use case would have completely different settings (scan depth,
    vulnerability thresholds, etc.).
"""

from __future__ import annotations

import os


def load_settings() -> dict:
    """
    Load settings for the GitHub Issues use case.

    Returns a dict that gets passed to AgentContext.config, making all settings
    available to every agent via ctx.config["setting_name"].

    All settings have sensible defaults. Override via environment variables
    for deployment-specific configuration.

    Settings:
        repo                  → GitHub repository ("owner/name" format).
        model                 → Default LLM model for code generation and planning.
        model_classify        → Model for classification (cheaper, faster model is fine).
        model_localize        → Model for file localization (cheap is fine).
        review_model          → Model for adversarial review. MUST differ from `model`.
        temperature_classify  → Temperature for classification (low = deterministic).
        temperature_code      → Temperature for code generation (high = creative).
        temperature_review    → Temperature for review (low = precise).
        temperature_plan      → Temperature for planning (medium = balanced).
        temperature_localize  → Temperature for localization (low = deterministic).
        max_retries           → How many times to retry a failed step before asking author.
        templates_dir         → Path to bug pattern template YAML files.
        reflections_path      → Path to reflexion memory JSON file.
        repo_root             → Absolute path to the repository root (for tools).
    """

    # Determine the templates directory relative to this file's location.
    this_dir = os.path.dirname(os.path.abspath(__file__))
    default_templates_dir = os.path.join(this_dir, "templates")

    # Determine the repo root (4 levels up from this file: use_cases/github_issues/ → src/glassbox/ → src/ → repo root).
    default_repo_root = os.path.abspath(os.path.join(this_dir, "..", "..", "..", ".."))

    return {
        # --- Repository ---
        "repo": os.environ.get(
            "GITHUB_REPOSITORY",
            "agentic-trust-labs/glassbox-ai",
        ),

        # --- LLM Models ---
        # The primary model for code generation, planning, and analysis.
        "model": os.environ.get("GLASSBOX_MODEL", "gpt-4o"),

        # Classification model: gpt-4o-mini is cheaper and sufficient for triage.
        "model_classify": os.environ.get("GLASSBOX_MODEL_CLASSIFY", "gpt-4o-mini"),

        # Localization model: gpt-4o-mini is cheap and file ranking doesn't need the big model.
        "model_localize": os.environ.get("GLASSBOX_MODEL_LOCALIZE", "gpt-4o-mini"),

        # Review model: MUST be different from the generation model.
        # Claude provides a different perspective than GPT, catching different errors.
        # See: docs/architecture/agent-failure-analysis.md — same model = same blind spots.
        "review_model": os.environ.get("GLASSBOX_REVIEW_MODEL", "claude-3-5-sonnet-20241022"),

        # --- Temperatures ---
        # Low (0.3) for deterministic tasks, high (1.0) for creative tasks.
        "temperature_classify": float(os.environ.get("GLASSBOX_TEMP_CLASSIFY", "0.3")),
        "temperature_code": float(os.environ.get("GLASSBOX_TEMP_CODE", "1.0")),
        "temperature_review": float(os.environ.get("GLASSBOX_TEMP_REVIEW", "0.3")),
        "temperature_plan": float(os.environ.get("GLASSBOX_TEMP_PLAN", "0.5")),
        "temperature_localize": float(os.environ.get("GLASSBOX_TEMP_LOCALIZE", "0.3")),

        # --- Retry Policy ---
        # How many times to retry a failed step before asking the author.
        # 0 = never retry (fail fast). 2 = try twice more. Default: 2.
        "max_retries": int(os.environ.get("GLASSBOX_MAX_RETRIES", "2")),

        # --- Paths ---
        "templates_dir": os.environ.get("GLASSBOX_TEMPLATES_DIR", default_templates_dir),
        "reflections_path": os.environ.get(
            "GLASSBOX_REFLECTIONS_PATH",
            os.path.join(default_repo_root, "data", "reflections.json"),
        ),
        "repo_root": os.environ.get("GLASSBOX_REPO_ROOT", default_repo_root),

        # --- Test Configuration ---
        "module": "glassbox",
        "test_path": "tests/",
        "test_args": "",
        "max_diff_lines": 3,
    }
