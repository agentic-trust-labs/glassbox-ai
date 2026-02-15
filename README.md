# GlassBox AI 💎

> **Trust is earned, not assumed.**

[![PyPI](https://img.shields.io/pypi/v/glassbox-ai)](https://pypi.org/project/glassbox-ai/)
[![Tests](https://img.shields.io/badge/tests-169%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![Live Tracker](https://img.shields.io/badge/live-performance%20tracker-blueviolet)](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/)

We are building trust infrastructure for autonomous AI agents, starting with the coding domain. When AI acts on your behalf - writing code, opening PRs, modifying production systems - you need more than accuracy. You need accountability, transparency, and trust that evolves with every interaction.

GlassBox is an autonomous coding agent that takes a GitHub issue and ships a tested PR. Every decision is visible. Every agent earns its trust score through outcomes, not assumptions. The same principles will extend to every domain where AI acts autonomously.

```
Issue opened   → 🎯 Manager classifies, generates briefing + edge cases
               → 🔧 JuniorDev generates fix (indent-preserving line editor)
               → 🧪 Tester validates (syntax + full test suite)
               → ✅ PR created in ~32s, merged on first attempt
               → 💬 Author can guide via comments (human-in-the-loop)
```

**v1.0** - 54% end-to-end success rate, 32s turnaround. See [performance tracker](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/) and [CHANGELOG](CHANGELOG.md).

---

## 🏗️ Architecture

```
          ┌─────────────────────────────────────────────────────┐
          │          GitHub Issue (labeled glassbox-agent)        │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🎯 Manager (The Strategist)                        │
          │  classifies issue, picks template, generates         │
          │  edge cases (MRU: T1-T4), sets confidence            │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🔧 JuniorDev (The Builder)                         │
          │  reads source + tests, generates fix                 │
          │  line-number editing, template-guided                │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🧪 Tester (The Gatekeeper)                         │
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
          │  ✅ Pull Request with full reasoning chain           │
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

## 🚀 Install

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

| Step | Agent | What happens |
|------|-------|--------------|
| 1 | 🎯 **Manager** | Classifies issue, picks template, generates edge cases (MRU: T1-T4), posts briefing |
| 2 | 🔧 **JuniorDev** | Reads source + tests, generates minimal fix via line-number editing |
| 3 | 🧪 **Tester** | Syntax check, full test suite, diff size verification |
| 4 | ✅ **PR** | Created with reasoning chain - every decision visible |
| 5 | 💬 **HITL** | Author can comment to guide - agent resumes with context |

### Core capabilities

- **4 fix templates** - `typo_fix`, `wrong_value`, `wrong_name`, `swapped_args`
- **Line-number editing** - no more "string not found" errors
- **MRU edge cases** - T1 happy path, T2 input variation, T3 error handling, T4 boundary
- **Reflexion memory** - learns from past failures ([Shinn et al. 2023](https://arxiv.org/abs/2303.11366))
- **Test-grounded fixes** - agent sees test files alongside source code
- **Human-in-the-loop** - author comments parsed as guidance, agent re-enters at the right phase
- **Concurrency control** - one run per issue, in-progress runs cancelled on re-trigger
- **Agent avatars** - each agent has a distinct identity with animal avatars for GitHub readability

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

**54% end-to-end success rate across 61 agent issues. 33 PRs merged.**

| Eval | Type | Result | PRs |
|------|------|--------|-----|
| Bug eval (7 bugs) | Bug fixes | 7/7 first-try | #53 #55 #57 #59 #61 #63 #65 |
| Feature eval (5 features) | New features | 4/5 solved, 2/4 merged | #71 #72 |

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

**💎 Trust is earned, not assumed.**
