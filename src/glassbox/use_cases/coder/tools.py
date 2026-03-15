"""Coder tools — str_replace_editor vendored from Anthropic's claude-quickstarts (MIT License).

Source:
  github.com/anthropics/claude-quickstarts/blob/main/computer-use-demo/computer_use_demo/tools/edit.py
  github.com/anthropics/claude-quickstarts/blob/main/computer-use-demo/computer_use_demo/tools/run.py
Copyright (c) 2023 Anthropic. MIT License.

Adaptations made for our context (unchanged: all core algorithms):
  - Removed async/await — our agent loop is synchronous
  - Removed BaseAnthropicTool class hierarchy — not needed with litellm function calling
  - Removed anthropic SDK dependency (CLIResult, ToolError) — return plain strings instead
  - Added cwd resolution so relative paths work from the repo root
  - Added `handle_editor` dispatch function that routes to each command

Tool JSON definitions follow Anthropic's SWE-bench blog post spec:
  https://www.anthropic.com/engineering/swe-bench-sonnet
  Tools: bash + str_replace_editor (the exact two tools that achieved 49% on SWE-bench Verified)

Complete tool pattern borrowed from Augment Code (MIT):
  github.com/augmentcode/augment-swebench-agent/blob/main/tools/complete_tool.py
"""

import os
import subprocess
from collections import defaultdict
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Constants — from Anthropic's run.py (MIT)
# Source: github.com/anthropics/claude-quickstarts/.../tools/run.py
# ──────────────────────────────────────────────────────────────────────────────

SNIPPET_LINES: int = 4  # lines of context shown around every edit in the success message

MAX_RESPONSE_LEN: int = 16000  # chars before output is truncated

# Truncation notice injected by Anthropic's maybe_truncate — tells the model what to do next.
# Verbatim from Anthropic's run.py so the model recognises the pattern from its training data.
TRUNCATED_MESSAGE: str = (
    "<response clipped><NOTE>To save on context only part of this file has been shown to you. "
    "You should retry this tool after you have searched inside the file with `grep -n` in order "
    "to find the line numbers of what you are looking for.</NOTE>"
)

# ──────────────────────────────────────────────────────────────────────────────
# maybe_truncate — verbatim from Anthropic's run.py (MIT)
# ──────────────────────────────────────────────────────────────────────────────

def maybe_truncate(content: str, truncate_after: int | None = MAX_RESPONSE_LEN) -> str:
    """Truncate content and append a notice if content exceeds the specified length.
    
    Verbatim from Anthropic's run.py. The truncation message is the exact string
    Anthropic's model was trained on — it tells the model to use grep -n to locate
    the section it needs, rather than reading the full file again.
    """
    return (
        content
        if not truncate_after or len(content) <= truncate_after
        else content[:truncate_after] + TRUNCATED_MESSAGE
    )


# ──────────────────────────────────────────────────────────────────────────────
# _make_output — verbatim from Anthropic's EditTool._make_output (MIT)
# ──────────────────────────────────────────────────────────────────────────────

def _make_output(file_content: str, file_descriptor: str, init_line: int = 1) -> str:
    """Generate numbered output for file content (equivalent to cat -n).
    
    Verbatim from Anthropic's EditTool._make_output method. The model is trained
    to expect this exact format when viewing file contents.
    """
    file_content = maybe_truncate(file_content)
    file_content = file_content.expandtabs()
    file_content = "\n".join(
        f"{i + init_line:6}\t{line}"
        for i, line in enumerate(file_content.split("\n"))
    )
    return f"Here's the result of running `cat -n` on {file_descriptor}:\n{file_content}\n"


# ──────────────────────────────────────────────────────────────────────────────
# File edit history — supports potential undo; pattern from Anthropic's EditTool
# ──────────────────────────────────────────────────────────────────────────────

_file_history: dict[str, list[str]] = defaultdict(list)


# ──────────────────────────────────────────────────────────────────────────────
# handle_editor — Anthropic's EditTool logic, adapted to sync + plain function
#
# CORE ALGORITHMS ARE VERBATIM FROM ANTHROPIC (MIT). See line-by-line comments.
# Adaptations: no async, no class, return str not CLIResult, cwd resolution.
# ──────────────────────────────────────────────────────────────────────────────

def handle_editor(command: str, path: str, cwd: str, **kwargs) -> str:
    """Execute a str_replace_editor command and return the result as a string.
    
    This is Anthropic's EditTool logic (MIT License) adapted to:
      1. Synchronous execution (no async/await)
      2. Plain function interface for litellm function calling
      3. Returns strings instead of CLIResult/ToolError objects
      4. Resolves relative paths against the repo cwd
    
    The core algorithms (str_replace uniqueness check, snippet generation,
    view range handling, insert logic) are copied verbatim from Anthropic's
    EditTool20250728 class in claude-quickstarts/computer-use-demo.
    """
    # Resolve relative paths against the repo root (our addition)
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    _path = Path(path)

    # ── Validation — verbatim from Anthropic's validate_path ──────────────────
    if not _path.exists() and command != "create":
        return f"Error: The path {path} does not exist. Please provide a valid path."
    if _path.exists() and command == "create":
        return f"Error: File already exists at: {path}. Cannot overwrite files using command `create`."
    if _path.is_dir() and command != "view":
        return f"Error: The path {path} is a directory and only the `view` command can be used on directories."

    # ── view ──────────────────────────────────────────────────────────────────
    if command == "view":
        if _path.is_dir():
            # Verbatim from Anthropic's view() directory branch
            result = subprocess.run(
                rf"find {path} -maxdepth 2 -not -path '*/\.*'",
                shell=True, capture_output=True, text=True
            )
            if not result.stderr:
                stdout = (
                    f"Here's the files and directories up to 2 levels deep in {path}, "
                    f"excluding hidden items:\n{result.stdout}\n"
                )
            else:
                stdout = result.stdout
            return stdout

        # Read file and apply view_range — verbatim from Anthropic's view() file branch
        try:
            file_content = _path.read_text()
        except Exception as e:
            return f"Error: Ran into {e} while trying to read {path}"

        init_line = 1
        view_range = kwargs.get("view_range")
        if view_range:
            # Validation verbatim from Anthropic
            if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                return "Error: Invalid `view_range`. It should be a list of two integers."
            file_lines = file_content.split("\n")
            n_lines_file = len(file_lines)
            init_line, final_line = view_range
            if init_line < 1 or init_line > n_lines_file:
                return (f"Error: Invalid `view_range`: {view_range}. Its first element `{init_line}` "
                        f"should be within the range of lines of the file: {[1, n_lines_file]}")
            if final_line != -1 and final_line > n_lines_file:
                return (f"Error: Invalid `view_range`: {view_range}. Its second element `{final_line}` "
                        f"should be smaller than the number of lines in the file: `{n_lines_file}`")
            if final_line != -1 and final_line < init_line:
                return (f"Error: Invalid `view_range`: {view_range}. Its second element `{final_line}` "
                        f"should be larger or equal than its first `{init_line}`")
            if final_line == -1:
                file_content = "\n".join(file_lines[init_line - 1:])
            else:
                file_content = "\n".join(file_lines[init_line - 1:final_line])

        return _make_output(file_content, str(path), init_line=init_line)

    # ── create ────────────────────────────────────────────────────────────────
    elif command == "create":
        file_text = kwargs.get("file_text")
        if file_text is None:
            return "Error: Parameter `file_text` is required for command: create"
        try:
            os.makedirs(_path.parent, exist_ok=True)
            _path.write_text(file_text)
        except Exception as e:
            return f"Error: Ran into {e} while trying to write to {path}"
        _file_history[path].append(file_text)
        return f"File created successfully at: {path}"

    # ── str_replace ───────────────────────────────────────────────────────────
    elif command == "str_replace":
        old_str = kwargs.get("old_str")
        new_str = kwargs.get("new_str", "")
        if old_str is None:
            return "Error: Parameter `old_str` is required for command: str_replace"

        # Read the file content — verbatim from Anthropic's str_replace
        try:
            file_content = _path.read_text()
        except Exception as e:
            return f"Error: Ran into {e} while trying to read {path}"

        # .expandtabs() preprocessing — verbatim from Anthropic (lines 161-163 of edit.py)
        file_content = file_content.expandtabs()
        old_str = old_str.expandtabs()
        new_str = new_str.expandtabs() if new_str is not None else ""

        # Uniqueness check — verbatim from Anthropic (lines 166-182 of edit.py)
        # This is the critical algorithm: 0 matches = not found, 2+ = ambiguous
        occurrences = file_content.count(old_str)
        if occurrences == 0:
            return (
                f"Error: No replacement was performed, old_str `{old_str}` "
                f"did not appear verbatim in {path}."
            )
        elif occurrences > 1:
            file_content_lines = file_content.split("\n")
            lines = [
                idx + 1
                for idx, line in enumerate(file_content_lines)
                if old_str in line
            ]
            return (
                f"Error: No replacement was performed. Multiple occurrences of old_str "
                f"`{old_str}` in lines {lines}. Please ensure it is unique"
            )

        # Apply replacement — verbatim from Anthropic (line 185 of edit.py)
        new_file_content = file_content.replace(old_str, new_str)

        # Write new content — verbatim from Anthropic (line 188 of edit.py)
        try:
            _path.write_text(new_file_content)
        except Exception as e:
            return f"Error: Ran into {e} while trying to write to {path}"

        # Save to history — verbatim from Anthropic (line 191 of edit.py)
        _file_history[path].append(file_content)

        # Snippet generation — verbatim from Anthropic (lines 193-196 of edit.py)
        replacement_line = file_content.split(old_str)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
        snippet = "\n".join(new_file_content.split("\n")[start_line: end_line + 1])

        # Success message — verbatim from Anthropic (lines 199-203 of edit.py)
        success_msg = f"The file {path} has been edited. "
        success_msg += _make_output(snippet, f"a snippet of {path}", start_line + 1)
        success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."
        return success_msg

    # ── insert ────────────────────────────────────────────────────────────────
    elif command == "insert":
        insert_line = kwargs.get("insert_line")
        new_str = kwargs.get("new_str", "")
        if insert_line is None:
            return "Error: Parameter `insert_line` is required for command: insert"

        # Read and preprocess — verbatim from Anthropic's insert (lines 206-211 of edit.py)
        try:
            file_text = _path.read_text()
        except Exception as e:
            return f"Error: Ran into {e} while trying to read {path}"

        file_text = file_text.expandtabs()
        new_str = new_str.expandtabs()
        file_text_lines = file_text.split("\n")
        n_lines_file = len(file_text_lines)

        # Range validation — verbatim from Anthropic (lines 213-217 of edit.py)
        if insert_line < 0 or insert_line > n_lines_file:
            return (
                f"Error: Invalid `insert_line` parameter: {insert_line}. "
                f"It should be within the range of lines of the file: {[0, n_lines_file]}"
            )

        # Build new file content — verbatim from Anthropic (lines 219-228 of edit.py)
        new_str_lines = new_str.split("\n")
        new_file_text_lines = (
            file_text_lines[:insert_line]
            + new_str_lines
            + file_text_lines[insert_line:]
        )
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_LINES): insert_line]
            + new_str_lines
            + file_text_lines[insert_line: insert_line + SNIPPET_LINES]
        )

        new_file_text = "\n".join(new_file_text_lines)
        snippet = "\n".join(snippet_lines)

        try:
            _path.write_text(new_file_text)
        except Exception as e:
            return f"Error: Ran into {e} while trying to write to {path}"

        _file_history[path].append(file_text)

        # Success message — verbatim from Anthropic (lines 232-237 of edit.py)
        success_msg = f"The file {path} has been edited. "
        success_msg += _make_output(
            snippet, "a snippet of the edited file",
            max(1, insert_line - SNIPPET_LINES + 1)
        )
        success_msg += "Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary."
        return success_msg

    return f"Error: Unrecognized command {command}. Allowed commands: view, create, str_replace, insert."


# ──────────────────────────────────────────────────────────────────────────────
# Tool JSON definitions — for litellm function calling
#
# Tool descriptions verbatim from Anthropic's SWE-bench blog post:
#   https://www.anthropic.com/engineering/swe-bench-sonnet
# "We put a lot of effort into the descriptions and specs for these tools...
#  We believe that much more attention should go into designing tool interfaces
#  for models, in the same way that a large amount of attention goes into
#  designing tool interfaces for humans."
# ──────────────────────────────────────────────────────────────────────────────

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        # Description verbatim from Anthropic's bash tool spec in the SWE-bench blog post
        "description": (
            "Run commands in a bash shell\n"
            "* Use this for: running tests, executing scripts, searching with grep/find, git operations.\n"
            "* Do NOT use this for viewing or editing files — use str_replace_editor instead.\n"
            "* State is persistent across command calls (cwd, env vars, installed packages).\n"
            "* The current working directory (cwd) is the root of the repository.\n"
            "* Output is truncated to 16000 chars. Pipe large output through head.\n"
            "* Please avoid commands that may produce a very large amount of output.\n"
            "* Please run long-lived commands in the background, e.g. 'sleep 10 &'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to run.",
                }
            },
            "required": ["command"],
        },
    },
}

EDITOR_TOOL = {
    "type": "function",
    "function": {
        "name": "str_replace_editor",
        # Description verbatim from Anthropic's str_replace_editor tool spec
        "description": (
            "Custom editing tool for viewing, creating and editing files\n"
            "* State is persistent across command calls and discussions with the user\n"
            "* If `path` is a file, `view` displays the result of applying `cat -n`. "
            "If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep\n"
            "* The `create` command cannot be used if the specified `path` already exists as a file\n"
            "* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`\n"
            "\n"
            "Notes for using the `str_replace` command:\n"
            "* The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. "
            "Be mindful of whitespaces!\n"
            "* If the `old_str` parameter is not unique in the file, the replacement will not be performed. "
            "Make sure to include enough context in `old_str` to make it unique\n"
            "* The `new_str` parameter should contain the edited lines that should replace the `old_str`"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["view", "create", "str_replace", "insert"],
                    "description": "The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`.",
                },
                "path": {
                    "type": "string",
                    "description": "Absolute path to file or directory, e.g. `/repo/file.py` or `/repo`.",
                },
                "file_text": {
                    "type": "string",
                    "description": "Required parameter of `create` command, with the content of the file to be created.",
                },
                "old_str": {
                    "type": "string",
                    "description": "Required parameter of `str_replace` command containing the string in `path` to replace.",
                },
                "new_str": {
                    "type": "string",
                    "description": (
                        "Required parameter of `str_replace` command containing the new string. "
                        "Required parameter of `insert` command containing the string to insert."
                    ),
                },
                "insert_line": {
                    "type": "integer",
                    "description": "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.",
                },
                "view_range": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": (
                        "Optional parameter of `view` command when `path` points to a file. "
                        "If none is given, the full file is shown. If provided, the file will be shown "
                        "in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. "
                        "Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from "
                        "`start_line` to the end of the file."
                    ),
                },
            },
            "required": ["command", "path"],
        },
    },
}

# Complete tool — pattern borrowed from Augment Code's CompleteTool (MIT)
# Source: github.com/augmentcode/augment-swebench-agent/blob/main/tools/complete_tool.py
# "Call this tool when you are done with the task, and supply your answer or summary."
COMPLETE_TOOL = {
    "type": "function",
    "function": {
        "name": "complete",
        "description": "Call this tool when you are done with the task, and supply your answer or summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "Summary of the changes made and the fix applied.",
                }
            },
            "required": ["result"],
        },
    },
}

RECALL_EPISODES_TOOL = {
    "type": "function",
    "function": {
        "name": "recall_episodes",
        "description": (
            "Search past correction episodes for lessons learned.\n"
            "* Use EARLY in investigation when you see a familiar pattern.\n"
            "* Returns up to 3 past corrections. Proceed normally if none found.\n"
            "* Do NOT call more than twice per task."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Describe the current problem or error pattern."}},
            "required": ["query"],
        },
    },
}

# The full tool set passed to litellm on every completion() call
TOOLS = [BASH_TOOL, EDITOR_TOOL, COMPLETE_TOOL, RECALL_EPISODES_TOOL]
