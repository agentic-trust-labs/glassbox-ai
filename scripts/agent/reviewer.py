"""GlassBox Agent v0.3-beta - Phase 3: debate + grade against checklist."""

import json

from openai import OpenAI

from .config import MODEL, TEMPERATURE_REVIEW, DEBATE_AGENTS
from .models import Analysis, Fix, DebateVote, Grade, ReviewResult


REVIEW_PROMPT = """You are @{agent_name} reviewing a code fix for GlassBox AI.

Issue: {issue_title}

ANALYSIS CHECKLIST (grade EVERY item):
{analysis_json}

PROPOSED FIX:
{fix_json}

RESULTING CODE after applying fix:
{preview}

TEST RESULTS:
{test_output}

Your role: {instruction}

Return ONLY valid JSON:
{{
  "approve": true/false,
  "reason": "one line summary",
  "grades": [
    {{"id": "A1", "item": "aspect name", "passed": true/false, "remark": "why"}},
    {{"id": "C1", "item": "challenge name", "passed": true/false, "remark": "why"}},
    {{"id": "E1", "item": "edge case name", "passed": true/false, "remark": "why"}}
  ]
}}

Rules:
- Grade EVERY aspect (A#), challenge (C#), and edge case (E#) from the checklist.
- For @critic: your job is to BREAK the fix. Try to find scenarios where it fails.
- If ANY edge case fails, you MUST set approve=false.
- Check: are Python variables leaking into SQL/HTML/regex strings?
- Check: are SDK return types correct (objects vs dicts)?
- Check: will existing tests still pass?"""


class Reviewer:
    """Phase 3: debate agents grade the fix against the analysis checklist."""

    def __init__(self, client: OpenAI):
        self.client = client

    def review(
        self,
        fix: Fix,
        analysis: Analysis,
        sources: dict[str, str],
        issue_title: str,
        test_output: str = "",
    ) -> ReviewResult:
        """Run debate: each agent grades every A#, C#, E# item."""
        # Build preview of code after fix
        preview = self._build_preview(fix, sources)
        analysis_json = analysis.model_dump_json(indent=2)
        fix_json = fix.model_dump_json(indent=2)

        votes: list[DebateVote] = []
        for agent_name, instruction in DEBATE_AGENTS.items():
            prompt = REVIEW_PROMPT.format(
                agent_name=agent_name,
                issue_title=issue_title,
                analysis_json=analysis_json,
                fix_json=fix_json,
                preview=json.dumps(preview, indent=2),
                test_output=test_output or "(not yet run)",
                instruction=instruction,
            )

            response = self.client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE_REVIEW,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

            data = json.loads(response.choices[0].message.content)
            grades = [Grade(**g) for g in data.get("grades", [])]
            vote = DebateVote(
                agent=agent_name,
                approve=data["approve"],
                reason=data["reason"],
                grades=grades,
            )
            votes.append(vote)
            icon = "✅" if vote.approve else "❌"
            print(f"  @{agent_name}: {icon} {vote.reason}")

        # Compute scores from first voter's grades (canonical)
        approved = sum(1 for v in votes if v.approve) >= 2
        aspect_score = self._score(votes[0].grades, "A") if votes else "0/0"
        challenge_score = self._score(votes[0].grades, "C") if votes else "0/0"
        edge_case_score = self._score(votes[0].grades, "E") if votes else "0/0"

        return ReviewResult(
            approved=approved,
            votes=votes,
            aspect_score=aspect_score,
            challenge_score=challenge_score,
            edge_case_score=edge_case_score,
        )

    def _build_preview(self, fix: Fix, sources: dict[str, str]) -> dict[str, str]:
        """Apply fix to sources in memory, return preview."""
        preview = dict(sources)
        for change in fix.changes:
            content = preview.get(change.file, "")
            if change.replace_all:
                content = content.replace(change.old, change.new)
            else:
                content = content.replace(change.old, change.new, 1)
            preview[change.file] = content
        return preview

    @staticmethod
    def _score(grades: list[Grade], prefix: str) -> str:
        filtered = [g for g in grades if g.id.startswith(prefix)]
        passed = sum(1 for g in filtered if g.passed)
        return f"{passed}/{len(filtered)}"
