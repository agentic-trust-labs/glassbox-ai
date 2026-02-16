"""Centralized configuration with validation. Fails fast on missing required values."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GitHub App credentials
    github_app_id: str = Field(..., description="GitHub App ID")
    github_app_private_key: str = Field(..., description="GitHub App private key (PEM)")
    github_webhook_secret: str = Field(default="", description="Webhook HMAC secret")

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")

    # Server
    port: int = Field(default=8080, ge=1, le=65535)
    log_level: str = Field(default="INFO")

    # Agent
    agent_label: str = Field(default="glassbox-agent")
    agent_timeout: int = Field(default=300, description="Max seconds per agent run")
    max_concurrent_runs: int = Field(default=3, description="Max parallel agent runs")

    # Rate limiting
    rate_limit_daily: int = Field(default=20, description="Max agent runs per day for non-exempt orgs")
    rate_limit_exempt_orgs: str = Field(default="agentic-trust-labs", description="Comma-separated exempt org logins")

    # Paths (inside Docker image)
    agent_pythonpath: str = Field(default="/app/src")

    @field_validator("github_app_private_key", mode="before")
    @classmethod
    def fix_newlines(cls, v: str) -> str:
        return v.replace("\\n", "\n") if v else v

    model_config = {"env_prefix": "", "case_sensitive": False}


def load_settings() -> Settings:
    """Load and validate settings from environment. Raises on missing required fields."""
    return Settings()  # type: ignore[call-arg]
