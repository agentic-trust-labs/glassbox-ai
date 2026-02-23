"""
GlassBox — Transparent AI Agent Platform
=========================================

GlassBox is an "OS + Apps" platform for AI agents that work on your code.

Architecture overview:
    core/       → The kernel. State machine engine + audit logging.
                  This is the "OS" — it never imports from agents, tools, or use cases.
                  It only knows: states exist, transitions connect them, agents are functions.

    agents/     → Shared agent pool. Every agent lives here (ONE copy, never duplicated).
                  Use cases BORROW agents by name. Core agents (classifier, reviewer,
                  conversationalist) require owner approval to change. Others are open.

    tools/      → Shared tool pool. Stateless utilities (LLM client, GitHub API, code editor).
                  Same governance as agents: core tools gatekept, others open.

    use_cases/  → Apps. Each use case is a self-contained folder with its own states,
                  pipeline (which agents to run at which state), settings, and templates.
                  Adding a use case = adding a folder. No core changes needed.

Version scheme:
    0.x = pre-release, API may change
    0.5 = platform foundation (state machine + easy/medium/hard routing)
    1.0 = production-ready with all three pipelines stable

Why "GlassBox"?
    Every state transition is logged. Every agent call is audited. Every decision
    is transparent. You can look inside the box and see exactly what happened,
    what was considered, and why. Not a black box. Not a white box. A glass box.
"""

__version__ = "0.5.0-alpha"
