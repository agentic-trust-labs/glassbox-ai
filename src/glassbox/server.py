"""GlassBox AI — Multi-agent MCP server with trust scoring."""

import os, subprocess
from typing import Optional
from mcp.server.fastmcp import FastMCP
from .orchestrator import MultiAgentOrchestrator

# Read API key: Keychain first, then env var
try:
    os.environ["OPENAI_API_KEY"] = subprocess.run(
        ["security", "find-generic-password", "-s", "OPENAI_API_KEY", "-a", "glassbox-ai", "-w"],
        capture_output=True, text=True, check=True
    ).stdout.strip()
except Exception:
    pass  # fall back to env var

from . import __version__
mcp = FastMCP(f"GlassBox AI v{__version__}")
trust_floor = 0.30


@mcp.tool()
async def analyze(task: str, agents: Optional[str] = None) -> str:
    """Run multiple AI agents on a task with trust-weighted consensus."""
    agent_list = [a.strip() for a in agents.split(",")] if agents else None
    return await orch.execute_formatted(task, agent_list)


@mcp.tool()
async def debate(task: str) -> str:
    """Run a multi-round debate between agents. They talk TO each other across 3 rounds: Position → Reaction → Convergence. Trust auto-updates based on who persuades whom."""
    return await orch.debate(task)


@mcp.tool()
def trust_scores() -> str:
    """View current trust scores for all agents."""
    scores = orch.trust_db.get_all_scores()
    return "\n".join(f"{a}: {s:.2f}" for a, s in scores.items())


@mcp.tool()
def update_trust(agent: str, was_correct: bool) -> str:
    """Update agent trust based on outcome."""
    orch.trust_db.update_trust(agent, was_correct)
    s = orch.trust_db.get_trust(agent)
    return f"{'✅' if was_correct else '❌'} {agent}: {s:.2f}"


def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
