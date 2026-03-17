"""Bug specification - what to inject, how to verify."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BugSpec:
    id: str            # "E01"
    difficulty: str    # "easy"
    file: str          # "src/glassbox/trust_db.py"
    title: str         # "[Bug] Wrong default trust"
    body: str          # Issue body text
    original: str      # Exact string in clean code
    mutation: str      # What replaces it
