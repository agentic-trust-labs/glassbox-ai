"""CodeEditor — line-number editing + fuzzy fallback (Paper 2: SWE-agent)."""

from __future__ import annotations

import difflib
import os

from glassbox_agent.core.models import LineEdit


class CodeEditor:
    """Edit files by line number. Eliminates 'String not found' failures."""

    def __init__(self, repo_root: str):
        self._root = repo_root

    def _resolve(self, rel_path: str) -> str | None:
        """Resolve a potentially partial path to a real file in the repo."""
        full = os.path.join(self._root, rel_path)
        if os.path.isfile(full):
            return full
        # Fallback: search by basename
        target = os.path.basename(rel_path)
        for dirpath, _, filenames in os.walk(self._root):
            if '.git' in dirpath or '__pycache__' in dirpath:
                continue
            if target in filenames:
                return os.path.join(dirpath, target)
        return None

    def apply(self, edit: LineEdit) -> tuple[bool, str]:
        """Apply a LineEdit to a file. Returns (ok, error_or_empty)."""
        full = self._resolve(edit.file)
        if not full:
            return False, f"File not found: {edit.file}"

        with open(full) as f:
            lines = f.readlines()

        if edit.start_line < 1 or edit.end_line > len(lines):
            return False, f"Line range {edit.start_line}-{edit.end_line} out of bounds ({len(lines)} lines)"

        # Indent-Capture-Reapply: preserve original indentation (RooCode pattern)
        original_line = lines[edit.start_line - 1]
        original_indent = original_line[:len(original_line) - len(original_line.lstrip())]

        new_lines = edit.new_text.split("\n")
        if not edit.new_text.endswith("\n"):
            new_lines = [line + "\n" for line in new_lines]
        else:
            new_lines = [line + "\n" if not line.endswith("\n") else line for line in edit.new_text.split("\n")]
            if new_lines and new_lines[-1] == "\n":
                new_lines[-1] = ""
                if new_lines[-1] == "":
                    new_lines.pop()

        # Reapply original indentation to each non-blank replacement line
        if original_indent:
            fixed = []
            for i, line in enumerate(new_lines):
                stripped = line.rstrip("\n")
                if not stripped.strip():
                    fixed.append(line)
                elif i == 0:
                    fixed.append(original_indent + stripped.lstrip() + "\n")
                else:
                    # Preserve relative indent: offset from first new line
                    first_indent = len(new_lines[0].rstrip("\n")) - len(new_lines[0].rstrip("\n").lstrip())
                    cur_indent = len(stripped) - len(stripped.lstrip())
                    relative = max(0, cur_indent - first_indent)
                    fixed.append(original_indent + " " * relative + stripped.lstrip() + "\n")
            new_lines = fixed

        lines[edit.start_line - 1:edit.end_line] = new_lines
        with open(full, "w") as f:
            f.writelines(lines)
        return True, ""

    def apply_all(self, edits: list[LineEdit]) -> tuple[bool, str]:
        """Apply multiple edits. Stops on first error."""
        for edit in edits:
            ok, err = self.apply(edit)
            if not ok:
                return False, err
        return True, ""

    def diff_line_count(self, edit: LineEdit) -> int:
        """Count how many lines an edit changes."""
        original_count = edit.end_line - edit.start_line + 1
        new_count = len(edit.new_text.strip().split("\n"))
        return max(original_count, new_count)

    @staticmethod
    def fuzzy_find(content: str, target: str, threshold: float = 0.3) -> tuple[int, float]:
        """Find best fuzzy match for target in content lines. Returns (line_number, ratio)."""
        lines = content.split("\n")
        best_line, best_ratio = 0, 0.0
        target_stripped = target.strip()
        for i, line in enumerate(lines):
            ratio = difflib.SequenceMatcher(None, line.strip(), target_stripped).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_line = i + 1
        return (best_line, best_ratio) if best_ratio >= threshold else (0, best_ratio)
