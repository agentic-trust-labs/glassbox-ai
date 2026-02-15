# GlassBox AI 💎

> **Trust is earned, not assumed.** 💎

[![PyPI](https://img.shields.io/pypi/v/glassbox-ai)](https://pypi.org/project/glassbox-ai/)
[![Tests](https://img.shields.io/badge/tests-169%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![Live Tracker](https://img.shields.io/badge/live-performance%20tracker-blueviolet)](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/)

We are building trust infrastructure for autonomous AI agents, starting with the coding domain. When AI acts on your behalf - writing code, opening PRs, modifying production systems - you need more than accuracy. You need accountability, transparency, and trust that evolves with every interaction.

GlassBox is an autonomous coding agent that takes a GitHub issue and ships a tested PR. Every decision is visible. Every agent earns its trust score through outcomes, not assumptions. The same principles will extend to every domain where AI acts autonomously.

```
Issue opened   → 🦉 Manager classifies, generates briefing + edge cases
               → 🦫 JuniorDev generates fix (indent-preserving line editor)
               → � Tester validates (syntax + full test suite)
               → 🦋 PR created in ~32s, merged on first attempt
               → 💬 Author can guide via comments (human-in-the-loop)
```

**65 agent issues. 33 PRs merged. 7/7 bug eval first-try. ~32s turnaround.** See [live performance tracker](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/) and [CHANGELOG](CHANGELOG.md).

---

## 🏗️ Architecture

```
          ┌─────────────────────────────────────────────────────┐
          │          GitHub Issue (labeled glassbox-agent)        │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🦉 Manager (The Strategist)                        │
          │  classifies issue, picks template, generates         │
          │  edge cases (MRU: T1-T4), sets confidence            │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🦫 JuniorDev (The Builder)                         │
          │  reads source + tests, generates fix                 │
          │  line-number editing, template-guided                │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  � Tester (The Skeptic)                             │
          │  syntax check, full test suite, diff size check      │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🛡️ Trust Database (SQLite)                          │
          │  adaptive EMA, floor 0.30, ceiling 1.00              │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🧠 Reflexion Memory                                │
          │  verbal failure reflections, full-title retrieval    │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🦋 Pull Request (The Glasswing)                     │
          │  full reasoning chain, nothing hidden                │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  💬 Human-in-the-Loop (optional)                    │
          │  author comments to guide, agent resumes from        │
          │  the right phase with guidance context               │
          └─────────────────────────────────────────────────────┘

          ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
                           PLANNED (next)
          │                                                     │
            🔀 Adaptive complexity (easy/medium/hard pipelines)
          │ 💬 Conversational loop for hard issues              │
            🤝 Bidirectional trust (EigenTrust)
          │ 🔒 Sandboxed execution (Docker runner)              │
            🧬 Multi-model support (Claude, Gemini)
          │ 🌐 Cross-repo fixing (fork, fix, PR)               │
          └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

**Solid lines** = built and shipping. **Dotted** = planned.

---

## � Project Structure

```
glassbox-ai/
├── src/
│   ├── glassbox/                     # MCP server + core library (pip install glassbox-ai)
│   │   ├── orchestrator.py           #   multi-agent debate engine (3 personas, 2 rounds)
│   │   ├── trust_db.py               #   SQLite trust scores - EMA, floor 0.30, ceiling 1.00
│   │   └── server.py                 #   MCP endpoint - works in any IDE
│   │
│   └── glassbox_agent/               # Autonomous agent pipeline (GitHub Actions)
│       ├── cli.py                    #   entry point: python -m glassbox_agent.cli <issue>
│       ├── agents/
│       │   ├── manager.py            #   🦉 The Strategist - classifies, briefs, approves
│       │   ├── junior_dev.py         #   🦫 The Builder - reads source, generates fix
│       │   └── tester.py             #   🦅 The Skeptic - syntax, tests, diff, edge cases
│       ├── core/
│       │   ├── base_agent.py         #   ABC with animal avatars + GitHub comment headers
│       │   ├── constants.py          #   hard aspects (HA1-5), challenges (HC1-5), patterns (TP1-3)
│       │   ├── conversation.py       #   HITL parsing - phase tags, author guidance, re-entry
│       │   ├── models.py             #   Pydantic: TriageResult, Fix, EdgeCase, TestResult
│       │   ├── settings.py           #   env config - repo, model, temperature
│       │   └── template.py           #   YAML template loader + matching
│       ├── tools/
│       │   ├── github_client.py      #   gh CLI wrapper - issues, comments, PRs, reactions
│       │   ├── code_editor.py        #   line-number editing (no string matching)
│       │   ├── file_reader.py        #   safe file reading with .py filter
│       │   └── test_runner.py        #   pytest runner with failure parsing
│       ├── templates/                #   fix templates: typo_fix, wrong_value, wrong_name, swapped_args
│       └── memory/
│           └── store.py              #   Reflexion memory - verbal failure reflections
│
├── evals/                            # Evaluation framework
│   ├── catalog.py                    #   10 bug specs (E01-E18) with inject/verify
│   ├── bug_factory.py                #   injects bugs into source, verifies fixes
│   └── results.md                    #   7/7 first-try, 100% pass rate
│
├── tests/                            #   169+ tests across 10 files (phases 1-8 + avatars + evals)
│
├── docs/
│   ├── index.html                    #   landing page (GitHub Pages)
│   ├── dashboard/                    #   live performance tracker - funnel, TAT, diagnostics
│   ├── assets/agents/                #   animal SVGs: owl, beaver, hawk, glasswing butterfly
│   ├── architecture/                 #   RFCs: adaptive complexity, HITL, failure analysis
│   └── research/                     #   paper explainer page
│
├── scripts/
│   └── dashboard/                    #   fetches GitHub data, renders HTML dashboard
│
├── .github/workflows/
│   ├── agent-fix.yml                 #   triggers on label/mention, runs full pipeline
│   ├── ci.yml                        #   test suite on push/PR
│   └── dashboard.yml                 #   regenerates live tracker on push
│
└── pyproject.toml                    #   package config, CLI entry point
```

---

## �🚀 Install

```bash
pip install glassbox-ai
```

Add to your MCP config:
```json
{
  "mcpServers": {
    "glassbox-ai": {
      "command": "glassbox-ai",
      "args": [],
      "env": { "OPENAI_API_KEY": "sk-..." }
    }
  }
}
```

Then ask your AI assistant anything - it will use GlassBox tools automatically.

---

## 🤖 Agent Pipeline

Label any issue `glassbox-agent` or mention `@glassbox-agent` - the agent ships a tested PR.

### Pipeline steps

| Step | Agent | Identity | What happens |
|------|-------|----------|--------------| 
| 1 | 🦉 **Manager** | *The Strategist* | Classifies issue, picks template, generates edge cases (MRU: T1-T4), posts briefing |
| 2 | 🦫 **JuniorDev** | *The Builder* | Reads source + tests, generates minimal fix via line-number editing |
| 3 | � **Tester** | *The Skeptic* | Syntax check, full test suite, diff size verification |
| 4 | 🦋 **Pull Request** | *The Glasswing* | Full reasoning chain, nothing hidden, transparent and ready to fly |
| 5 | 💬 **HITL** | *Author* | Comment to guide, agent resumes from the right phase with context |

### Core capabilities

- **4 fix templates** - `typo_fix`, `wrong_value`, `wrong_name`, `swapped_args`
- **Line-number editing** - no more "string not found" errors
- **MRU edge cases** - T1 happy path, T2 input variation, T3 error handling, T4 boundary
- **Reflexion memory** - learns from past failures ([Shinn et al. 2023](https://arxiv.org/abs/2303.11366))
- **Test-grounded fixes** - agent sees test files alongside source code
- **Human-in-the-loop** - author comments parsed as guidance, agent re-enters at the right phase
- **Concurrency control** - one run per issue, in-progress runs cancelled on re-trigger
- **Agent avatars** - each agent has a distinct animal kingdom identity (🦉 owl, 🦫 beaver, 🦅 hawk, 🦋 glasswing butterfly) rendered as custom SVGs in GitHub comments

### Trust system

| Property | Value |
|----------|-------|
| **Persistence** | SQLite - survives across sessions |
| **Initial score** | 0.85 for all agents |
| **Update** | Adaptive EMA: `a = 1/(1+total)` - new agents learn fast, established agents stabilize |
| **Bounds** | Floor 0.30, ceiling 1.00 |

Backed by [EigenTrust (Kamvar et al. 2003)](https://dl.acm.org/doi/10.1145/775152.775242) and Bayesian decay principles. Trust starts high and adjusts based on real outcomes - the same way you would trust a new team member who shows competence.

---

## 📊 Results

**65 agent issues. 33 PRs merged. 7/7 bug eval first-try. ~32s turnaround.**

| Eval | Scope | Result | PRs |
|------|-------|--------|-----|
| 🦉 Bug eval (7 seeded bugs) | E01-E15 injected via BugFactory | **7/7 first-try, 100%** | [#53](https://github.com/agentic-trust-labs/glassbox-ai/pull/53) [#55](https://github.com/agentic-trust-labs/glassbox-ai/pull/55) [#57](https://github.com/agentic-trust-labs/glassbox-ai/pull/57) [#59](https://github.com/agentic-trust-labs/glassbox-ai/pull/59) [#61](https://github.com/agentic-trust-labs/glassbox-ai/pull/61) [#63](https://github.com/agentic-trust-labs/glassbox-ai/pull/63) [#65](https://github.com/agentic-trust-labs/glassbox-ai/pull/65) |
| 🦫 Feature improvements | Comment UX, dep pinning, workflow fixes | **26 shipped** | [#71](https://github.com/agentic-trust-labs/glassbox-ai/pull/71) [#72](https://github.com/agentic-trust-labs/glassbox-ai/pull/72) [#88](https://github.com/agentic-trust-labs/glassbox-ai/pull/88)-[#125](https://github.com/agentic-trust-labs/glassbox-ai/pull/125) |
| 🦅 End-to-end (all issues) | 65 agent issues across v1 + v2 | **33 merged, 51%** | 33 PRs total |

👉 [**Live Performance Tracker**](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/) - conversion funnel, TAT breakdown, failure diagnostics, all updated in real-time.

---

## 🏆 How GlassBox Compares

| Capability | Devin | SWE-agent | OpenHands | **GlassBox** |
|-----------|-------|-----------|-----------|-------------|
| Issue to PR | ✅ | ✅ | ✅ | ✅ |
| Multi-agent pipeline | ❌ | ❌ | ❌ | ✅ |
| Trust scoring | ❌ | ❌ | ❌ | ✅ |
| Think-before-code | ❌ | ❌ | ❌ | ✅ |
| Human-in-the-loop | Partial | ❌ | ❌ | ✅ |
| Reflexion memory | ❌ | ❌ | Partial | ✅ |
| MCP server (any IDE) | ❌ | ❌ | ✅ | ✅ |
| Open source | ❌ | ✅ | ✅ | ✅ |

**What makes GlassBox different:**
1. **Trust-first** - every agent earns trust through outcomes, not configuration
2. **Transparent** - every PR shows the full reasoning chain, every decision visible
3. **Multi-agent** - Manager + JuniorDev + Tester, not one agent guessing
4. **Human-guided** - author can intervene at any point, agent resumes with context
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

**💎 Trust is earned, not assumed. 💎**
