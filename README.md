<p align="center">
  <img src="docs/assets/agents/glasswing.svg" width="80" height="80" alt="GlassBox AI">
</p>

# GlassBox AI

> **Trust is earned, not assumed.** 💎

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()

An orchestration platform for autonomous coding agents - built for enterprise problems where every ticket is worth hundreds of dollars in engineer time. GlassBox makes **auditability**, **human oversight**, and **continuous improvement** first-class concerns, not afterthoughts.

Most agent frameworks optimize for autonomy. We optimize for **trust**.

---

## The Problem

Enterprise engineering teams face a growing paradox: AI coding agents are powerful enough to ship real fixes, but too unreliable to trust without oversight. A single bad merge can cost hours of debugging. A hallucinated API call can break production.

Current tools treat human oversight as a speed bump. GlassBox treats it as the engine.

---

## How GlassBox Works

GlassBox is a state machine that orchestrates autonomous agents with five first-class guarantees:

### 1. Full Auditability
Every state transition, every tool call, every LLM response - logged in an append-only audit trail. When a patch ships, you can trace exactly what happened, what was decided, and why. No black boxes.

### 2. Human-in-the-Loop (HITL)
Human checkpoints are real pause states in the machine, not bolt-on features. The engine pauses, waits for human input, and resumes from the exact right state with full context. Reviewers see the agent's reasoning, not just its output.

### 3. Continuous Improvement
Every human correction is captured as a structured episode. Rules evolve over time. The agent gets better with every interaction - not through fine-tuning, but through accumulated experience:

- **RULES.md** - 27 rules bootstrapped from top SWE-bench agents (Codex CLI, OpenHands, Augment Code), injected into every prompt
- **episodes.jsonl** - Append-only store of human corrections, searchable by the agent via a recall tool
- **Reflection loop** - Failed patches become learning signals, not just retries

### 4. Transparency
The agent's system prompt, rules, episodes, and decision log are all readable files in the repo. No hidden weights, no opaque embeddings. You can read every rule the agent follows, edit them, and version-control them alongside your code.

### 5. Reliability
Deterministic state machine with explicit transitions. No probabilistic routing, no hidden fallbacks. If the agent gets stuck, it escalates - it doesn't silently guess. Patches are stripped of artifacts, validated against test suites in Docker, and only shipped after human review.

```
Task arrives  ->  Engine classifies and routes
              ->  Agent loop: bash + str_replace_editor + LLM reasoning
              ->  Patch produced, new files stripped automatically
              ->  Docker evaluation (swebench harness)
              ->  Human review checkpoint
              ->  If rejected: correction captured as episode, agent re-runs with guidance
              ->  Rules evolve, next run is smarter
```

---

## Architecture

```
        +---------------------------------------------------+
        |              GlassBox Engine (core)                |
        |  state machine - transitions - audit trail         |
        |  ~260 lines. never imports from use cases.         |
        +--------+------------------+-----------------------+
                 |                  |
        +--------v--------+  +-----v---------+
        |   Agent Loop     |  |   HITL Memory  |
        |  bash, editor,   |  |  RULES.md      |
        |  LLM (litellm)   |  |  episodes.jsonl |
        |  recall_episodes  |  |  recall tool    |
        +--------+--------+  +-----+---------+
                 |                  |
        +--------v------------------v-----------+
        |          Use Case: Coder               |
        |  pipeline.py  - agent loop + tools     |
        |  settings.py  - model, limits, config  |
        |  states.py    - transitions            |
        |  RULES.md     - 27 learned rules       |
        |  memory/      - episode store           |
        +--------+------------------------------+
                 |
        +--------v------------------------------+
        |  SWE-bench Evaluation (Docker)         |
        |  swebench harness, per-instance        |
        |  containers, test-verified results     |
        +---------------------------------------+
```

**Adding a use case = adding a folder.** The engine never changes.

---

## The Coder Agent

An autonomous coding agent that fixes bugs from real-world open-source repositories. Evaluated on SWE-bench Verified - the industry standard benchmark.

**Tools:** bash, str_replace_editor, complete, recall_episodes
**Prompt:** Borrowed from OpenAI's GPT-4.1 guide (persistence + tool-calling + planning = +20% on SWE-bench)
**Rules:** 27 rules from 7 top SWE-bench agents (Codex CLI, OpenHands, Augment Code, Cursor, Aider, Claude Code, mini-swe-agent)
**Evaluation:** Docker containers via swebench harness - same setup used by every leaderboard submission

### HITL Learning in Action

```
Run 1:  Agent produces patch for astropy-14508
        -> Docker eval: target test passes, but test_invalid_float_cards2 regresses
        -> HITL diagnosis: str() shortcut produces lowercase 'e', FITS requires uppercase 'E'
        -> Episode captured in episodes.jsonl

Run 2:  Agent sees the correction in its prompt
        -> Produces improved patch with proper guard
        -> Episode library grows, future similar bugs benefit
```

**First end-to-end HITL run (3 instances):**

| Instance | Patch | Steps | Cost | Eval Result | HITL Correction |
|----------|-------|-------|------|-------------|-----------------|
| astropy-14365 | 619 chars | 10 | $0.13 | Tests failed (incomplete fix) | "re.IGNORECASE alone insufficient - write path needs uppercase too" |
| astropy-14539 | 1251 chars | 29 | $0.66 | Tests failed (wrong approach) | "VLA padding wrong - use element-wise comparison for object-dtype" |
| astropy-14508 | 514 chars | 9 | $0.09 | Target test passed, regression | "str() gives lowercase e, FITS needs uppercase E - use .16G format" |

**Total cost: $0.88 for 3 instances.** Every failure becomes a learning signal.

---

## Honest Comparison

We believe in transparency - including about where we fall short.

| Capability | Devin | OpenHands | Augment Code | Codex CLI | **GlassBox** |
|---|:---:|:---:|:---:|:---:|:---:|
| **Autonomous bug fixing** | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| **SWE-bench score** | 🟢 undisclosed | 🟢 37% | 🟢 65% | 🟢 ~70% | 🔴 **0% (3 instances, WIP)** |
| **Sandboxed execution** | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 **Local + Docker eval** |
| **Multi-language support** | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 **Python only (for now)** |
| **State machine audit trail** | 🔴 | 🔴 | 🔴 | 🔴 | 🟢 |
| **Human checkpoints (first-class)** | 🟡 Partial | 🔴 | 🔴 | 🔴 | 🟢 |
| **HITL learning (corrections become rules)** | 🔴 | 🔴 | 🔴 | 🔴 | 🟢 |
| **Transparent rules (readable, editable, versioned)** | 🔴 | 🔴 | 🟡 | 🟡 AGENTS.md | 🟢 |
| **Episode memory (past corrections searchable)** | 🔴 | 🔴 | 🔴 | 🔴 | 🟢 |
| **Enterprise audit compliance** | 🟡 | 🔴 | 🔴 | 🔴 | 🟢 |
| **Open source** | 🔴 | 🟢 | 🟡 Partial | 🟢 | 🟢 |

**Where we're behind** (and working on it):
- 🔴 **SWE-bench score:** 0% on 3 instances vs 65%+ for leaders. We're early. The infrastructure is built, the scores will follow as we iterate with HITL corrections and stronger models.
- 🟡 **Sandboxing:** Agent runs locally, evaluation in Docker. Full Docker sandboxing for inference is planned.
- 🟡 **Language coverage:** Python-only today. The architecture is language-agnostic but tooling isn't.

**Where we lead:**
- No other open-source agent has first-class HITL learning where human corrections become persistent rules
- No other agent ships a readable, version-controlled rule file that evolves with every interaction
- No other agent has an append-only episode store that the agent can search during problem-solving

---

## Quick Start

```bash
# Clone and set up
git clone https://github.com/agentic-trust-labs/glassbox-ai.git
cd glassbox-ai
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env: OPENAI_API_KEY=sk-... and GLASSBOX_MODEL=gpt-4o

# Run on a SWE-bench instance
.venv/bin/python src/glassbox/use_cases/coder/run_swebench.py \
    --dataset SWE-bench/SWE-bench_Verified \
    --split test \
    --instance_ids astropy__astropy-14365 \
    --output predictions.json

# Evaluate with Docker
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock \
.venv/bin/python -m swebench.harness.run_evaluation \
    --dataset_name SWE-bench/SWE-bench_Verified \
    --predictions_path predictions.json \
    --max_workers 1 \
    --run_id my_eval
```

---

## Research

Built on peer-reviewed research:

- **HITL for Agents** - [HULA, ICSE 2025](https://arxiv.org) - 54% said code had defects without human oversight
- **Self-Correction** - [Reflexion, NeurIPS 2023](https://arxiv.org/abs/2303.11366), [Self-Refine, NeurIPS 2023](https://arxiv.org/abs/2303.17651)
- **Agent Prompting** - [OpenAI GPT-4.1 Guide](https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide/) - persistence + tool-calling + planning
- **Trust** - [EigenTrust, WWW 2003](https://dl.acm.org/doi/10.1145/775152.775242), [AI Safety via Debate, 2018](https://arxiv.org/abs/1805.00899)

---

## License

MIT

---

Built by [Sourabh Gupta](https://www.linkedin.com/in/sourabhgupta16/) at [Agentic Trust Labs](https://github.com/agentic-trust-labs)

**Trust is earned, not assumed. 💎**
