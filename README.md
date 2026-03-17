<p align="center">
  <img src="docs/assets/agents/glasswing.svg" width="80" height="80" alt="GlassBox AI">
</p>

# GlassBox AI

> **Trust is earned, not assumed.** 💎

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![Status](https://img.shields.io/badge/status-early%20stage-orange)]()

GlassBox is an orchestration platform for autonomous AI agents, built for enterprise problems where decisions are consequential and accountability is non-negotiable.

The platform centers on one idea: **auditability, human oversight, and continuous improvement should be structural properties of agent systems - not features you bolt on afterward.**

---

## Why This Exists

Enterprise AI agents today are largely black boxes. They take actions, produce outputs, and when something goes wrong, there's no trace of what happened, no mechanism to feed corrections back, and no human with a meaningful checkpoint. Deploy them anyway and you're betting that the model is right. Most of the time, that's not good enough.

We're building an orchestration layer where:
- Every action an agent takes is logged in an append-only audit trail
- Human review is a first-class state in the execution graph, not an external wrapper
- Corrections from humans are captured, persisted, and fed back into future runs
- The agent gets measurably better over time without retraining

The design is domain-agnostic. The same engine, the same audit model, the same HITL mechanism - applied to any enterprise workflow where an AI agent acts autonomously.

---

## How the Platform Works

GlassBox is a lean state machine engine (~260 lines) that knows one thing: states exist, transitions connect them, and agents are plain functions that return events. Everything else - what the agent does, what tools it has, what the domain is - lives in self-contained use cases.

```
                    +------------------------------------------+
                    |         GlassBox Engine (core)            |
                    |  state machine, transitions, audit trail   |
                    |  never imports from use cases              |
                    +---+-------------------+-------------------+
                        |                   |
           +------------v------+   +--------v-----------+
           |   Agent (any)      |   |   HITL Memory       |
           |   plain function   |   |   RULES.md          |
           |   returns events   |   |   episodes.jsonl    |
           +------------+------+   +--------+-----------+
                        |                   |
                    +---v-------------------v---+
                    |    Use Case (self-contained)|
                    |    states, pipeline,        |
                    |    settings, tools          |
                    +---+------------------------+
                        |
                    +---v----------------------------+
                    |  Audit Trail (append-only)      |
                    |  every step: state, event,      |
                    |  agent, timestamp, cost, detail  |
                    +--------------------------------+
```

**Core properties:**
- **Append-only audit trail** - every state, event, tool call, LLM response, cost, and timestamp is logged. Not configurable. Always on.
- **HITL as a real state** - `awaiting_review` is a pause state in the machine. The engine waits, resumes with full context. Not a workaround.
- **Corrections that accumulate** - human feedback is written to `RULES.md` (injected into every future prompt) and `episodes.jsonl` (searchable by the agent at runtime via `recall_episodes`).
- **Modular use cases** - adding a new domain means adding a folder. The engine never changes.

```python
# Every agent is a plain function - same contract across all use cases and domains
def run(ctx: AgentContext, **kwargs) -> dict:
    return {"event": "done", "detail": "..."}

# Engine drives the state machine, logs every step, handles HITL pauses
engine.run(ctx, state="received")
```

---

## Use Cases

Use cases are self-contained folders that plug into the engine. Each defines its own states, agent pipeline, configuration, and tools. The engine sees none of this - it only sees state transitions and events.

### UC-1: Coding Agent (active, early stage)

An autonomous coding agent for software bug-fixing, evaluated on SWE-bench Verified - the industry-standard benchmark for coding agents.

The agent runs a tool loop (`bash`, `str_replace_editor`, `recall_episodes`) against real repositories, produces a git patch, which is then evaluated in Docker via the swebench harness.

**HITL learning loop:**
```
Run  ->  Agent produces patch
     ->  Evaluation (Docker, swebench harness)
     ->  Human reviews failure, writes correction
     ->  Correction added to RULES.md + episodes.jsonl
     ->  Next run: agent reads updated rules, can recall past corrections
```

**Where we are - first end-to-end run (3 instances):**

| Instance | Patch | Steps | Cost | Result | Correction |
|----------|:---:|:---:|---:|--------|------------|
| astropy-14365 | Yes | 10 | $0.13 | Failed - read path fixed, write path missed | "re.IGNORECASE alone insufficient - write path needs uppercase too" |
| astropy-14539 | Yes | 29 | $0.66 | Failed - wrong approach to VLA comparison | "Use element-wise comparison for object-dtype arrays" |
| astropy-14508 | Yes | 9 | $0.09 | Partial - target test passed, caused regression | "str() gives lowercase e, FITS spec requires uppercase E" |

3/3 patches produced. 0/3 passed evaluation. 4 corrections captured. $0.88 total cost.

The pass rate is not the point yet. The loop is: failures become corrections, corrections become rules, rules improve the next run. Whether this compounds is what we're measuring.

---

## Comparison

How GlassBox compares to existing agent frameworks and platforms:

| | [LangGraph](https://github.com/langchain-ai/langgraph) | [CrewAI](https://github.com/crewAIInc/crewAI) | [OpenHands](https://github.com/All-Hands-AI/OpenHands) | [SWE-agent](https://github.com/SWE-agent/SWE-agent) | [Devin](https://devin.ai) | **GlassBox** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Orchestration layer** | Graph-based | Role-based | Single agent | Single agent | Proprietary | State machine |
| **Audit trail (structural)** | No | No | No | Trajectories only | No | Yes - every step |
| **HITL as first-class state** | Partial | No | No | No | Partial | Yes |
| **Corrections fed back to agent** | No | No | No | No | No | Yes - rules + episodes |
| **Domain-agnostic use cases** | Yes | Yes | No | No | No | Yes |
| **Modular / pluggable** | Yes | Yes | No | No | No | Yes |
| **Open source** | Yes | Yes | Yes | Yes | No | Yes |
| **SWE-bench score** | N/A | N/A | 37% | 43% | Undisclosed | 0% (n=3, WIP) |
| **Production-ready** | Yes | Yes | Yes | Yes | Yes | No |

**Where GlassBox is behind:**
- **SWE-bench score** - 0% on 3 instances. Not competitive. The agent loop works; the patches aren't good enough yet.
- **Production-ready** - Early stage. No production deployments, no hardened APIs, no enterprise support.
- **Ecosystem** - LangGraph and CrewAI have large ecosystems, integrations, and community. We have none of that.
- **Sandboxing** - Agent runs locally. Evaluation is in Docker. Full inference sandboxing is not built yet.

**Where GlassBox is different:**
- **HITL is structural, not optional** - In LangGraph you can add human-in-the-loop as a graph node. In GlassBox, `awaiting_review` is a native state - the engine was designed around it, not patched to support it.
- **Corrections compound** - No other framework has a mechanism where human corrections become version-controlled rules that every future agent run reads. `RULES.md` and `episodes.jsonl` are the start of that.
- **Audit trail is not observability** - Observability tools (LangSmith, Arize, etc.) log what happened. GlassBox's audit trail is structural - it's the execution record the engine produces, tied to the state machine, not a separate monitoring layer.
- **Lean by design** - The engine is ~260 lines. Agents are plain functions. There is no framework magic to debug.

---

## Project Structure

```
src/glassbox/
  core/
    engine.py         State machine: step(), run(), audit trail
    state.py          BaseState enum + BASE_TRANSITIONS
    models.py         AgentContext, AuditEntry, TriageResult

  use_cases/
    coder/            UC-1: Coding agent (SWE-bench)
      pipeline.py     Agent loop, tool dispatch, patch extraction
      states.py       State transitions for this use case
      settings.py     Config keys with defaults
      tools.py        bash, str_replace_editor, complete
      RULES.md        27 accumulated rules (version-controlled)
      run_swebench.py Batch runner for SWE-bench instances
      memory/
        episodes.py   Episode store + recall_episodes tool
        episodes.jsonl Correction history (append-only)
```

---

## Quick Start

```bash
git clone https://github.com/agentic-trust-labs/glassbox-ai.git
cd glassbox-ai
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # Set OPENAI_API_KEY and GLASSBOX_MODEL=gpt-4o

# Run the coding agent on a SWE-bench instance
python src/glassbox/use_cases/coder/run_swebench.py \
    --dataset SWE-bench/SWE-bench_Verified \
    --split test \
    --instance_ids astropy__astropy-14365 \
    --output predictions.json

# Evaluate with Docker
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
python -m swebench.harness.run_evaluation \
    --dataset_name SWE-bench/SWE-bench_Verified \
    --predictions_path predictions.json \
    --max_workers 1 --run_id my_eval
```

---

## What's Next

- [ ] Re-run 3 instances with accumulated corrections, measure if pass rate improves
- [ ] Scale to 50+ SWE-bench instances
- [ ] Full Docker sandboxing for agent inference
- [ ] Validate that `recall_episodes` measurably changes agent behavior
- [ ] Second use case (domain TBD) to validate platform generality

---

## Research Foundation

- [Reflexion](https://arxiv.org/abs/2303.11366) (NeurIPS 2023) - Verbal reinforcement learning: corrections as learning signal
- [HULA](https://arxiv.org) (ICSE 2025) - 54% of agent outputs had defects without human review
- [SWE-agent](https://arxiv.org/abs/2405.15793) (NeurIPS 2024) - Agent-computer interfaces for software engineering
- [Agentless](https://arxiv.org/abs/2407.01489) - Localize, repair, validate - no agent loop needed
- [OpenAI GPT-4.1 Guide](https://cookbook.openai.com/examples/gpt4-1_prompting_guide) - Persistence + tool-calling + planning

---

MIT - [Sourabh Gupta](https://www.linkedin.com/in/sourabhgupta16/) / [Agentic Trust Labs](https://github.com/agentic-trust-labs)

**Trust is earned, not assumed. 💎**
