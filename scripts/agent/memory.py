"""GlassBox Agent v0.3-beta - Reflexion memory (paper #12, Shinn et al.)."""

import json
import os

from .config import REFLECTIONS_PATH
from .models import Reflection


class Memory:
    """Stores and retrieves verbal failure reflections.

    After failure: save WHY it failed in plain English.
    Before coding: load reflections from similar past issues.
    """

    def __init__(self, path: str = REFLECTIONS_PATH):
        self.path = path
        self._reflections: list[Reflection] = self._load()

    def _load(self) -> list[Reflection]:
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            data = json.load(f)
        return [Reflection(**r) for r in data]

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump([r.model_dump() for r in self._reflections], f, indent=2)

    def save_reflection(
        self,
        issue_number: int,
        issue_title: str,
        failure_modes: list[str],
        reflection: str,
        edge_case_missed: str = "",
    ) -> None:
        """Store a failure reflection after an attempt fails."""
        self._reflections.append(
            Reflection(
                issue_number=issue_number,
                issue_title=issue_title,
                failure_modes=failure_modes,
                reflection=reflection,
                edge_case_missed=edge_case_missed,
            )
        )
        self._save()

    def relevant(self, issue_title: str, limit: int = 5) -> list[Reflection]:
        """Return past reflections, most recent first.

        Future: semantic similarity search. For now: return all, capped.
        """
        return self._reflections[-limit:]

    def format_for_prompt(self, issue_title: str) -> str:
        """Format relevant reflections as context for the LLM prompt."""
        refs = self.relevant(issue_title)
        if not refs:
            return ""
        lines = ["PAST FAILURE REFLECTIONS (learn from these):"]
        for r in refs:
            lines.append(f"- Issue #{r.issue_number} ({r.issue_title}): {r.reflection}")
            if r.edge_case_missed:
                lines.append(f"  Edge case missed: {r.edge_case_missed}")
        return "\n".join(lines)
