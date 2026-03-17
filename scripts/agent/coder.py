"""GlassBox Agent v0.3-beta - Phase 2: generate code approach."""

import json

from openai import OpenAI

from .config import MODEL, TEMPERATURE_CODE
from .models import Analysis, Fix


CODE_PROMPT = """You are a senior Python developer fixing a GitHub issue for GlassBox AI.

Issue #{issue_number}: {issue_title}
{issue_body}

{retry_context}

Source files:
{sources}

ANALYSIS (you MUST satisfy every aspect, challenge, and edge case):
{analysis_json}

Return ONLY valid JSON:
{{
  "changes": [
    {{
      "file": "path/to/file.py",
      "old": "exact string to replace",
      "new": "replacement string",
      "replace_all": false
    }}
  ],
  "not_changed": [
    {{
      "file": "path/to/file.py",
      "line_desc": "Line 7: DEFAULT 0.85 in SQL CREATE",
      "reason": "SQL literal evaluated by SQLite, not Python"
    }}
  ],
  "test_code": "def test_N_description():\\n    ...",
  "summary": "one-line commit message",
  "strategy": "brief description of approach taken"
}}

Rules:
- Minimal fix only. Max 10-15 lines of actual change.
- "old" must be an EXACT substring of the current file content.
- NEVER replace literals inside SQL strings, f-strings, or embedded DSLs with Python variables.
- Use SEPARATE change entries for different contexts.
- Include ONE test function that verifies the fix.
- The test MUST check ALL changed locations.
- List files/lines you intentionally did NOT change in "not_changed" with reasons.
- Follow existing code style exactly.
- Do not change comments or docstrings unless the issue requires it.
- If a previous attempt failed, use a DIFFERENT strategy (do not retry the same approach)."""


class Coder:
    """Phase 2: generate the code fix based on analysis."""

    def __init__(self, client: OpenAI):
        self.client = client

    def generate_fix(
        self,
        issue_number: int,
        issue_title: str,
        issue_body: str,
        sources: dict[str, str],
        analysis: Analysis,
        prev_error: str | None = None,
    ) -> Fix:
        """Generate a code fix that satisfies the analysis checklist."""
        retry_context = ""
        if prev_error:
            retry_context = (
                f"\nPREVIOUS ATTEMPT FAILED:\n{prev_error}\n\n"
                "Use a DIFFERENT strategy. Do NOT retry the same approach."
            )

        analysis_json = analysis.model_dump_json(indent=2)

        prompt = CODE_PROMPT.format(
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
            retry_context=retry_context,
            sources=json.dumps(sources, indent=2),
            analysis_json=analysis_json,
        )

        response = self.client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE_CODE,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content)
        return Fix(**data)
