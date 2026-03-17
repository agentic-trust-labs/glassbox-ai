<p align="center">
  <img src="docs/assets/agents/glasswing.svg" width="80" height="80" alt="GlassBox AI">
</p>

# GlassBox AI

> We are exploring GlassBox as an orchestration platform for autonomous AI agents, built for enterprise problems where each decision costs hundreds — and each bad one costs more.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![Status](https://img.shields.io/badge/status-early%20stage-orange)]()

---

## The Platform

Enterprise AI agents today are largely black boxes. They take actions, produce outputs, and when something goes wrong, there is no trace of what happened, no mechanism to feed corrections back, and no human with a meaningful checkpoint. Existing orchestration tools — LangGraph, CrewAI, AutoGen — solve the wiring problem well. They do not solve the accountability problem. You get a graph of agents; you do not get auditability, you do not get a correction loop, and human oversight is something you bolt on manually if you think of it.

GlassBox is an attempt to build the orchestration layer where accountability is structural — not optional, not a plugin, not an afterthought.

**What it does:**
- Runs agents as state machines with explicit, traceable transitions
- Logs every step — state, event, tool call, LLM response, cost, timestamp — in an append-only audit trail. Always on. Not configurable.
- Treats human review as a first-class pause state: the engine pauses, waits, resumes with full context
- Captures human corrections and feeds them back into future agent runs as version-controlled rules (`RULES.md`) and a searchable episode store (`episodes.jsonl`)

**What it does not do:**
- It is not a prompt framework, not a RAG library, not a multi-agent chat system
- It does not replace your LLM or your tools — it orchestrates whatever agent you bring
- It is not production-ready. It is early stage.

**How it differs from existing orchestration tools:**
LangGraph gives you a graph. CrewAI gives you roles. AutoGen gives you message passing. None of them have a structural audit trail tied to the execution model. None of them have HITL as a native state — it is always bolted on. None of them have a mechanism where a human correction in run 1 becomes a rule the agent reads in run 2, without retraining.

The engine itself is ~260 lines. Agents are plain functions that return events. Use cases are self-contained folders. The engine never imports from use cases.

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

```python
# Every agent is a plain function — same contract across all use cases
def run(ctx: AgentContext, **kwargs) -> dict:
    return {"event": "done", "detail": "..."}

# Engine drives the state machine, logs every step, handles HITL pauses
engine.run(ctx, state="received")
```

---

## Use Cases

Use cases are self-contained folders that plug into the engine. Each defines its own states, agent pipeline, configuration, and tools. The engine only sees state transitions and events.

### UC-1: Coding Agent (active, early stage)

An autonomous coding agent for software bug-fixing, evaluated against SWE-bench Verified — the industry-standard benchmark for coding agents. The agent runs a tool loop (`bash`, `str_replace_editor`, `recall_episodes`) against real repositories, produces a git patch, evaluated in Docker via the swebench harness.

Our metric is not pass rate. **Our metric is the reduction in human involvement time** — how much faster a human can review, correct, and ship a fix when the agent has a full audit trail, a correction loop, and accumulated rules vs. starting cold every time. SWE-bench benchmarking is in progress.

**HITL learning loop:**
```
Run  ->  Agent produces patch
     ->  Evaluation (Docker, swebench harness)
     ->  Human reviews, writes correction if needed
     ->  Correction added to RULES.md + episodes.jsonl
     ->  Next run: agent reads updated rules, recalls past corrections
     ->  Human involvement time decreases with each cycle
```

---

## Comparison

🟢 Strong / native &nbsp;&nbsp; 🟡 Partial / workaround &nbsp;&nbsp; 🔴 Not present

| | [LangGraph](https://github.com/langchain-ai/langgraph) | [CrewAI](https://github.com/crewAIInc/crewAI) | [AutoGen](https://github.com/microsoft/autogen) | [OpenHands](https://github.com/All-Hands-AI/OpenHands) | [Devin](https://devin.ai) | **GlassBox** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Orchestration model** | 🟢 Graph | 🟢 Roles | 🟢 Messaging | 🔴 Single agent | 🔴 Proprietary | 🟢 State machine |
| **Structural audit trail** | 🔴 | 🔴 | 🔴 | 🟡 Logs only | 🔴 | 🟢 Every step, always on |
| **HITL as first-class state** | 🟡 Graph node | 🔴 | 🟡 Manual | 🔴 | 🟡 Partial | 🟢 Native pause state |
| **Corrections fed back to agent** | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🟢 RULES.md + episodes |
| **Domain-agnostic use cases** | 🟢 | 🟢 | 🟢 | 🔴 | 🔴 | 🟢 |
| **Open source** | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| **Ecosystem / integrations** | 🟢 Large | 🟢 Large | 🟢 Large | 🟢 Growing | 🔴 | 🔴 Early |
| **Production-ready** | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 Early stage |
| **Lean / auditable core** | 🟡 Complex | 🟡 Complex | 🟡 Complex | 🔴 | 🔴 | 🟢 ~260 lines |

**Where GlassBox is behind:**
- 🔴 **Ecosystem** — LangGraph, CrewAI, AutoGen have large communities, integrations, tooling. We have none of that yet.
- 🔴 **Production-ready** — No production deployments. No hardened APIs. No enterprise support.
- 🔴 **Sandboxing** — Agent runs locally. Evaluation is in Docker. Full inference sandboxing is not built yet.
- 🔴 **SWE-bench score** — Benchmarking in progress. No published score yet.

**Where GlassBox is structurally different:**
- 🟢 **HITL is native, not bolted on** — `awaiting_review` is a state in the machine. The engine was designed around it. In every other framework, HITL is a pattern you implement manually.
- 🟢 **Corrections that compound** — Human feedback in run N becomes a rule the agent reads in run N+1. Version-controlled, readable, editable. No retraining. No fine-tuning.
- 🟢 **Audit trail is not observability** — LangSmith, Arize, and similar tools observe from outside. GlassBox's audit trail is produced by the engine itself, tied to every state transition, inseparable from execution.
- 🟢 **Lean by design** — The engine is ~260 lines. Agents are plain functions. There is no framework magic between your agent and the execution.

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

- [ ] Run SWE-bench evaluation and measure reduction in human involvement time across instances
- [ ] Scale to 50+ SWE-bench instances as the correction loop accumulates
- [ ] Validate that `recall_episodes` measurably reduces human correction effort per instance
- [ ] Full Docker sandboxing for agent inference (not just evaluation)
- [ ] Second use case (domain TBD) to validate platform generality beyond coding

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
