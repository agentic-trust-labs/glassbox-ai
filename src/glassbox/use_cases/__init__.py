"""
GlassBox Use Cases — The Apps Layer
======================================

Each use case is a self-contained folder that plugs into the GlassBox platform.

Think of this like apps on a phone:
    - The phone (core/) provides the OS: state machine, audit logging, agent contracts.
    - Apps (use_cases/) provide specific functionality: GitHub issue fixing, code review, etc.

Each use case folder contains:
    __init__.py  → Registration: what this use case is, how to activate it.
    states.py    → Use-case-specific states that extend BaseState (e.g., EASY_FIXING, MED_PLANNING).
    pipeline.py  → Which agents run at which state. The wiring diagram.
    settings.py  → Use-case-specific configuration (.gitignore-able for private settings).
    agents/      → Local agent escape hatch (empty by default, for future use-case-specific agents).
    tools/       → Local tool escape hatch (empty by default).
    templates/   → Use-case-specific data files (bug pattern YAMLs, prompt templates, etc.).
    memory/      → Use-case-specific memory (reflexion store, learning data, etc.).

How to add a new use case:
    1. Create a new folder: use_cases/my_use_case/
    2. Define states.py with your custom states + transitions (extend BASE_TRANSITIONS).
    3. Define pipeline.py mapping states to agent functions.
    4. Define settings.py with your configuration.
    5. Run: python -m glassbox.cli <issue_number> --use-case my_use_case
    That's it. No core changes needed.

Current use cases:
    github_issues/ → Fix GitHub issues automatically (easy/medium/hard routing).
                      This is the flagship use case — what GlassBox is known for.
"""
