# GlassBox AI 💎

> **Trust is earned, not assumed.**

[![PyPI](https://img.shields.io/pypi/v/glassbox-ai)](https://pypi.org/project/glassbox-ai/)
[![Tests](https://img.shields.io/badge/tests-25%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![Live Tracker](https://img.shields.io/badge/live-performance%20tracker-blueviolet)](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/)

Autonomous coding agent that takes a GitHub issue and ships a tested PR, with full transparency at every step. Powered by trust scores that evolve with every interaction.

**v1.0.0** - TAT (turnaround time) reduced from 60s to 32s (47% faster). See [speed report](docs/speed-optimization-report.md) and [CHANGELOG](CHANGELOG.md).

```
Issue labeled  → 🎯 Manager classifies (gpt-4o-mini, ~2s)
               → 🔧 JuniorDev generates fix (1 line, indent-preserving editor)
               → 🧪 Tester validates (55 tests pass, diff: 1 line)
               → ✅ PR created in ~32s — merged on first attempt
```

---

## 🏗️ Architecture

```
          ┌─────────────────────────────────────────────────────┐
          │          GitHub Issue (labeled glassbox-agent)        │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🎯 Manager                                         │
          │  classifies issue · picks template · generates       │
          │  edge cases (MRU: T1→T4) · sets confidence           │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🔧 JuniorDev                                       │
          │  reads all source + test files · generates fix       │
          │  line-number editing · template-guided               │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🧪 Tester                                          │
          │  syntax check · full test suite · diff size check    │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🛡️ Trust Database (SQLite)                          │
          │  adaptive EMA · floor 0.30 · ceiling 1.00            │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  🧠 Reflexion Memory                                │
          │  verbal failure reflections · full-title retrieval   │
          └──────────────────────┬──────────────────────────────┘
                                 │
          ┌──────────────────────▼──────────────────────────────┐
          │  ✅ Pull Request — with full reasoning chain         │
          └─────────────────────────────────────────────────────┘

          ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
                           PLANNED (future)
          │                                                     │
            🔀 Complexity routing (easy/med/hard pipelines)
          │ 🌐 Cross-repo fixing (fork → fix → PR)             │
            🤝 Bidirectional trust (EigenTrust)
          │ 🔒 Sandboxed execution (Docker runner)              │
            🧬 Multi-model support (Claude, Gemini)
          │                                                     │
          └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

**Solid lines** = built and shipping today. **Dotted lines** = planned.

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

Then ask your AI assistant anything — it will use GlassBox tools automatically.

---

## 🤖 GlassBox Agent v1

Label any issue `glassbox-agent` → the agent ships a tested PR.

### How it works

| Step | Agent | What happens |
|------|-------|--------------|
| 1 | 🎯 **Manager** | Classifies issue, picks template, generates edge cases (MRU: T1→T4) |
| 2 | 🔧 **JuniorDev** | Reads all source + test files, generates minimal fix via line-number editing |
| 3 | 🧪 **Tester** | Syntax check → full test suite → diff size verification |
| 4 | ✅ **PR** | Created with full reasoning chain — every decision visible |

### Features
- **4 templates:** `typo_fix` · `wrong_value` · `wrong_name` · `swapped_args`
- **Line-number editing** — no more "string not found" errors
- **MRU edge cases** — T1 happy path → T2 input variation → T3 error → T4 boundary
- **Reflexion memory** — learns from past failures ([Shinn et al. 2023](https://arxiv.org/abs/2303.11366))
- **Test-grounded fixes** — agent sees test files alongside source code

### Trust System

| Property | Value |
|----------|-------|
| **Persistence** | SQLite — survives across sessions |
| **Initial score** | 0.85 for all agents |
| **Update** | Adaptive EMA: `α = 1/(1+total)` — new agents learn fast, established agents stabilize |
| **Bounds** | Floor 0.30, ceiling 1.00 |

Backed by [EigenTrust (Kamvar et al. 2003)](https://dl.acm.org/doi/10.1145/775152.775242) and Bayesian decay principles.

---

## 📊 Eval Results

**9/11 agent PRs merged · 2 rejected (indentation issues)**

| Run | Type | Result | PRs Merged |
|-----|------|--------|------------|
| Bug eval (7 bugs) | Bug fixes | ✅ 7/7 first-try | #53 #55 #57 #59 #61 #63 #65 |
| Feature eval (5 features) | New features | ✅ 4/5 solved, 2/4 merged | #71 #72 |

👉 [**Live Performance Tracker →**](https://agentic-trust-labs.github.io/glassbox-ai/dashboard/)

---

## 🏆 How GlassBox Compares

| Capability | Devin | SWE-agent | OpenHands | **GlassBox** |
|-----------|-------|-----------|-----------|-------------|
| Issue → PR | ✅ | ✅ | ✅ | ✅ |
| Multi-agent pipeline | ❌ | ❌ | ❌ | ✅ |
| Trust scoring | ❌ | ❌ | ❌ | ✅ |
| Think-before-code | ❌ | ❌ | ❌ | ✅ |
| Reflexion memory | ❌ | ❌ | Partial | ✅ |
| MCP server (any IDE) | ❌ | ❌ | ✅ | ✅ |
| Open source | ❌ | ✅ | ✅ | ✅ |

**What makes GlassBox different:**
1. **Transparency** — every PR shows the full reasoning chain
2. **Multi-agent** — Manager + JuniorDev + Tester, not 1 agent guessing
3. **Trust** — earned through outcomes, not assumed
4. **Learning** — failures become Reflexion memory, not just retries

---

## 🔗 Research

Built on peer-reviewed research across multi-agent debate, trust systems, and AI safety:

- **Multi-Agent Debate** — [Du et al. NeurIPS 2024](https://arxiv.org/abs/2305.14325) · [ChatEval, ICLR 2024](https://arxiv.org/abs/2308.07201)
- **Trust & Reputation** — [EigenTrust, WWW 2003](https://dl.acm.org/doi/10.1145/775152.775242) · [LLM-as-Judge Survey 2024](https://arxiv.org/abs/2411.15594)
- **Self-Correction** — [Reflexion, NeurIPS 2023](https://arxiv.org/abs/2303.11366) · [Self-Refine, NeurIPS 2023](https://arxiv.org/abs/2303.17651)
- **AI Safety** — [AI Safety via Debate, 2018](https://arxiv.org/abs/1805.00899) · [Constitutional AI, 2022](https://arxiv.org/abs/2212.08073) · [Scalable Oversight, NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/899511e37a8e01e1bd6f6f1d377cc250-Paper-Conference.pdf)
- **Grounding** — [FACTS, DeepMind 2024](https://deepmind.google/blog/facts-grounding-a-new-benchmark-for-evaluating-the-factuality-of-large-language-models/) · [MiniCheck, EMNLP 2024](https://arxiv.org/abs/2404.10774)

---

## 📜 License

MIT

---

Built by [Sourabh Gupta](https://github.com/sourabharsh) · [Agentic Trust Labs](https://github.com/agentic-trust-labs)

**💎 Trust is earned, not assumed.**
