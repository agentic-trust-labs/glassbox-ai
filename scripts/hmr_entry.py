"""Thin wrapper for mcp-hmr: sets up sys.path so relative imports in glassbox package work."""
import sys
sys.path.insert(0, "/Users/sourabh/Documents/projects/glassbox-ai/src")
from glassbox.server import mcp  # noqa: E402
