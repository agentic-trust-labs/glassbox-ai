"""
GlassBox Server — MCP Server (Stub)
======================================

Purpose:
    Expose GlassBox capabilities as an MCP (Model Context Protocol) server
    for IDE integration. This allows IDEs like VS Code, Cursor, and Windsurf
    to interact with the GlassBox platform directly.

Current status: STUB
    The full MCP server implementation is Phase 4. For now, this file provides
    the structure and will be fleshed out when we get there.

    The old server.py (54 lines) in src/glassbox/ was a FastAPI-based MCP server
    that exposed the debate/orchestrator functionality. The new server will expose
    the full platform: run use cases, check state, read audit logs, etc.

What the MCP server will expose:
    Tools:
        - glassbox.run(issue_number, use_case) → Run a use case on an issue
        - glassbox.status(issue_number) → Get current state and audit log
        - glassbox.classify(issue_number) → Just classify without running
        - glassbox.debate(topic) → Multi-agent debate (from old orchestrator)

    Resources:
        - glassbox://issues/{number}/state → Current state
        - glassbox://issues/{number}/audit → Full audit trail
        - glassbox://config → Current settings

Future implementation will use the `mcp` Python SDK.
"""

from __future__ import annotations


def create_server():
    """
    Create and return the MCP server instance.

    STUB: Returns None. Full implementation in Phase 4.

    When implemented, this will:
        1. Create an MCP server instance.
        2. Register tools (run, status, classify, debate).
        3. Register resources (state, audit, config).
        4. Return the server ready to be started.
    """

    # Placeholder — will be implemented in Phase 4.
    print("GlassBox MCP Server — not yet implemented (Phase 4)")
    print("Use the CLI instead: python -m glassbox.cli <issue_number>")
    return None


if __name__ == "__main__":
    create_server()
