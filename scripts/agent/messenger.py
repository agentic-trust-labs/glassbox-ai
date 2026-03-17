"""GlassBox Agent v0.3-beta - formats the 5 GitHub messages."""

from .config import AGENT_NAME
from .models import Analysis, Fix, ReviewResult


class Messenger:
    """Formats structured markdown comments for the 5-message protocol."""

    def msg1_analysis(self, issue_number: int, issue_title: str, analysis: Analysis) -> str:
        """Message 1: ANALYSIS - aspects, challenges, edge cases."""
        lines = [
            f"🤖 **{AGENT_NAME} picked up #{issue_number}** - analyzing before touching code...\n",
            "## 🏗️ Aspects (system design / best practices)\n",
            "| # | Aspect | Why it matters | Ideal behavior |",
            "|---|--------|---------------|----------------|",
        ]
        for a in analysis.aspects:
            lines.append(f"| {a.id} | {a.emoji} **{a.name}** | {a.why} | {a.ideal} |")

        lines += [
            "\n## ⚠️ Challenges\n",
            "| # | Challenge | Why | Mitigation |",
            "|---|-----------|-----|------------|",
        ]
        for c in analysis.challenges:
            lines.append(f"| {c.id} | {c.name} | {c.risk} | {c.mitigation} |")

        lines += [
            "\n## 🎯 Edge Cases\n",
            "| # | Scenario | Expected behavior |",
            "|---|---------|-------------------|",
        ]
        for e in analysis.edge_cases:
            lines.append(f"| {e.id} | {e.scenario} | {e.expected} |")

        return "\n".join(lines)

    def msg2_approach(self, fix: Fix) -> str:
        """Message 2: APPROACH - IDE-style diff, verbose."""
        lines = [
            "## 🔧 Approach\n",
            f"**Strategy:** {fix.strategy}\n",
        ]
        for i, c in enumerate(fix.changes, 1):
            lines += [
                f"### Change {i}/{len(fix.changes)}",
                f"**File:** `{c.file}`" + (" *(all occurrences)*" if c.replace_all else ""),
                "```diff",
                f"- {c.old}",
                f"+ {c.new}",
                "```\n",
            ]

        if fix.not_changed:
            lines.append("### ⚠️ NOT changed (intentional)\n")
            for nc in fix.not_changed:
                lines.append(f"- **`{nc.file}`** - {nc.line_desc}: {nc.reason}")

        lines += [
            "\n### New test",
            "```python",
            fix.test_code,
            "```",
        ]
        return "\n".join(lines)

    def msg3_performance(self, review: ReviewResult, attempt: int) -> str:
        """Message 3: PERFORMANCE - graded checklist + debate."""
        lines = ["## 📊 Performance\n"]

        # Split grades by type prefix
        all_grades = []
        for v in review.votes:
            all_grades.extend(v.grades)

        # Deduplicate by id (take first vote's grades as canonical)
        seen = set()
        unique_grades = []
        for g in review.votes[0].grades if review.votes else []:
            if g.id not in seen:
                seen.add(g.id)
                unique_grades.append(g)

        aspects = [g for g in unique_grades if g.id.startswith("A")]
        challenges = [g for g in unique_grades if g.id.startswith("C")]
        edges = [g for g in unique_grades if g.id.startswith("E")]

        if aspects:
            lines += ["### Aspects", "| # | Item | ✅/❌ | Remark |", "|---|------|-------|--------|"]
            for g in aspects:
                lines.append(f"| {g.id} | {g.item} | {'✅' if g.passed else '❌'} | {g.remark} |")

        if challenges:
            lines += ["\n### Challenges", "| # | Item | ✅/❌ | Remark |", "|---|------|-------|--------|"]
            for g in challenges:
                lines.append(f"| {g.id} | {g.item} | {'✅' if g.passed else '❌'} | {g.remark} |")

        if edges:
            lines += ["\n### Edge Cases", "| # | Item | ✅/❌ | Remark |", "|---|------|-------|--------|"]
            for g in edges:
                lines.append(f"| {g.id} | {g.item} | {'✅' if g.passed else '❌'} | {g.remark} |")

        lines.append("\n### 🗣️ Debate\n")
        for v in review.votes:
            icon = "✅" if v.approve else "❌"
            lines.append(f"- **@{v.agent}:** {icon} {v.reason}")

        lines.append(
            f"\n**Score: {review.aspect_score} aspects | "
            f"{review.challenge_score} challenges | "
            f"{review.edge_case_score} edge cases** | Attempt {attempt}"
        )
        return "\n".join(lines)

    def msg4_ci_running(self, branch: str, issue_number: int, summary: str, test_count: str) -> str:
        """Message 4: CI RUNNING."""
        return (
            "## 🔄 PR generated. CI running.\n\n"
            f"- **Branch:** `{branch}`\n"
            f"- **Commit:** `fix: {summary} (#{issue_number})`\n"
            f"- **Tests:** ✅ {test_count} local\n"
            f"- **CI pipeline:** ⏳ running..."
        )

    def msg5_pr_created(self, pr_url: str, fix: Fix, issue_number: int, attempt: int) -> str:
        """Message 5: PR CREATED."""
        change_files = ", ".join(f"`{c.file}`" for c in fix.changes)
        not_changed_lines = ""
        if fix.not_changed:
            items = "; ".join(f"{nc.line_desc} ({nc.reason})" for nc in fix.not_changed)
            not_changed_lines = f"\n**What was NOT changed (and why):** {items}"

        return (
            f"## ✅ PR created\n\n"
            f"**Link:** {pr_url}\n\n"
            f"**Summary:** {fix.summary}\n"
            f"**Files:** {change_files}\n"
            f"**Attempts:** {attempt}\n"
            f"**What changed:** {len(fix.changes)} code change(s), 1 new test\n"
            f"**Why:** {fix.strategy}"
            f"{not_changed_lines}\n\n"
            f"Waiting for maintainer review."
        )
