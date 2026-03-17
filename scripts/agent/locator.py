"""GlassBox Agent v0.3-beta - Code localization via Aider RepoMap.

Uses tree-sitter + PageRank to find relevant files and code snippets
for a given issue. Replaces hardcoded SOURCE_FILES with dynamic discovery.
"""

import glob
import os

from aider.io import InputOutput
from aider.models import Model
from aider.repomap import RepoMap

from .config import MODEL, REPO_MAP_TOKENS, REPO_FILE_EXTENSIONS


class Locator:
    """Finds relevant files and code context for a given issue.

    Design: dependency injection (root passed in), encapsulated state,
    fail-fast if RepoMap can't parse.
    """

    def __init__(self, root: str):
        self._root = root
        self._io = InputOutput(yes=True)
        self._model = Model(MODEL)
        self._repo_map = RepoMap(
            map_tokens=REPO_MAP_TOKENS,
            root=root,
            io=self._io,
            main_model=self._model,
        )

    # -- Public API --

    def get_repo_map(self) -> str:
        """Return PageRank-ranked repo map showing key symbols and signatures."""
        all_files = self._discover_files()
        if not all_files:
            print("  [locator] no files found")
            return ""
        repo_map = self._repo_map.get_repo_map(chat_files=[], other_files=all_files)
        print(f"  [locator] repo map: {len(repo_map)} chars, {len(all_files)} files scanned")
        return repo_map

    def get_relevant_sources(self, all_files: list[str] | None = None) -> dict[str, str]:
        """Read all discovered source files into a dict {path: content}."""
        files = all_files or self._discover_files()
        sources = {}
        for path in files:
            full = os.path.join(self._root, path)
            try:
                with open(full) as f:
                    sources[path] = f.read()
            except (OSError, UnicodeDecodeError) as e:
                print(f"  [locator] skip {path}: {e}")
        print(f"  [locator] read {len(sources)} source files")
        return sources

    # -- Private helpers --

    def _discover_files(self) -> list[str]:
        """Find all source files in the repo by configured extensions."""
        prev = os.getcwd()
        os.chdir(self._root)
        try:
            files = []
            for ext in REPO_FILE_EXTENSIONS:
                files.extend(glob.glob(f"**/*.{ext}", recursive=True))
            # Filter out agent scripts themselves and hidden dirs
            files = [
                f for f in files
                if not f.startswith("scripts/agent/")
                and not f.startswith(".")
            ]
            return sorted(set(files))
        finally:
            os.chdir(prev)
