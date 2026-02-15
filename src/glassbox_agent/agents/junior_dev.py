"""GlassBox Junior Dev — generates and applies code fixes guided by templates."""

from __future__ import annotations

import json

from openai import OpenAI

from glassbox_agent.core.base_agent import BaseAgent
from glassbox_agent.core.models import EdgeCase, Fix, LineEdit, TriageResult
from glassbox_agent.core.settings import Settings
from glassbox_agent.core.template import Template
from glassbox_agent.tools.code_editor import CodeEditor
from glassbox_agent.tools.file_reader import FileReader
from glassbox_agent.tools.github_client import GitHubClient


FIX_PROMPT = """You are GlassBox Junior Dev. Fix ONLY the bug described below.

Issue #{issue_number}: {title}
{body}

Template: {template_id} — {template_name}
Template instructions:
{coder_instructions}

Aspects to satisfy:
{aspects}

Challenges to watch for:
{challenges}

Edge cases to handle:
{edge_cases}

Source files:
{all_sources}

{feedback}

Return ONLY valid JSON:
{{
  "edits": [
    {{
      "file": "src/glassbox/example.py",
      "start_line": 12,
      "end_line": 12,
      "new_text": "    \"critic\":     (\"gpt-4o-mini\", 0.4, \"...\"),\n"
    }}
  ],
  "test_code": "def test_fix():\\n    ...",
  "summary": "one-line commit message",
  "strategy": "brief approach description"
}}

CRITICAL RULES:
- Change ONLY the specific value/string the issue describes. Do NOT touch any other lines.
- The "file" MUST be the full relative path like "src/glassbox/orchestrator.py"
- The "new_text" MUST preserve the EXACT original indentation and trailing newline
- Usually only 1 edit of 1 line is needed. Do NOT rewrite functions or add code.
- Line numbers must match the numbered source shown above
- Include a test that verifies the fix"""


class JuniorDev(BaseAgent):
    """Receives template + briefing from Manager, generates and applies the fix."""

    def __init__(self, client: OpenAI, github: GitHubClient, settings: Settings,
                 editor: CodeEditor, file_reader: FileReader):
        super().__init__(name="GlassBox Junior Dev", avatar="\U0001f9ab", client=client, github=github, settings=settings,
                         avatar_img="beaver.svg", title="The Builder")
        self.editor = editor
        self.reader = file_reader

    def think(self, context: dict) -> str:
        return "Reading source file and generating fix..."

    def act(self, context: dict) -> dict:
        return {"fix": self.generate_fix(**context)}

    def generate_fix(self, issue_number: int, title: str, body: str,
                     template: Template, triage: TriageResult,
                     sources: dict[str, str], feedback: str = "") -> Fix:
        """Generate a code fix guided by template + Manager's briefing."""
        aspects_text = "\n".join(
            f"- {a.get('id', '?')}: {a.get('name', '?')}" for a in triage.soft_aspects
        )
        challenges_text = "\n".join(
            f"- {c.get('id', '?')}: {c.get('name', '?')} — {c.get('risk', '')}" for c in triage.soft_challenges
        )
        edge_cases_text = "\n".join(
            f"- {ec.tier}: {ec.scenario} → {ec.expected}" for ec in triage.edge_cases
        )

        # Build numbered source for ALL files
        all_sources_parts = []
        for fpath, content in sources.items():
            numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(content.split("\n")))
            all_sources_parts.append(f"── {fpath} ──\n{numbered}")
        all_sources_text = "\n\n".join(all_sources_parts) if all_sources_parts else "(no sources)"

        feedback_section = f"\nPREVIOUS ATTEMPT FEEDBACK:\n{feedback}" if feedback else ""

        prompt = FIX_PROMPT.format(
            issue_number=issue_number,
            title=title,
            body=body,
            template_id=template.id,
            template_name=template.name,
            coder_instructions=template.coder_instructions,
            aspects=aspects_text or "(none)",
            challenges=challenges_text or "(none)",
            edge_cases=edge_cases_text or "(none)",
            all_sources=all_sources_text,
            feedback=feedback_section,
        )

        raw = self._call_llm(prompt, temperature=self.settings.temperature_code, json_mode=True)
        data = json.loads(raw)

        edits = [LineEdit(**e) for e in data.get("edits", [])]
        return Fix(
            edits=edits,
            test_code=data.get("test_code", ""),
            summary=data.get("summary", "fix bug"),
            strategy=data.get("strategy", ""),
        )

    def apply_fix(self, fix: Fix) -> tuple[bool, str]:
        """Apply fix edits to the repo. Returns (ok, error)."""
        return self.editor.apply_all(fix.edits)

    def format_comment(self, fix: Fix) -> str:
        """Format fix details as a GitHub comment."""
        lines = ["Generating fix...\n"]
        for edit in fix.edits:
            lines.append(f"**[{edit.file}](https://github.com/{self.settings.repo}/blob/main/{edit.file}#L{edit.start_line})** line {edit.start_line}-{edit.end_line}:")
            lines.append(f"```python\n{edit.new_text}```")
        lines.append(f"\n**Strategy:** {fix.strategy}")
        lines.append(f"**Lines changed:** {sum(e.end_line - e.start_line + 1 for e in fix.edits)}")
        lines.append("\n🧪 **Tester**, over to you.")
        return "\n".join(lines)
