"""
GlassBox Tool — File Reader
==============================

Purpose:
    Read source files from the repository with line numbers. This is how agents
    "see" the codebase — every file is presented with numbered lines so the LLM
    can reference specific locations accurately.

Why line numbers matter:
    When the LLM sees "12: DEFAULT_VALUE = 0.85", it can generate an edit that says
    "replace line 12 with DEFAULT_VALUE = 0.90". Without line numbers, the LLM
    has to describe WHAT to change (string matching), which fails when there are
    multiple similar lines or when whitespace differs.

    This approach is inspired by SWE-agent (NeurIPS 2024): "ACI design reduces
    action space" — giving the LLM numbered lines reduces the space of possible
    edit descriptions to just (file, start_line, end_line, new_text).

Ported from:
    glassbox_agent/tools/file_reader.py — port with added documentation.
"""

from __future__ import annotations

import os


class FileReader:
    """
    Reads files relative to repo root, returns line-numbered content.

    Constructor:
        repo_root → Absolute path to the repository root.
                     All file paths are resolved relative to this.
    """

    def __init__(self, repo_root: str):
        self._root = repo_root

    def read(self, rel_path: str) -> tuple[bool, str]:
        """
        Read a file and return its content with line numbers.

        Each line is prefixed with its 1-indexed line number:
            1: first line of the file
            2: second line of the file
            ...

        This format is used in LLM prompts for all agents that need to
        reference specific lines (classifier, fix_generator, localizer).

        Args:
            rel_path → Relative path to the file from repo root.

        Returns:
            (True, numbered_content) on success.
            (False, error_message) if file not found.
        """

        full = os.path.join(self._root, rel_path)
        if not os.path.isfile(full):
            return False, f"File not found: {rel_path}"
        with open(full) as f:
            lines = f.readlines()
        numbered = "".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
        return True, numbered

    def read_lines(self, rel_path: str, start: int, end: int) -> tuple[bool, str]:
        """
        Read a specific line range (1-indexed, inclusive).

        Useful for showing only the relevant portion of a large file in a prompt,
        keeping token usage low.

        Args:
            rel_path → Relative path to the file.
            start    → First line to read (1-indexed, inclusive).
            end      → Last line to read (1-indexed, inclusive).

        Returns:
            (True, numbered_content) on success.
            (False, error_message) if file not found or range out of bounds.
        """

        full = os.path.join(self._root, rel_path)
        if not os.path.isfile(full):
            return False, f"File not found: {rel_path}"
        with open(full) as f:
            lines = f.readlines()
        if start < 1 or end > len(lines):
            return False, f"Line range {start}-{end} out of bounds (file has {len(lines)} lines)"
        selected = lines[start - 1:end]
        numbered = "".join(f"{start + i}: {line}" for i, line in enumerate(selected))
        return True, numbered

    def read_raw(self, rel_path: str) -> tuple[bool, str]:
        """
        Read raw file content without line numbers.

        Used when line numbers aren't needed (e.g., reading YAML templates,
        config files, or non-source files).

        Returns:
            (True, content) on success.
            (False, error_message) if file not found.
        """

        full = os.path.join(self._root, rel_path)
        if not os.path.isfile(full):
            return False, f"File not found: {rel_path}"
        with open(full) as f:
            return True, f.read()

    def list_files(self, extensions: tuple[str, ...] = (".py",)) -> list[str]:
        """
        List all source files in the repository matching given extensions.

        Walks the repo directory tree and returns relative paths for files
        matching any of the given extensions. Skips common non-source directories:
        .git, .venv, __pycache__, node_modules.

        This is used by the localizer agent to get the full file list for
        relevance ranking.

        Args:
            extensions → Tuple of file extensions to include (e.g., (".py",)).
                          Default: Python files only.

        Returns:
            Sorted list of relative file paths.
        """

        result = []
        for root, _, files in os.walk(self._root):
            # Skip directories that definitely don't contain source code.
            if any(skip in root for skip in (".git", ".venv", "__pycache__", "node_modules")):
                continue
            for fname in sorted(files):
                if any(fname.endswith(ext) for ext in extensions):
                    result.append(os.path.relpath(os.path.join(root, fname), self._root))
        return result
