"""
GlassBox Use Case — Reflexion Memory Store
=============================================

Purpose:
    Save and query verbal failure reflections so agents can learn from past mistakes.

    When an issue fix fails, the pipeline records what went wrong in natural language.
    On the next similar issue, these reflections are injected into agent prompts
    so the LLM can avoid repeating the same errors.

Based on:
    Reflexion (NeurIPS 2023): "Verbal failure reflections improve future attempts."
    The key insight is that LLMs can learn from their own past mistakes if you
    describe those mistakes in natural language and include them in the prompt.

How it works:
    1. After a fix fails, the pipeline creates a Reflection object:
       - issue_number, issue_title, template_id
       - failure_modes: list of what went wrong (e.g., "String not found", "Test failed")
       - reflection: natural language lesson learned

    2. On the next issue, the classifier calls memory.format_for_prompt(title)
       which queries for similar past issues and returns a formatted string like:
           PAST REFLECTIONS (learn from these):
           - Issue #18 (wrong_value): Failed because value was in SQL string.

    3. This string is injected into the classification prompt so the LLM can
       adjust its approach based on past experience.

Storage:
    Simple JSON file at the path configured in settings.py (default: data/reflections.json).
    Each reflection is a JSON object. The file is a JSON array of all reflections.

    This is intentionally simple — no database, no vector store, no embeddings.
    Keyword matching is sufficient for our current volume (dozens of issues).
    If we need semantic search later, we can upgrade to embeddings without
    changing the interface (format_for_prompt still returns a string).

Ported from:
    glassbox_agent/memory/store.py — verbatim port with added documentation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class Reflection:
    """
    One failure reflection — a lesson learned from a failed fix attempt.

    Fields:
        issue_number  → The GitHub issue that failed.
        issue_title   → Title of the issue (used for keyword matching).
        template_id   → Which bug pattern template was used (e.g., "typo_fix").
        failure_modes → List of what went wrong (e.g., ["String not found", "Wrong line number"]).
        reflection    → Natural language lesson learned. This is the key field —
                         it's what gets injected into future prompts.
    """

    issue_number: int
    issue_title: str
    template_id: str = ""
    failure_modes: list[str] = field(default_factory=list)
    reflection: str = ""


class MemoryStore:
    """
    Stores and queries verbal failure reflections.

    Constructor:
        path → File path for JSON persistence. If empty, runs in-memory only.
               Default: "" (in-memory). Typically set to "data/reflections.json"
               by the use case settings.

    Thread safety: NOT thread-safe. The GitHub agent pipeline runs sequentially,
    so this isn't a problem. If we ever need concurrent access, add file locking.
    """

    def __init__(self, path: str = ""):
        self._path = path
        self._reflections: list[Reflection] = []

        # Load existing reflections from disk if the file exists.
        if path and os.path.exists(path):
            self._load()

    def _load(self) -> None:
        """Load reflections from the JSON file."""
        with open(self._path) as f:
            data = json.load(f)
        self._reflections = [Reflection(**r) for r in data]

    def save_reflection(self, reflection: Reflection) -> None:
        """
        Save a new reflection to the store.

        Appends to the in-memory list and persists to disk if a path is configured.
        Call this after a fix attempt fails with a meaningful reflection.
        """
        self._reflections.append(reflection)
        if self._path:
            self._persist()

    def _persist(self) -> None:
        """Write all reflections to the JSON file."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump([r.__dict__ for r in self._reflections], f, indent=2)

    def query(self, keyword: str, limit: int = 5) -> list[Reflection]:
        """
        Find reflections matching a keyword in the issue title or reflection text.

        This is a simple keyword search — no embeddings, no ML. It checks if the
        keyword (case-insensitive) appears in the issue_title or reflection text.

        For our current volume (dozens of reflections), this is fast enough.
        If we grow to thousands of reflections, upgrade to vector search.

        Args:
            keyword → Search term (typically the new issue's title).
            limit   → Maximum number of results to return.

        Returns:
            List of matching Reflection objects, most recent first (up to limit).
        """
        keyword_lower = keyword.lower()
        matches = [
            r for r in self._reflections
            if keyword_lower in r.issue_title.lower() or keyword_lower in r.reflection.lower()
        ]
        # Return the most recent matches (last N).
        return matches[-limit:]

    def format_for_prompt(self, title: str) -> str:
        """
        Format relevant reflections for injection into an LLM prompt.

        This is the main interface for agents. The classifier calls this with the
        new issue's title, and gets back a formatted string to include in its prompt.

        Returns:
            A string like:
                PAST REFLECTIONS (learn from these):
                - Issue #18 (wrong_value): Failed because value was in SQL string.
                - Issue #22 (typo_fix): Fixed wrong variable but missed the second occurrence.

            Returns empty string if no relevant reflections are found.
        """
        relevant = self.query(title if title else "", limit=3)
        if not relevant:
            return ""
        lines = ["PAST REFLECTIONS (learn from these):"]
        for r in relevant:
            lines.append(f"- Issue #{r.issue_number} ({r.template_id}): {r.reflection}")
        return "\n".join(lines)

    def all(self) -> list[Reflection]:
        """Return all stored reflections. For debugging and inspection."""
        return list(self._reflections)
