"""
GlassBox Tool — Code Editor
==============================

Purpose:
    Apply line-number-based edits to source files. This is how the fix generator's
    output gets applied to the actual codebase.

Why line-number editing instead of string replacement:
    The old system (v1) used str.replace() to apply fixes. This failed constantly:
        - "String not found" when the LLM's text didn't EXACTLY match the source
        - Whitespace differences (tabs vs spaces, trailing spaces)
        - Multiple occurrences (str.replace replaces ALL, not just the target)

    Line-number editing is deterministic:
        "Replace lines 12-14 with this text" always works, regardless of content.
        The LLM sees numbered source lines and specifies exact line ranges.

    This eliminated the #1 source of apply failures in the v1 agent.

Edit format:
    Each edit is a dict (or LineEdit object) with:
        file       → Relative path to the file (e.g., "src/glassbox/config.py")
        start_line → First line to replace (1-indexed, inclusive)
        end_line   → Last line to replace (1-indexed, inclusive)
        new_text   → Replacement text (including newline at the end)

    Example:
        {"file": "src/config.py", "start_line": 12, "end_line": 12,
         "new_text": "    DEFAULT_VALUE = 0.85\\n"}

    This replaces line 12 of src/config.py with the new text.

Ported from:
    glassbox_agent/tools/code_editor.py — port with added documentation.
    Includes the fuzzy_find helper for finding approximate line matches.
"""

from __future__ import annotations

import difflib
import os


class CodeEditor:
    """
    Applies line-number-based edits to source files.

    Constructor:
        repo_root → Absolute path to the repository root.
                     All file paths in edits are relative to this.
    """

    def __init__(self, repo_root: str):
        self._root = repo_root

    def apply_edit(self, file: str, start_line: int, end_line: int, new_text: str) -> tuple[bool, str]:
        """
        Apply a single line-number edit to a file.

        Replaces lines start_line through end_line (1-indexed, inclusive) with new_text.

        Args:
            file       → Relative path to the file.
            start_line → First line to replace (1-indexed).
            end_line   → Last line to replace (1-indexed).
            new_text   → Replacement text. Should end with newline if replacing whole lines.

        Returns:
            (ok, error) → (True, "") on success, (False, "error message") on failure.

        Failure cases:
            - File doesn't exist
            - Line numbers out of range
            - Write permission denied
        """

        full_path = os.path.join(self._root, file)

        # Check that the file exists.
        if not os.path.isfile(full_path):
            return False, f"File not found: {file}"

        # Read all lines from the file.
        with open(full_path) as f:
            lines = f.readlines()

        # Validate line range. Lines are 1-indexed in the edit format.
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return False, (
                f"Invalid line range {start_line}-{end_line} "
                f"(file has {len(lines)} lines)"
            )

        # Apply the edit: replace lines[start-1:end] with new_text.
        # We split new_text into lines to maintain the list structure.
        # If new_text doesn't end with a newline, add one to prevent line merging.
        new_lines = new_text.split("\n")
        # Re-add newlines that split() removed (except for the last empty string from trailing \n)
        replacement = []
        for i, line in enumerate(new_lines):
            if i < len(new_lines) - 1:
                replacement.append(line + "\n")
            elif line:  # Last non-empty line
                replacement.append(line + "\n")

        # Replace the target line range.
        lines[start_line - 1:end_line] = replacement

        # Write back.
        with open(full_path, "w") as f:
            f.writelines(lines)

        return True, ""

    def apply_all(self, edits: list) -> tuple[bool, str]:
        """
        Apply multiple edits in sequence.

        Edits are applied in order. If ANY edit fails, we stop immediately
        and return the error. This prevents partial application of multi-edit fixes.

        Each edit can be a dict or an object with file, start_line, end_line, new_text attributes.

        IMPORTANT: When applying multiple edits to the SAME file, they must be ordered
        from bottom to top (highest line numbers first). Otherwise, earlier edits shift
        line numbers and later edits target the wrong lines.

        The fix generator is instructed to produce edits in this order.
        If it doesn't, this function does NOT re-sort (the caller should sort).

        Returns:
            (ok, error) → (True, "") if all edits succeeded, (False, "error") on first failure.
        """

        for edit in edits:
            # Support both dict and object formats.
            if isinstance(edit, dict):
                file = edit["file"]
                start_line = edit["start_line"]
                end_line = edit["end_line"]
                new_text = edit["new_text"]
            else:
                file = edit.file
                start_line = edit.start_line
                end_line = edit.end_line
                new_text = edit.new_text

            ok, error = self.apply_edit(file, start_line, end_line, new_text)
            if not ok:
                return False, f"Edit failed on {file}:{start_line}-{end_line}: {error}"

        return True, ""

    @staticmethod
    def fuzzy_find(content: str, target: str, threshold: float = 0.3) -> tuple[int, float]:
        """
        Find the best fuzzy match for a target string in file content.

        This is a fallback for when the LLM's line numbers are slightly off.
        It scans all lines in the content and returns the line number of the
        best match (by string similarity ratio).

        Used when an edit fails and we want to suggest the correct line number.

        Args:
            content   → The file content as a single string.
            target    → The string to search for (typically the LLM's expected old text).
            threshold → Minimum similarity ratio to consider a match (0.0-1.0).

        Returns:
            (line_number, ratio) → Best matching line (1-indexed) and similarity ratio.
            (0, ratio) if no line meets the threshold.
        """

        lines = content.split("\n")
        best_line, best_ratio = 0, 0.0
        target_stripped = target.strip()

        for i, line in enumerate(lines):
            ratio = difflib.SequenceMatcher(None, line.strip(), target_stripped).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_line = i + 1  # 1-indexed

        return (best_line, best_ratio) if best_ratio >= threshold else (0, best_ratio)
