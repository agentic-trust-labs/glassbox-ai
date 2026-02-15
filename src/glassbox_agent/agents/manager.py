"""GlassBox Manager — classifies issues, generates briefing (aspects, challenges, edge cases), delegates."""

from __future__ import annotations

import json

from openai import OpenAI

from glassbox_agent.core.base_agent import BaseAgent
from glassbox_agent.core.constants import HARD_ASPECTS, HARD_CHALLENGES
from glassbox_agent.core.models import TriageResult, EdgeCase
from glassbox_agent.core.settings import Settings
from glassbox_agent.core.template import Template, TemplateLoader
from glassbox_agent.memory.store import MemoryStore
from glassbox_agent.tools.github_client import GitHubClient


CLASSIFY_PROMPT = """You are GlassBox Manager. Classify this GitHub issue and generate a full briefing.

Issue #{issue_number}: {title}
{body}

Source file contents:
{sources}

Available templates: {template_list}

INSTRUCTIONS:
1. Pick the best template_id from the list above.
2. Rate your confidence 0.0-1.0.
3. If this is a question or duplicate, set skip_reason. Bugs AND code improvements are both valid — do NOT skip them.
4. Pick relevant soft_aspects from: SA1 Cross-boundary safety, SA2 Idempotency, SA3 Type correctness, SA4 No hardcoding, SA5 Readability
5. Generate 1-3 issue-specific soft_challenges (risks the developer should watch for).
6. Generate 4-8 edge_cases using MRU: T1 happy path, T2 input variation, T3 error path, T4 boundary.

{past_reflections}

Return ONLY valid JSON:
{{
  "template_id": "...",
  "confidence": 0.95,
  "skip_reason": null,
  "soft_aspects": [{{"id": "SA1", "name": "...", "reason": "..."}}],
  "soft_challenges": [{{"id": "SC1", "name": "...", "risk": "..."}}],
  "edge_cases": [{{"tier": "T1", "scenario": "...", "expected": "..."}}]
}}"""


class Manager(BaseAgent):
    """Classifies issues, generates full briefing, delegates to JuniorDev + Tester."""

    def __init__(self, client: OpenAI, github: GitHubClient, settings: Settings,
                 template_loader: TemplateLoader, memory: MemoryStore):
        super().__init__(name="GlassBox Manager", avatar="\U0001f989", client=client, github=github, settings=settings,
                         avatar_img="owl.svg", title="The Strategist")
        self.templates = template_loader
        self.memory = memory

    def think(self, context: dict) -> str:
        return "Classifying issue and generating briefing..."

    def act(self, context: dict) -> dict:
        return self.classify(
            issue_number=context["issue_number"],
            title=context["title"],
            body=context["body"],
            sources=context.get("sources", {}),
        )

    def classify(self, issue_number: int, title: str, body: str, sources: dict) -> TriageResult:
        """LLM classifies → template_id + confidence + aspects + challenges + edge_cases."""
        template_list = ", ".join(t.id for t in self.templates.all())
        past = self.memory.format_for_prompt(title)

        source_text = ""
        for path, content in sources.items():
            lines = content.split("\n")
            numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))
            source_text += f"\n--- {path} ---\n{numbered}\n"

        prompt = CLASSIFY_PROMPT.format(
            issue_number=issue_number,
            title=title,
            body=body,
            sources=source_text or "(no sources provided)",
            template_list=template_list,
            past_reflections=past,
        )

        raw = self._call_llm(prompt, temperature=self.settings.temperature_classify, json_mode=True, model=self.settings.model_classify)
        data = json.loads(raw)

        edge_cases = [EdgeCase(**ec) for ec in data.get("edge_cases", [])]

        return TriageResult(
            template_id=data["template_id"],
            confidence=data.get("confidence", 0.5),
            skip_reason=data.get("skip_reason"),
            soft_aspects=data.get("soft_aspects", []),
            soft_challenges=data.get("soft_challenges", []),
            edge_cases=edge_cases,
        )

    def format_briefing(self, triage: TriageResult, template: Template) -> str:
        """Format the full briefing as a GitHub comment body."""
        lines = []
        lines.append(f"| | |")
        lines.append(f"|---|---|")
        lines.append(f"| 📋 **Template** | `{template.id}` — {template.name}: {template.description} |")
        lines.append(f"| 🎯 **Confidence** | {triage.confidence:.0%} |")
        if triage.skip_reason:
            lines.append(f"| ⏭️ **Skip** | {triage.skip_reason} |")
            return "\n".join(lines)

        lines.append("")
        lines.append("**Aspects:**")
        hard = " · ".join(f"{a['name']}" for i, a in enumerate(HARD_ASPECTS))
        lines.append(f"<details><summary>🔴 Hard Aspects (5)</summary>\n\n- {hard}\n</details>")
        if triage.soft_aspects:
            soft = " · ".join(f"{a.get('id', '?')} {a.get('name', '?')}" for a in triage.soft_aspects)
            lines.append(f"- 🟡 {soft}")

        lines.append("")
        lines.append("**Challenges:**")
        hard_c = " · ".join(f"{c['name']}" for i, c in enumerate(HARD_CHALLENGES))
        lines.append(f"<details><summary>🔴 Hard Challenges (5)</summary>\n\n- {hard_c}\n</details>")
        if triage.soft_challenges:
            for sc in triage.soft_challenges:
                lines.append(f"- 🟡 {sc.get('name', '?')}: {sc.get('risk', '?')}")

        if triage.edge_cases:
            lines.append("")
            lines.append("**Edge Cases (MRU):**")
            tier_emoji = {"T1": "🟢", "T2": "🟡", "T3": "🟠", "T4": "🔴"}
            for ec in triage.edge_cases:
                emoji = tier_emoji.get(ec.tier, "⚪")
                lines.append(f"- {emoji} {ec.tier}: `{ec.scenario}` → {ec.expected}")

        lines.append("")
        lines.append(f"🔧 **Junior Dev**, your mission. Template: `{template.id}`. Go.")
        return "\n".join(lines)
