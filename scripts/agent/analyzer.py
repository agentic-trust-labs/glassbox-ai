"""GlassBox Agent v0.3-beta - Phase 1: THINK before coding."""

import json

from openai import OpenAI

from .config import MODEL, TEMPERATURE_ANALYZE, CORE_ASPECTS
from .memory import Memory
from .models import Analysis


ANALYZE_PROMPT = """You are a senior engineer about to fix a GitHub issue. BEFORE writing any code, think deeply.

Issue #{issue_number}: {issue_title}
{issue_body}

Repository map (PageRank-ranked classes, functions, signatures):
{repo_map}

Source files:
{sources}

{past_reflections}

MANDATORY CORE ASPECTS (include ALL of these, tailored to THIS issue):
{core_aspects}

Generate a structured analysis in JSON:
{{
  "aspects": [
    {{
      "id": "A1",
      "emoji": "relevant emoji",
      "name": "short name",
      "why": "why this aspect matters for THIS issue",
      "ideal": "how the ideal solution performs on this aspect"
    }}
  ],
  "challenges": [
    {{
      "id": "C1",
      "name": "short name",
      "risk": "what could go wrong",
      "mitigation": "how to avoid it"
    }}
  ],
  "edge_cases": [
    {{
      "id": "E1",
      "scenario": "specific input or scenario",
      "expected": "what should happen"
    }}
  ]
}}

Rules:
- MUST include ALL {num_core} core aspects above (A1-A{num_core}), with "why" and "ideal" tailored to THIS specific issue
- Add 1-5 MORE issue-specific aspects after the core ones (A{next_id}+)
- 5-10 challenges covering: what could break, what traps exist, what the agent might get wrong
- Edge cases: follow Marginal Return of Utility (MRU) - T1 happy path + T2 input + T3 error + T4 boundary per affected function
- CRITICAL: if the issue involves SQL/regex/HTML/embedded DSL, at least 3 edge cases MUST cover cross-boundary scenarios
- CRITICAL: if the issue involves an external SDK, at least 2 edge cases MUST cover return type verification
- Think about what would make a PR reviewer reject the fix
- Think about what would make tests fail"""


class Analyzer:
    """Phase 1: generate aspects, challenges, edge cases before coding."""

    def __init__(self, client: OpenAI, memory: Memory):
        self.client = client
        self.memory = memory

    def analyze(
        self,
        issue_number: int,
        issue_title: str,
        issue_body: str,
        sources: dict[str, str],
        repo_map: str = "",
    ) -> Analysis:
        """Generate structured analysis for the issue."""
        past = self.memory.format_for_prompt(issue_title)
        num_core = len(CORE_ASPECTS)
        core_formatted = "\n".join(
            f"  {a['id']}. {a['emoji']} {a['name']} - {a['why']} (ideal: {a['ideal']})"
            for a in CORE_ASPECTS
        )

        prompt = ANALYZE_PROMPT.format(
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
            repo_map=repo_map or '(not available)',
            sources=json.dumps(sources, indent=2),
            past_reflections=past,
            core_aspects=core_formatted,
            num_core=num_core,
            next_id=num_core + 1,
        )

        response = self.client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE_ANALYZE,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content)
        return Analysis(**data)
