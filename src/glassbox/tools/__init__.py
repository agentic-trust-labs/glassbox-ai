"""
GlassBox Tools — Shared Tool Pool
====================================

All tools live here in ONE place. No duplication.

Tools are STATELESS utilities: they take input, return output, and have no
side effects beyond their stated purpose. They are the "system calls" of the
GlassBox platform — agents use them to interact with the outside world.

Tool categories (for documentation, not for folder structure):

    PLATFORM tools (used by the engine and all agents):
        llm.py         → LLM abstraction. Wraps OpenAI/Claude/etc. API calls.
        state_store.py → Persist and load state (to GitHub, file, or DB).

    CODE tools (used by any use case that modifies code):
        code_editor.py → Apply line-number edits to source files.
        file_reader.py → Read source files with line numbers.
        test_runner.py → Run pytest and parse results.

    CHANNEL tools (used by any use case that communicates on a specific channel):
        github_client.py → GitHub API: issues, comments, PRs, branches.
        (future: slack_client.py, jira_client.py, etc.)

Governance:
    CORE_TOOLS → These tools are essential for the platform to function.
                  Changing them requires owner approval (CODEOWNERS).
                  Currently: llm and state_store.

    All other tools are OPEN for contribution. Anyone can add a new tool file
    to this directory.

How to add a new tool:
    1. Create a new file: tools/my_tool.py
    2. Define stateless functions or a simple class.
    3. Use it from your agent by importing it.
    That's it. No registry, no base class.
"""

# Core tools: require owner approval to modify.
# These are the infrastructure that everything else depends on.
CORE_TOOLS: set[str] = {"llm", "state_store"}
