# GlassBox Trust & Evaluation Programme

**Last updated:** February 2026 · **Owner:** @agentic-trust-labs

> Testing is not quality assurance — it is the mechanism that delivers on the GlassBox promise:
> you can see inside.

## Executive Summary

This programme establishes testing and evaluation as a first-class feature of the GlassBox platform. Over 5 phases, we build from CI foundations through real-time tracing, LLM-based evaluation, public trust dashboards, and community benchmarks. Each phase produces independently valuable deliverables while building the foundation for trust at scale.

---

## Architecture Approach

**Core design:** Trust Kernel + ASL Levels (Agent Safety Levels), balanced for sustainability.

The tracer lives in `src/glassbox/tracing/`, not inside `core/`. The engine calls the
tracer via a hook — if tracing is disabled, the engine doesn't know or care. This keeps
the kernel small and the tracing subsystem independently evolvable.

**Event-driven architecture:** GlassBox operates on events (classified, fixed, failed, etc.).
This programme evaluates event correctness, event quality, and computes trust scores for
event sequences. Tests verify agents return valid events; scorers measure the quality of
artifacts attached to those events.

**Research basis:**
- Anthropic — Bloom framework, ASL graduated safety levels, judge calibration [1]
- OpenAI — Eval-driven development, Agents SDK tracing, LLM-as-judge guidance [2]
- Google — SMURF (Speed, Maintainability, Utilization, Reliability, Fidelity) [3]
- Linux Kernel — KUnit (white-box) + kselftest (black-box) dual-layer testing [4]
- UK AISI — Inspect framework (composable Tasks = Datasets + Solvers + Scorers) [5]
- Cleanlab — Real-time trust scoring across agent architectures [6]

---

## The Audience Ladder

Each phase targets a progressively wider audience, building credibility from the inside out. Every phase requires the deliverables from prior phases — trust compounds.

| Phase | Trust Level | Value Proposition |
|-------|-------------|-------------------|
| 1 | Developer trust | "Your commits are safe." |
| 2 | Technical trust | "Every run is traced and scored." |
| 3 | Organizational trust | "We publish our quality weekly, in the open." |
| 4 | Public trust | "Visit our trust dashboard." |
| 5 | Industry trust | "We are building the standard for agent trust." |

---

## Phase 1 · Foundation

**Timeline:** 2 weeks from programme start · **Audience:** Developers

| | Detail |
|---|---|
| **Input** | 66 tests (0.07s), no CI gate, legacy files, no event contract validation |
| **Output** | ~80 tests in `tests/unit/` + `tests/integration/`, CI workflow, legacy files removed |
| **Delivery** | CI gate blocks merge on failure. README badge: `CI: Passing` |
| **How tested** | The CI workflow itself is the test — if it runs, Phase 1 works |
| **Product feature** | Every contributor knows their code won't break event contracts |

**Schema — test directory:**
```
tests/
├── unit/
│   ├── test_engine.py          42 tests — state transitions, _back, _route, audit
│   ├── test_agents.py          15 tests — each agent with mocked LLM
│   └── test_tools.py           ~15 tests — tool unit tests (new)
├── integration/
│   ├── test_e2e.py              9 tests — full pipeline with mock agents
│   └── test_contracts.py       ~10 tests — agent return schema validation (new)
├── fixtures/
│   └── mock_responses.yaml      Mocked LLM responses for deterministic tests
└── conftest.py                  Shared fixtures, pytest markers
```

**Event contract specification:**

| Agent | Required keys | Valid events |
|-------|---------------|-------------|
| classifier | event, triage_result | easy, medium, hard, skip |
| fix_generator | event, fix | fixed, failed |
| planner | event, steps | planned, too_hard |
| localizer | event, files | found, not_found |
| test_validator | event, results | passed, failed |
| reviewer | event, review | approved, rejected |
| conversationalist | event, route_to | (any valid state) |
| researcher | event, report | researched, failed |

### How It Works — Example Run

**Scenario:** A contributor modifies `classifier.py` and pushes to GitHub.

**What happens:**
1. GitHub Actions triggers on push
2. CI runs: `pytest tests/unit/ tests/integration/`
3. Contract test verifies: `assert result["event"] in ["easy", "medium", "hard", "skip"]`
4. If any test fails → merge is blocked
5. If all tests pass → merge is allowed

**What you see:**
```
tests/unit/test_engine.py ✓ 42 passed
tests/unit/test_agents.py ✓ 15 passed  
tests/integration/test_contracts.py ✓ 10 passed
CI: Passing
```

**Value:** Every contributor knows their code won't break event contracts.

---

## Phase 2 · Tracer + Trust Scores

**Timeline:** 1 month from programme start · **Audience:** Developers + technical users

| | Detail |
|---|---|
| **Input** | Phase 1 complete, no tracing, no golden dataset, no scoring |
| **Output** | Tracer module, golden dataset (20 issues), trust score computation, ASL-1/2 defined |
| **Delivery** | `python -m evals.runner --suite regression` produces a score |
| **How tested** | Tracer tested with mock pipelines; scorer tested with synthetic traces |
| **Product feature** | "Every agent run is traced and scored" — the first GlassBox differentiator |

**Schema — tracer (outside core, hook-based):**
```
src/glassbox/tracing/
├── __init__.py
├── tracer.py          Tracer class — records TraceEvents, produces TraceReport
└── models.py          TraceEvent, TrustScore, TraceReport dataclasses
```

**Schema — TraceEvent:**
```python
@dataclass
class TraceEvent:
    kind: str          # "trace_started" | "agent_called" | "tool_called"
                       # "transition_fired" | "trace_ended"
    timestamp: float
    data: dict         # kind-specific payload
```

**Schema — TrustScore (4 dimensions):**

| Dimension | Measure | Weight |
|-----------|---------|--------|
| Decision Quality | Classification accuracy | 0.30 |
| Fix Quality | Fix applied + tests pass | 0.35 |
| Efficiency | Retries / total steps | 0.15 |
| Transparency | % of steps with complete traces | 0.20 |

**Schema — eval primitives (Inspect-inspired [5]):**
```
evals/
├── core/
│   ├── dataset.py       Load samples from YAML
│   ├── scorer.py        Base scorer interface: score(input, output, expected) → Score
│   ├── suite.py         Bind dataset + scorer → runnable eval
│   └── runner.py        Run suites, collect results, produce report
├── datasets/
│   ├── golden_easy.yaml        10 issues with expected classification + fix
│   ├── golden_medium.yaml       5 issues with expected plan + affected files
│   └── golden_hard.yaml         5 issues with expected research direction
└── scorers/
    ├── exact_event.py    Did the agent return the correct event?
    ├── diff_size.py      Is the fix minimal?
    └── trust_score.py    Composite trust metric from trace
```

**ASL levels defined:**

| Level | Requirements | Deployment |
|-------|--------------|------------|
| ASL-1 (Development) | All unit + contract tests pass | Local dev |
| ASL-2 (Staging) | Golden dataset score > 0.7, trust > 0.5 | Test repo |

### How It Works — Example Run

**Scenario:** Issue #42 says "The config key for critic is misspelled as 'critc'"

**What you run:**
```bash
python -m glassbox.cli fix-issue --repo myorg/myrepo --issue 42
```

**What happens internally:**
1. Engine starts → tracer records `trace_started` event
2. Classifier runs → tracer records `agent_called` with event="easy", duration=1200ms
3. Trust scorer computes decision quality from trace → 0.92
4. Fix generator runs → tracer records fix event
5. Each step appends to trace, trust recomputed after each event
6. Final trace saved to `.glassbox/traces/issue-42-trace.json`

**What you see on screen:**
```
🔍 Classifying issue #42... → easy (trust: 0.92)
📍 Localizing files... → src/glassbox/orchestrator.py (trust: 0.88)
🔧 Generating fix... → Fixed 'critc' → 'critic' line 47 (trust: 0.85)
✓ Tests passed (trust: 0.91)
📊 Final trust score: 0.87
```

**What's in the trace file:**
```json
{
  "trace_id": "issue-42-20260223-203045",
  "events": [
    {"kind": "agent_called", "agent": "classifier", 
     "data": {"event": "easy", "confidence": 0.92}},
    {"kind": "agent_called", "agent": "localizer", 
     "data": {"event": "found", "files": ["src/glassbox/orchestrator.py"]}},
    ...
  ],
  "trust_score": {"overall": 0.87, "decision_quality": 0.92, "fix_quality": 0.85}
}
```

**Run eval against golden dataset:**
```bash
python -m evals.runner --suite regression
```

**What you see:**
```
Golden Dataset Regression Suite
================================
Issue #101 (easy): ✓ expected 'easy', got 'easy' (trust: 0.94)
Issue #102 (medium): ✓ expected 'planned', got 'planned' (trust: 0.81)
Issue #103 (hard): ✗ expected 'researched', got 'too_hard' (trust: 0.62)

Score: 18/20 (90%) — Avg trust: 0.84
```

**Value:** Real-time visibility into agent behavior. Every run is auditable. Quality is quantified.

---

## Phase 3 · The Judge + ASL-3

**Timeline:** 3 months from programme start · **Audience:** Organizations + potential users

| | Detail |
|---|---|
| **Input** | Phase 2 complete, no subjective quality eval, no behavioural testing |
| **Output** | LLM-judge scorer, behavioural checks, weekly eval reports, ASL-3 defined |
| **Delivery** | Weekly quality report committed to `docs/eval-reports/YYYY-WW.md` |
| **How tested** | Judge calibrated against 20 human-scored traces (target: Spearman correlation > 0.8) [1] |
| **Product feature** | "We publish our eval results. Every week. In the repo." |

**Schema — new scorers:**
```
evals/scorers/
├── llm_judge.py         Strong model scores fix quality 1–10, with CoT reasoning [2]
└── behavioural.py       Deterministic checks first, LLM-judge only for subjective
```

**Behavioral checks (deterministic):**

| Check | Method | Severity |
|-------|--------|----------|
| Hallucinated file path | regex + os.path | Critical |
| Unnecessary code changes | diff line count | Warning |
| Claimed false confidence | keyword match | Warning |
| Modified unrelated files | diff file list | Critical |

**Budget:** ~20 LLM judge calls/week ≈ $2–10/week.

**ASL-3 defined:**

| Level | Requirements | Deployment |
|-------|--------------|------------|
| ASL-3 (Production) | LLM-judge avg > 8.0/10, 0 critical behavioral violations, human review of 10 samples | External repos |

---

## Phase 4 · The Observatory

**Timeline:** 6 months from programme start · **Audience:** Everyone

| | Detail |
|---|---|
| **Input** | Phase 3 complete, eval results in markdown files, no visualisation |
| **Output** | Trust dashboard, drift detection, mutation testing, trace replay |
| **Delivery** | `docs/dashboard/trust.html` linked from README |
| **How tested** | Dashboard tested with synthetic data; drift tested with artificial regression |
| **Product feature** | A single URL that proves the GlassBox promise |

**Dashboard sections:**

1. Current ASL level per pipeline (easy / medium / hard)
2. Trust score trend — line chart, last 12 weeks
3. Golden dataset pass rate trend
4. LLM judge score trend
5. Last 10 agent runs with trace summaries

**Drift detection:** Compare current week's eval to trailing 4-week average. Alert if any metric drops > 10% with statistical significance (paired t-test, statistical threshold p < 0.05).

**Mutation testing:** Monthly via `mutmut`. Target: > 85% mutation kill rate.

---

## Phase 5 · Maturity

**Timeline:** 12+ months from programme start · **Audience:** AI community

| | Detail |
|---|---|
| **Input** | Phase 4 complete, dashboard live, 6+ months of quality data |
| **Output** | ASL-4 criteria, progressive automation, community eval contributions |
| **Delivery** | GlassBox Benchmark published, eval contribution guide |
| **How tested** | ASL-4 validated by 90-day production track record on certified repos |
| **Product feature** | "We are not just building an agent. We are building a standard." |

**ASL-4 (aspirational):**

| Level | Requirements | Deployment |
|-------|--------------|------------|
| ASL-4 (Autonomous) | 90-day track record, <5% error rate, trust > 0.9 sustained, 3+ human-guidance patterns encoded as rules | No human checkpoint required |

**Community evals:** Enabled by the composable `evals/core/` architecture. Contributing a
new eval = adding a YAML dataset + a Python scorer. Validated by CI on PR.

---

## Dependency Chain

| Phase | Consumes | Produces |
|-------|----------|----------|
| 1 | Current codebase | Tests + CI gate |
| 2 | Phase 1 tests | Traces + trust scores + golden dataset |
| 3 | Phase 2 traces + golden dataset | Judge scores + eval reports |
| 4 | Phase 3 eval reports | Dashboard + drift alerts |
| 5 | Phase 4 dashboard + 6+ months of data | ASL-4 + benchmark + community |

Nothing is wasted. Nothing is rearchitected. Each phase extends the previous.

---

## Known Risks + Mitigations

| Risk | Mitigation |
|---|---|
| Solo maintainer sustainability | Phases 1–3 are small. Golden dataset updates are quarterly, not daily. |
| LLM model changes shift scores | Pin model version in judge config. Recalibrate on major model releases. |
| ASL levels are self-certified | Acknowledged transparently in docs. External audit is a Phase 5 goal. |
| Golden dataset staleness | Issues drawn from real repo history. Refresh quarterly. |
| Dashboard maintenance | Static HTML generated from eval data. No backend server to maintain. |

---

## References

1. Anthropic — Bloom: automated behavioural evaluations (2025). Judge calibration: Spearman 0.86 with Opus. [alignment.anthropic.com/2025/bloom-auto-evals](https://alignment.anthropic.com/2025/bloom-auto-evals/)
2. OpenAI — Evaluation best practices: eval-driven development, LLM-as-judge with CoT. [platform.openai.com/docs/guides/evals](https://platform.openai.com/docs/guides/evals)
3. Google — SMURF: Speed, Maintainability, Utilization, Reliability, Fidelity (2024). [testing.googleblog.com](https://testing.googleblog.com/)
4. Linux Kernel — KUnit + kselftest dual-layer testing. [docs.kernel.org/dev-tools/testing-overview.html](https://docs.kernel.org/dev-tools/testing-overview.html)
5. UK AISI — Inspect: open-source eval framework (Tasks = Datasets + Solvers + Scorers). [inspect.aisi.org.uk](https://inspect.aisi.org.uk/)
6. Cleanlab — Real-time trust scoring across agent architectures (2024). [cleanlab.ai/blog/agent-tlm-hallucination-benchmarking](https://cleanlab.ai/blog/agent-tlm-hallucination-benchmarking/)
