<p align="center">
  <img src="docs/assets/agents/glasswing.svg" width="80" height="80" alt="GlassBox AI">
</p>

# GlassBox AI

**Autonomous coding agents for enterprise engineering - where every ticket costs real money and every bad merge costs more.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![Status](https://img.shields.io/badge/status-early%20stage-orange)]()

Enterprise AI needs agents that improve with oversight, not despite it. GlassBox is our approach: a state machine that orchestrates coding agents with a full audit trail, human-in-the-loop checkpoints, and a correction mechanism where every failed patch makes the next run smarter.

Still early. The learning loop is built. We're now running it and measuring.

---

## The Approach

Most coding agents are stateless. They don't learn from corrections. When a human rejects a patch and explains why, that knowledge disappears.

GlassBox takes a different approach:

- **Rules that accumulate.** Human corrections are written to `RULES.md` - a version-controlled file injected into every agent prompt. Currently 27 rules, bootstrapped from studying how the top SWE-bench agents (Codex CLI, OpenHands, Augment Code, Cursor, Aider, Claude Code, mini-swe-agent) handle common failure modes.

- **Episodes that persist.** Every correction is also logged to `episodes.jsonl`. The agent has a `recall_episodes` tool to search past corrections during problem-solving.

- **Audit trail by default.** Every state transition, tool call, and LLM response is logged. When a patch fails, you can trace what happened. This isn't a feature we added - it's how the state machine works.

- **Human checkpoints as real states.** The engine pauses, waits for human input, and resumes with full context. Not a bolt-on.

```
Issue  ->  Agent loop (bash + str_replace_editor + LLM)
       ->  Patch produced
       ->  Evaluation (swebench Docker harness)
       ->  Human reviews
       ->  If rejected: correction captured, rules updated
       ->  Next run starts with more context
```

---

## Where We Are

We ran 3 SWE-bench Verified instances end-to-end:

| Instance | Patch | Steps | Cost | Result | Correction Captured |
|----------|:---:|:---:|---:|--------|---------------------|
| astropy-14365 | Yes | 10 | $0.13 | Failed - incomplete (read path only, not write path) | "re.IGNORECASE alone insufficient" |
| astropy-14539 | Yes | 29 | $0.66 | Failed - wrong approach to VLA comparison | "Use element-wise comparison for object-dtype" |
| astropy-14508 | Yes | 9 | $0.09 | Partial - target test passed, caused regression | "str() gives lowercase e, FITS needs uppercase E" |

**3/3 patches produced. 0/3 passed. 4 corrections captured. $0.88 total.**

The agent produces patches. They're not good enough yet. Each failure produced a structured correction that feeds into the next run. Whether this compounds into meaningful improvement is the open question.

---

## How It Works

The core is a state machine engine (~260 lines) that drives transitions and logs every step. Use cases are self-contained folders - adding one doesn't require touching the engine.

The first use case is a coding agent:

```
src/glassbox/
  core/                 State machine engine, models, base states
  use_cases/
    coder/
      pipeline.py       Agent loop: LLM calls, tool dispatch, patch extraction
      tools.py          bash, str_replace_editor, complete (Anthropic-style)
      RULES.md          27 rules injected into system prompt
      run_swebench.py   Batch runner for SWE-bench instances
      memory/
        episodes.py     Episode store + recall_episodes tool
        episodes.jsonl  Correction history (append-only)
```

**Tools:** `bash`, `str_replace_editor`, `complete`, `recall_episodes`
**Model:** Any model via litellm (currently GPT-4o)
**Prompt design:** Based on [OpenAI's GPT-4.1 guide](https://cookbook.openai.com/examples/gpt4-1_prompting_guide) - persistence, tool-calling, planning
**Evaluation:** Docker containers via swebench harness, same setup as every leaderboard submission

---

## Landscape

For context on where this sits:

| | SWE-bench | Learns from Corrections | Audit Trail | Open Source |
|---|:---:|:---:|:---:|:---:|
| [SWE-agent](https://github.com/SWE-agent/SWE-agent) | 43% | No | Trajectories | Yes |
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | 37% | No | Conversation logs | Yes |
| [Agentless](https://github.com/OpenAutoCoder/Agentless) | 27% | No | No | Yes |
| **GlassBox** | **0% (n=3)** | **In progress** | **State machine log** | **Yes** |

The benchmark score is not competitive. The bet is that a correction loop - rules that accumulate, episodes that persist, humans that stay in the loop - is the right foundation for enterprise reliability. That's unproven. We're working on proving it.

---

## Quick Start

```bash
git clone https://github.com/agentic-trust-labs/glassbox-ai.git
cd glassbox-ai
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # Set OPENAI_API_KEY and GLASSBOX_MODEL=gpt-4o

python src/glassbox/use_cases/coder/run_swebench.py \
    --dataset SWE-bench/SWE-bench_Verified \
    --split test \
    --instance_ids astropy__astropy-14365 \
    --output predictions.json
```

---

## What's Next

- [ ] Re-run 3 instances with accumulated corrections, measure if pass rate improves
- [ ] Scale to 50+ SWE-bench instances to get a statistically meaningful score
- [ ] Docker sandboxing for agent inference, not just evaluation
- [ ] Test whether `recall_episodes` meaningfully changes agent behavior
- [ ] Multi-language support beyond Python

---

## Related Work

- [Reflexion](https://arxiv.org/abs/2303.11366) (NeurIPS 2023) - Verbal reinforcement learning for agents
- [HULA](https://arxiv.org) (ICSE 2025) - Human-in-the-loop study: 54% said code had defects without human oversight
- [SWE-agent](https://github.com/SWE-agent/SWE-agent) (NeurIPS 2024) - Agent-computer interfaces for software engineering
- [Agentless](https://github.com/OpenAutoCoder/Agentless) - Localize, repair, validate without an agent loop
- [OpenAI GPT-4.1 Guide](https://cookbook.openai.com/examples/gpt4-1_prompting_guide) - Persistence + tool-calling + planning

---

MIT - [Sourabh Gupta](https://www.linkedin.com/in/sourabhgupta16/) / [Agentic Trust Labs](https://github.com/agentic-trust-labs)
