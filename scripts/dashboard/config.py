"""Dashboard configuration - single source of truth."""

import os

REPO = os.environ.get("GITHUB_REPOSITORY", "agentic-trust-labs/glassbox-ai")
WORKFLOW_NAME = "GlassBox Agent"
AGENT_LABELS = ["glassbox-agent", "agent"]
AGENT_MENTIONS = ["@glassbox-agent", "@glassbox_agent"]
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "dashboard")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")
