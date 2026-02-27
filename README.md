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

We are building trust infrastructure for autonomous AI agents, starting with the coding domain. When AI acts on your behalf - writing code, opening PRs, modifying production systems - you need more than accuracy. You need accountability, transparency, and trust that evolves with every interaction.

GlassBox is an autonomous coding agent platform. Label a GitHub issue and the agent classifies it, routes it through the right pipeline (easy, medium, or hard), and ships a tested PR - or posts a research report for issues that are too complex to fix automatically. Every state transition is logged. Every decision is auditable.

```
Issue labeled  → 🔍 Classifier routes to easy / medium / hard pipeline
               →   [easy]   Localizer finds file → FixGenerator patches → TestValidator confirms → PR
               →   [medium] Planner decomposes → step-by-step execution → integration test → PR
               →   [hard]   Researcher posts analysis → Author guides → agent acts on direction
               → 💬 Author can guide at any checkpoint (human-in-the-loop)
               → 🦋 PR created with full audit trail, nothing hidden
```

**65 agent issues. 33 PRs merged. 7/7 bug eval first-try. ~32s turnaround.** See [live performance tracker](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/) and [CHANGELOG](CHANGELOG.md).

---

## 🏗️ Architecture

GlassBox v0.5 is built as an **OS + Apps** platform. The core is a state machine engine that never knows what the agent is doing - it only knows states, transitions, and agents as functions. Use cases (like GitHub Issues) plug in on top without touching the core.

```
          ┌─────────────────────────────────────────────────────┐
          │         GitHub Issue (labeled glassbox-agent)         │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🔍 Classifier                                       │
          │  reads title + body, routes to easy / medium / hard  │
          │  safe fallback: malformed LLM output → hard          │
          └──────┬───────────────┬───────────────┬──────────────┘
                 │               │               │
         ┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼────────┐
         │  EASY         │ │  MEDIUM      │ │  HARD         │
         │  single file  │ │  multi-step  │ │  research     │
         │  clear scope  │ │  decomposed  │ │  + convo loop │
         └───────┬───────┘ └──────┬───────┘ └─────┬─────────┘
                 │               │               │
         ┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼────────┐
         │  Localizer   │ │  Planner    │ │  Researcher   │
         │  FixGen      │ │  StepExec   │ │  (report)     │
         │  TestValid   │ │  StepTest   │ │               │
         └───────┬───────┘ │  Integrate  │ └─────┬─────────┘
                 │         └──────┬───────┘       │
                 └────────────────┴───────────────┘
                                  │
          ┌──────────────────────▼──────────────────────────────┐
          │  🧠 Reflexion Memory                                │
          │  verbal failure reflections stored per-repo         │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🦋 Pull Request                                     │
          │  full audit trail: every state, event, agent logged  │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  💬 Human-in-the-Loop (checkpoints)                 │
          │  author comments parsed by Conversationalist agent   │
          │  engine resumes from the right state with context    │
          └─────────────────────────────────────────────────────┘

          ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
                           PLANNED (next)
          │                                                     │
            � Researcher: real codebase analysis (Phase 4)
          │ 🔒 Sandboxed test execution (Docker runner)        │
            🧬 Multi-model support (Claude, Gemini)
          │ 📦 MCP server (glassbox-ai as IDE tool)            │
            🌐 Cross-repo fixing (fork, fix, PR)
          └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

**Solid lines** = built and shipping. **Dotted** = planned.

---

## 📁 Project Structure

```
glassbox-ai/
├── src/glassbox/                     # Agent platform (v0.5, OS + Apps architecture)
│   ├── core/
│   │   ├── engine.py                 #   State machine: step(), run(), audit trail
│   │   ├── state.py                  #   BaseState enum + BASE_TRANSITIONS
│   │   └── models.py                 #   AgentContext, AuditEntry, TriageResult
│   │
│   ├── agents/                       # Shared agent pool (one copy, never duplicated)
│   │   ├── classifier.py             #   Routes issues to easy / medium / hard / skip
│   │   ├── localizer.py              #   Ranks files by relevance to the issue
│   │   ├── fix_generator.py          #   Generates line-number edits (no string matching)
│   │   ├── test_validator.py         #   Syntax check + pytest runner
│   │   ├── planner.py                #   Decomposes medium issues into ordered steps
│   │   ├── conversationalist.py      #   Parses author intent from GitHub comments
│   │   ├── reviewer.py               #   Claude-based code review
│   │   └── researcher.py             #   Research report for hard issues (Phase 4 stub)
│   │
│   ├── tools/                        # Shared tool pool (stateless utilities)
│   │   ├── llm.py                    #   OpenAI client wrapper
│   │   ├── state_store.py            #   Persists state between webhook-resumed runs
│   │   ├── github_client.py          #   gh CLI wrapper: issues, comments, PRs, branches
│   │   ├── code_editor.py            #   Line-number editing engine
│   │   ├── file_reader.py            #   Safe repo file reading
│   │   └── test_runner.py            #   pytest runner with failure parsing
│   │
│   ├── use_cases/github_issues/      # GitHub Issues use case (self-contained)
│   │   ├── states.py                 #   17 transitions: easy + medium + hard pipelines
│   │   ├── pipeline.py               #   Maps each state to its agent function
│   │   ├── settings.py               #   18 config keys with defaults
│   │   └── templates/                #   4 YAML fix templates
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
├── evals/                            # Evaluation framework
│   ├── catalog.py                    #   Bug specs (E01-E18) with inject/verify
│   └── bug_factory.py                #   Injects bugs into source, verifies fixes
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

## 🤖 Agent Pipeline

Label any issue `glassbox-agent` - the agent classifies it and routes it to the right pipeline.

### The agents

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

### Three pipelines

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

### State machine core

Every step is logged automatically. You can see the full audit trail in the PR description:

```python
# Every agent is a plain function
def run(ctx: AgentContext, **kwargs) -> dict:
    return {"event": "easy", "detail": "Single-file typo, confidence 0.95"}

# Engine drives transitions
engine.run(ctx, state="received")
# → received → classifying → easy_localizing → easy_fixing → easy_testing → creating_pr → done
```

### Core capabilities

- **Adaptive routing** - classifier sends issues to the right pipeline based on complexity
- **Line-number editing** - no more "string not found" errors from patch tools
- **Reflexion memory** - learns from past failures ([Shinn et al. 2023](https://arxiv.org/abs/2303.11366))
- **Human-in-the-loop** - author comments parsed as guidance, engine resumes at the right state
- **Full audit trail** - every state transition logged with timestamp, agent, event, detail
- **Concurrency control** - one run per issue, deduplication at the runner level
- **Rate limiting** - configurable daily limit with exempt orgs (agentic-trust-labs exempt by default)

---

## 📊 Results

**65 agent issues. 33 PRs merged. 7/7 bug eval first-try. ~32s turnaround.**

| Eval | Scope | Result | PRs |
|------|-------|--------|-----|
| 🔍 Bug eval (7 seeded bugs) | E01-E15 injected via BugFactory | **7/7 first-try, 100%** | [#53](https://github.com/agentic-trust-labs/glassbox-ai/pull/53) [#55](https://github.com/agentic-trust-labs/glassbox-ai/pull/55) [#57](https://github.com/agentic-trust-labs/glassbox-ai/pull/57) [#59](https://github.com/agentic-trust-labs/glassbox-ai/pull/59) [#61](https://github.com/agentic-trust-labs/glassbox-ai/pull/61) [#63](https://github.com/agentic-trust-labs/glassbox-ai/pull/63) [#65](https://github.com/agentic-trust-labs/glassbox-ai/pull/65) |
| 🔧 Feature improvements | Comment UX, dep pinning, workflow fixes | **26 shipped** | [#71](https://github.com/agentic-trust-labs/glassbox-ai/pull/71) [#72](https://github.com/agentic-trust-labs/glassbox-ai/pull/72) [#88](https://github.com/agentic-trust-labs/glassbox-ai/pull/88)-[#125](https://github.com/agentic-trust-labs/glassbox-ai/pull/125) |
| � End-to-end (all issues) | 65 agent issues across v1 + v2 | **33 merged, 51%** | 33 PRs total |

👉 [**Live Performance Tracker**](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/) - conversion funnel, TAT breakdown, failure diagnostics, all updated in real-time.

---

## 🏆 How GlassBox Compares

| Capability | Devin | SWE-agent | OpenHands | **GlassBox** |
|-----------|-------|-----------|-----------|-------------|
| Issue to PR | ✅ | ✅ | ✅ | ✅ |
| Adaptive complexity routing | ❌ | ❌ | ❌ | ✅ |
| State machine audit trail | ❌ | ❌ | ❌ | ✅ |
| Human checkpoints (first-class) | Partial | ❌ | ❌ | ✅ |
| Reflexion memory | ❌ | ❌ | Partial | ✅ |
| Multi-pipeline (easy/med/hard) | ❌ | ❌ | ❌ | ✅ |
| MCP server (any IDE) | ❌ | ❌ | ✅ | ✅ (planned) |
| Open source | ❌ | ✅ | ✅ | ✅ |

**What makes GlassBox different:**
1. **Transparent** - every state transition logged, every PR shows the full audit trail
2. **Adaptive** - easy issues are fully automated, hard issues get a research report + conversation
3. **Human-first** - author checkpoints are first-class states in the machine, not afterthoughts
4. **Modular** - agents are plain functions, use cases are folders, adding a pipeline needs no core changes
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
