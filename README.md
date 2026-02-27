<p align="center">
  <img src="docs/assets/agents/glasswing.svg" width="80" height="80" alt="GlassBox AI">
</p>

# GlassBox AI

> **Trust is earned, not assumed.** 💎

[![PyPI](https://img.shields.io/pypi/v/glassbox-ai)](https://pypi.org/project/glassbox-ai/)
[![Tests](https://img.shields.io/badge/tests-66%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![Live Tracker](https://img.shields.io/badge/live-performance%20tracker-blueviolet)](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/)

We are building trust infrastructure for autonomous AI agents. When AI acts on your behalf - writing code, reviewing pull requests, auditing systems, managing workflows - you need more than accuracy. You need accountability, transparency, and trust that evolves with every interaction.

GlassBox is a **lean orchestration platform** for autonomous agents. At its core is a state machine engine: agents are plain functions, use cases are self-contained folders, and every state transition is logged in an append-only audit trail. You can look inside the box and see exactly what happened, what was decided, and why. Not a black box. A glass box.

```
Any task arrives  →  Engine classifies and routes to the right pipeline
                  →  Agents run as plain functions, return events
                  →  State machine drives transitions, logs every step
                  →  Human checkpoints are first-class states, not afterthoughts
                  →  Full audit trail ships with every result
```

The platform is domain-agnostic. The same engine, the same agent contracts, the same audit model - applied to any problem where an AI needs to act autonomously on your behalf.

---

## 🏗️ How It Works

GlassBox v0.5 is an **OS + Apps** platform. The core engine is completely decoupled from what agents do - it only knows: states exist, transitions connect them, and agents are functions that return events.

```
          ┌─────────────────────────────────────────────────────┐
          │              Task arrives (any domain)               │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  GlassBox Engine (core)                             │
          │  state machine - transitions - audit trail           │
          │  never imports from agents, tools, or use cases      │
          └──────┬───────────────┬───────────────┬──────────────┘
                 │               │               │
         ┌───────▼───────┐ ┌─────▼──────┐ ┌─────▼────────┐
         │  Agents        │ │  Tools     │ │  Use Cases   │
         │  plain funcs   │ │  stateless │ │  self-       │
         │  return events │ │  utilities │ │  contained   │
         └───────┬───────┘ └─────┬──────┘ └─────┬─────────┘
                 └───────────────┴───────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  Audit Trail                                        │
          │  every step: state, event, agent, timestamp, detail  │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  Human-in-the-Loop (first-class checkpoints)        │
          │  pause states in the machine, not bolt-on features   │
          │  engine resumes from the right state with context    │
          └─────────────────────────────────────────────────────┘
```

**The key design principle:** adding a new use case means adding a folder. No core changes. The engine doesn't need to know it exists.

```python
# Every agent is a plain function - same contract across all use cases
def run(ctx: AgentContext, **kwargs) -> dict:
    return {"event": "classified", "detail": "Easy fix, high confidence"}

# Engine drives the state machine
engine.run(ctx, state="received")
# Logs every step automatically - no agent opt-in required
```

**Platform capabilities:**
- **Lean orchestration** - state machine engine with explicit transitions, no magic
- **Full audit trail** - every state, event, agent, and timestamp logged automatically
- **Human checkpoints** - `awaiting_author` is a real pause state, not a workaround
- **Retry with memory** - `_back` routing returns to the exact failed state
- **Author routing** - `_route` lets the author's reply determine the next state
- **Modular use cases** - each use case is a self-contained folder: states, pipeline, settings, templates

---

## 📁 Project Structure

```
glassbox-ai/
├── src/glassbox/                     # Orchestration platform (v0.5)
│   ├── core/
│   │   ├── engine.py                 #   State machine: step(), run(), audit trail
│   │   ├── state.py                  #   BaseState enum + BASE_TRANSITIONS
│   │   └── models.py                 #   AgentContext, AuditEntry, TriageResult
│   │
│   ├── agents/                       # Shared agent pool (one copy, never duplicated)
│   │   ├── classifier.py             #   Routes tasks to easy / medium / hard / skip
│   │   ├── localizer.py              #   Ranks files by relevance
│   │   ├── fix_generator.py          #   Generates line-number edits
│   │   ├── test_validator.py         #   Syntax check + pytest runner
│   │   ├── planner.py                #   Decomposes tasks into ordered steps
│   │   ├── conversationalist.py      #   Parses author intent from comments
│   │   ├── reviewer.py               #   Claude-based review (model diversity)
│   │   └── researcher.py             #   Research report for hard tasks (Phase 4 stub)
│   │
│   ├── tools/                        # Shared tool pool (stateless utilities)
│   │   ├── llm.py                    #   OpenAI client wrapper
│   │   ├── state_store.py            #   Persists state between webhook-resumed runs
│   │   ├── github_client.py          #   gh CLI wrapper: issues, comments, PRs, branches
│   │   ├── code_editor.py            #   Line-number editing engine
│   │   ├── file_reader.py            #   Safe repo file reading
│   │   └── test_runner.py            #   pytest runner with failure parsing
│   │
│   ├── use_cases/                    # Use case apps (self-contained, plug in on top of core)
│   │   └── github_issues/            #   UC-01: Coding Agent (see Use Cases below)
│   │       ├── states.py             #     17 transitions: easy + medium + hard pipelines
│   │       ├── pipeline.py           #     Maps each state to its agent function
│   │       ├── settings.py           #     18 config keys with defaults
│   │       └── templates/            #     4 YAML fix templates
│   │
│   ├── cli.py                        # Entry point: python -m glassbox.cli <issue>
│   └── server.py                     # MCP server stub (Phase 4)
│
├── github-app/app/                   # GitHub App webhook server (deployed on Render)
│   ├── main.py                       #   FastAPI app + health endpoint
│   ├── webhook.py                    #   HMAC signature verification + dispatch
│   ├── handlers.py                   #   Issue / comment event routing
│   ├── runner.py                     #   Clone, install, run agent, cleanup
│   ├── auth.py                       #   JWT-based GitHub App auth
│   ├── github_api.py                 #   Async GitHub API client
│   ├── rate_limiter.py               #   Daily rate limiting with exempt orgs
│   └── config.py                     #   Pydantic settings, fail-fast validation
│
├── tests/
│   ├── unit/
│   │   ├── test_engine.py            #   30+ tests: transitions, retry, routing, audit
│   │   └── test_agents.py            #   11 tests: each agent with mocked LLM
│   └── integration/
│       ├── test_e2e.py               #   8 full pipeline runs (easy, medium, hard)
│       └── test_contracts.py         #   Event contract verification per agent
│
├── docs/
│   ├── index.html                    #   Landing page (GitHub Pages)
│   ├── dashboard/                    #   Live performance tracker
│   └── architecture/                 #   RFCs: adaptive complexity, failure analysis
│
└── pyproject.toml                    # Package config, CLI entry point
```

---

## � Use Cases

Use cases are self-contained folders that plug into the engine. Each one defines its own states, which agents run at which state, and its own config. The core never changes.

---

### UC-01 — Coding Agent (GitHub Issues)

**Status: live.** Label any GitHub issue `glassbox-agent` - the agent classifies it by complexity and routes it through the right pipeline, then ships a tested PR or posts a research report.

```
Issue labeled  → 🔍 Classifier routes to easy / medium / hard
               →   [easy]   Localizer → FixGenerator → TestValidator → PR
               →   [medium] Planner decomposes → step-by-step execution → integrate → PR
               →   [hard]   Researcher posts analysis → Author guides → agent acts
               → 💬 Author can comment at any checkpoint to redirect
               → 🦋 PR ships with full audit trail attached
```

**65 agent issues. 33 PRs merged. 7/7 bug eval first-try. ~32s turnaround.** See [live performance tracker](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/) and [CHANGELOG](CHANGELOG.md).

#### The agents

<p align="center">
  <img src="docs/assets/agents/owl.svg" width="64" height="64" alt="Classifier">&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="docs/assets/agents/beaver.svg" width="64" height="64" alt="FixGenerator">&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="docs/assets/agents/hawk.svg" width="64" height="64" alt="TestValidator">&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="docs/assets/agents/glasswing.svg" width="64" height="64" alt="Pull Request">
</p>

| Agent | Role | Notes |
|-------|------|-------|
| 🔍 **Classifier** | Routes to easy / medium / hard / skip | Core agent - gatekept |
| 📍 **Localizer** | Ranks files by relevance to the issue | LLM-based, returns ranked list |
| 🔧 **FixGenerator** | Generates line-number edits | No string matching - edit by line |
| ✅ **TestValidator** | Syntax check + full pytest run | Returns passed / failed + failure detail |
| 📋 **Planner** | Decomposes medium issues into steps | Escalates to hard if too complex |
| 💬 **Conversationalist** | Parses author intent from comments | Keyword-based, no LLM needed |
| 🔬 **Reviewer** | Code review before PR | Claude-based for model diversity |
| 📊 **Researcher** | Research report for hard issues | Phase 4 - stub in current release |

#### Three pipelines

**Easy** - fully automated, single file, clear scope:
```
received → classifying → easy_localizing → easy_fixing → easy_testing → creating_pr → done
```

**Medium** - multi-step with optional human checkpoints:
```
received → classifying → med_planning → med_step_executing → med_step_testing
                                            ↑ (more steps loop)       ↓ (last step)
                                                               med_integrating → creating_pr → done
```

**Hard** - research first, author-guided execution:
```
received → classifying → hard_researching → hard_report_posted → hard_author_guided
                                                                     ↓ try_fix → med_planning
                                                                     ↓ more_research → hard_researching
                                                                     ↓ manual → done
```

#### Results

| Eval | Scope | Result | PRs |
|------|-------|--------|-----|
| 🔍 Bug eval (7 seeded bugs) | E01-E15 injected via BugFactory | **7/7 first-try, 100%** | [#53](https://github.com/agentic-trust-labs/glassbox-ai/pull/53) [#55](https://github.com/agentic-trust-labs/glassbox-ai/pull/55) [#57](https://github.com/agentic-trust-labs/glassbox-ai/pull/57) [#59](https://github.com/agentic-trust-labs/glassbox-ai/pull/59) [#61](https://github.com/agentic-trust-labs/glassbox-ai/pull/61) [#63](https://github.com/agentic-trust-labs/glassbox-ai/pull/63) [#65](https://github.com/agentic-trust-labs/glassbox-ai/pull/65) |
| 🔧 Feature improvements | Comment UX, dep pinning, workflow fixes | **26 shipped** | [#71](https://github.com/agentic-trust-labs/glassbox-ai/pull/71) [#72](https://github.com/agentic-trust-labs/glassbox-ai/pull/72) [#88](https://github.com/agentic-trust-labs/glassbox-ai/pull/88)-[#125](https://github.com/agentic-trust-labs/glassbox-ai/pull/125) |
| 🦋 End-to-end (all issues) | 65 agent issues across v1 + v2 | **33 merged, 51%** | 33 PRs total |

👉 [**Live Performance Tracker**](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/) - conversion funnel, TAT breakdown, failure diagnostics, all updated in real-time.

---

### UC-02 and beyond

The platform is designed to support any domain where an AI agent needs to act autonomously. Adding a use case means adding a folder under `use_cases/` with its own states, pipeline, and settings. No core changes required.

Future use cases under consideration: PR review pipelines, security audit agents, dependency update automation, cross-repo refactoring.

---

## 🏆 Why GlassBox

| Capability | Devin | SWE-agent | OpenHands | **GlassBox** |
|-----------|-------|-----------|-----------|-------------|
| Autonomous task execution | ✅ | ✅ | ✅ | ✅ |
| Domain-agnostic orchestration | ❌ | ❌ | ❌ | ✅ |
| State machine audit trail | ❌ | ❌ | ❌ | ✅ |
| Human checkpoints (first-class) | Partial | ❌ | ❌ | ✅ |
| Adaptive complexity routing | ❌ | ❌ | ❌ | ✅ |
| Reflexion memory | ❌ | ❌ | Partial | ✅ |
| Pluggable use cases | ❌ | ❌ | ❌ | ✅ |
| Open source | ❌ | ✅ | ✅ | ✅ |

**What makes GlassBox different:**
1. **Transparent** - every state transition logged, every result ships with a full audit trail
2. **Lean** - the core engine is ~260 lines. Agents are plain functions. No framework lock-in.
3. **Human-first** - author checkpoints are first-class pause states in the machine, not afterthoughts
4. **Modular** - adding a use case = adding a folder. The engine never needs to change.
5. **Learning** - failures become Reflexion memory, not just retries

---

## 🔗 Research

Built on peer-reviewed research across multi-agent systems, trust, and AI safety:

- **Multi-Agent Debate** - [Du et al. NeurIPS 2024](https://arxiv.org/abs/2305.14325), [ChatEval, ICLR 2024](https://arxiv.org/abs/2308.07201)
- **Trust and Reputation** - [EigenTrust, WWW 2003](https://dl.acm.org/doi/10.1145/775152.775242), [LLM-as-Judge Survey 2024](https://arxiv.org/abs/2411.15594)
- **Self-Correction** - [Reflexion, NeurIPS 2023](https://arxiv.org/abs/2303.11366), [Self-Refine, NeurIPS 2023](https://arxiv.org/abs/2303.17651)
- **AI Safety** - [AI Safety via Debate, 2018](https://arxiv.org/abs/1805.00899), [Constitutional AI, 2022](https://arxiv.org/abs/2212.08073), [Scalable Oversight, NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/899511e37a8e01e1bd6f6f1d377cc250-Paper-Conference.pdf)
- **Grounding** - [FACTS, DeepMind 2024](https://deepmind.google/blog/facts-grounding-a-new-benchmark-for-evaluating-the-factuality-of-large-language-models/), [MiniCheck, EMNLP 2024](https://arxiv.org/abs/2404.10774)

---

## 📜 License

MIT

---

Built by [Sourabh Gupta](https://www.linkedin.com/in/sourabhgupta16/) at [Agentic Trust Labs](https://github.com/agentic-trust-labs)

**Trust is earned, not assumed. 💎**
