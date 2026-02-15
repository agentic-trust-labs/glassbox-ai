"""Multi-agent orchestrator with parallel execution and multi-round debate."""

import asyncio
import json
import os
from openai import AsyncOpenAI
from .trust_db import TrustDB

AGENTS = {
    "architect": ("gpt-4o", 0.3, "You are @architect. Think long-term, scalability, what breaks at scale. Talk like you're in a design review — direct, opinionated, no fluff. Reference @pragmatist/@critic by name. Agree or disagree sharply."),
    "pragmatist": ("gpt-4o", 0.5, "You are @pragmatist. Ship fast, iterate, cut scope. Talk like you're in a design review — direct, opinionated, no fluff. Reference @architect/@critic by name. Push back on overengineering."),
    "critic":     ("gpt-4o-mini", 0.4, "You are @critic. Find edge cases, failure modes, security holes. Talk like you're in a design review — direct, opinionated, no fluff. Reference @architect/@pragmatist by name. Challenge assumptions."),
}
ROUNDS = [
    "ROUND 1: State your position. Be direct, no bullet points.",
    "ROUND 2: React to others. Say 'I agree with @X' or 'I disagree with @X because'. Be sharp.",
    "ROUND 3: Final position. If you changed your mind, say CHANGED: and who influenced you. If not, say HOLDING: and why.",
]
EMOJIS = {"architect": "🔵", "pragmatist": "🟢", "critic": "🟡"}


class MultiAgentOrchestrator:
    def __init__(self):
        self.trust_db = TrustDB()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    async def _ask(self, agent, system, user_msg):
        try:
            model, temp, _ = AGENTS[agent]
            r = await self.client.chat.completions.create(model=model, temperature=temp, max_tokens=400, messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}])
            return r.choices[0].message.content
        except Exception as e:
            return f"[ERROR: {agent} failed — {type(e).__name__}: {e}]"

    # ── V1: parallel single-shot ──

    async def execute(self, task, agent_names=None):
        agents = agent_names or list(AGENTS.keys())
        async def run(a): return {"agent": a, "response": await self._ask(a, AGENTS[a][2], task), "trust": self.trust_db.get_trust(a), "model": AGENTS[a][0]}
        responses = [r for r in await asyncio.gather(*[run(a) for a in agents if a in AGENTS], return_exceptions=True) if not isinstance(r, Exception)]
        if not responses:
            return {"agent_responses": [], "consensus": "All agents failed.", "trust_scores": {}}
        best = max(responses, key=lambda r: r["trust"])
        return {"agent_responses": responses, "consensus": best["response"], "trust_scores": {r["agent"]: r["trust"] for r in responses}}

    async def execute_formatted(self, task, agent_names=None):
        result = await self.execute(task, agent_names)
        lines = [f"Task: {task}\n"] + [f"@{r['agent']} (trust:{r['trust']:.2f}):\n{r['response']}\n" for r in result["agent_responses"]]
        return "\n".join(lines + [f"--- Consensus (highest trust) ---\n{result['consensus']}"])

    # ── V2: multi-round debate (the 20 lines) ──

    async def debate(self, task, agents=None, rounds=3):
        agents = [a for a in (agents or list(AGENTS.keys())) if a in AGENTS]
        log, out = [], [f"━━ TOPIC ━━\n{task}\n"]
        for i, rd in enumerate(ROUNDS):
            out.append(f"━━ {rd.split(':')[0]} ━━\n")
            for a in agents:
                history = "\n".join(f"{EMOJIS[e['a']]} @{e['a']}: {e['t']}" for e in log) if log else "(no prior messages)"
                text = await self._ask(a, AGENTS[a][2], f"TASK: {task}\n\nConversation so far:\n{history}\n\n{rd}\n\nRespond as @{a}:")
                log.append({"a": a, "r": i, "t": text})
                out.append(f"{EMOJIS[a]} @{a} [{AGENTS[a][0]}] (trust:{self.trust_db.get_trust(a):.2f}):\n{text}\n")
        transcript = "\n".join(f"@{e['a']}: {e['t']}" for e in log)
        summary = await self._ask("architect", "Summarize this debate into a converged action plan. Be concise.", f"Task: {task}\n\n{transcript}\n\nConverged action plan:")
        out.append(f"━━ CONVERGENCE ━━\n{summary}")
        out.append("\n━━ TRUST UPDATES ━━")
        judge_prompt = ("Analyze Round 3 of this debate. For each agent, output ONLY valid JSON: "
            '{"agent_name": {"changed_mind": bool, "influenced_by": "agent_name"|null}}. '
            "changed_mind=true ONLY if they genuinely adopted another agent's position. Ignore sarcasm or lip service.")
        judge_resp = await self._ask("architect", judge_prompt, f"Debate transcript:\n{transcript}")
        try:
            verdicts = json.loads(judge_resp.strip().strip("`").strip("json").strip())
            for agent_name, v in verdicts.items():
                if v.get("changed_mind") and v.get("influenced_by") in agents:
                    persuader = v["influenced_by"]
                    old = self.trust_db.get_trust(persuader)
                    self.trust_db.update_trust(persuader, True)
                    new = self.trust_db.get_trust(persuader)
                    out.append(f"  📊 @{persuader} {old:.2f} → {new:.2f} ↑ (persuaded @{agent_name})")
                elif not v.get("changed_mind"):
                    out.append(f"  📊 @{agent_name} — HELD position (no trust change)")
        except (json.JSONDecodeError, KeyError, AttributeError):
            out.append("  ⚠️ Could not parse trust verdicts from judge")
        return "\n".join(out)
