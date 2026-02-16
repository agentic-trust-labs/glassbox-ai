"""Single source of truth for all agent configuration."""

from __future__ import annotations

import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    repo: str = Field(default_factory=lambda: os.environ.get("GITHUB_REPOSITORY", "agentic-trust-labs/glassbox-ai"))
    model: str = "gpt-4o"
    model_classify: str = "gpt-4o-mini"
    temperature_classify: float = 0.3
    temperature_code: float = 0.1
    temperature_review: float = 0.3
    max_retries: int = 2
    templates_dir: str = Field(default_factory=lambda: os.path.join(os.path.dirname(__file__), "..", "templates"))
    reflections_path: str = Field(default_factory=lambda: os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "reflections.json"))
