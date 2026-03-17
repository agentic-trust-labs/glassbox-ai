"""BugFactory - inject bugs, verify fixes."""

from .bug_spec import BugSpec
from .catalog import CATALOG


class BugFactory:
    """Creates and verifies synthetic bugs for agent benchmarking."""

    def list_bugs(self, difficulty: str = "easy") -> list[BugSpec]:
        """Return all bugs at given difficulty."""
        return [b for b in CATALOG if b.difficulty == difficulty]

    def get(self, bug_id: str) -> BugSpec:
        """Lookup one bug by ID."""
        return next(b for b in CATALOG if b.id == bug_id)

    def inject(self, spec: BugSpec, sources: dict[str, str]) -> dict[str, str]:
        """Return mutated copy of sources with bug injected."""
        out = dict(sources)
        out[spec.file] = out[spec.file].replace(spec.original, spec.mutation, 1)
        return out

    def verify(self, spec: BugSpec, sources: dict[str, str]) -> bool:
        """True if the source has the original string (bug is fixed)."""
        return spec.original in sources.get(spec.file, "")
