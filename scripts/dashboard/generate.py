#!/usr/bin/env python3
"""GlassBox Agent Dashboard Generator.

Fetches all agent data from GitHub API and generates an HTML dashboard.
Run: python -m scripts.dashboard.generate
"""

import os
import sys

from .config import OUTPUT_DIR, OUTPUT_FILE
from .fetch import GitHubFetcher
from .render import DashboardRenderer


def main():
    print("[dashboard] Starting dashboard generation...")

    fetcher = GitHubFetcher()
    data = fetcher.fetch_all()

    renderer = DashboardRenderer(data)
    html_content = renderer.render()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[dashboard] Written to {OUTPUT_FILE}")
    print(f"[dashboard] Agent issues: {len(data['agent_issues'])}")
    print(f"[dashboard] PRs: {len(data['prs'])}")
    print(f"[dashboard] Workflow runs: {len(data['runs'])}")


if __name__ == "__main__":
    main()
