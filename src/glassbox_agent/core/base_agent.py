"""BaseAgent ABC — parent of Manager, JuniorDev, Tester."""

from __future__ import annotations

from abc import ABC, abstractmethod

from openai import OpenAI

from glassbox_agent.core.settings import Settings
from glassbox_agent.tools.github_client import GitHubClient


class BaseAgent(ABC):
    """Every agent has a name, avatar, LLM client, and can post GitHub comments."""

    AVATAR_BASE_URL = "https://agentic-trust-labs.github.io/glassbox-ai/assets/agents"

    def __init__(self, name: str, avatar: str, client: OpenAI, github: GitHubClient, settings: Settings,
                 avatar_img: str = "", title: str = ""):
        self.name = name
        self.avatar = avatar
        self.client = client
        self.github = github
        self.settings = settings
        self.avatar_img = avatar_img
        self.title = title

    @property
    def header(self) -> str:
        """Markdown header for GitHub comments, with optional animal avatar image."""
        if self.avatar_img:
            url = f"{self.AVATAR_BASE_URL}/{self.avatar_img}"
            title_html = f"<br><sub>{self.title}</sub>" if self.title else ""
            return (
                f'<table><tr>'
                f'<td><img src="{url}" width="40" height="40" alt="{self.name}"></td>'
                f'<td><strong>{self.avatar} {self.name}</strong>{title_html}</td>'
                f'</tr></table>'
            )
        return f"{self.avatar} **{self.name}**"

    def comment(self, issue_number: int, body: str) -> int:
        """Post a GitHub comment as this agent (with avatar + name header)."""
        formatted = f"{self.header}\n\n{body}"
        return self.github.post_comment(issue_number, formatted)

    def react(self, comment_id: int, reaction: str = "+1") -> None:
        """Add a reaction to a comment (ack without a new comment)."""
        self.github.add_reaction(comment_id, reaction)

    def _call_llm(self, prompt: str, temperature: float | None = None, json_mode: bool = False, model: str | None = None) -> str:
        """Call OpenAI with retry-safe defaults. Returns raw content string."""
        kwargs: dict = {
            "model": model or self.settings.model,
            "temperature": temperature if temperature is not None else self.settings.temperature_classify,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        kwargs["max_tokens"] = 2048
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    @abstractmethod
    def think(self, context: dict) -> str:
        """Reason about the task. Returns a summary of thinking."""
        ...

    @abstractmethod
    def act(self, context: dict) -> dict:
        """Take action. Returns result dict."""
        ...
