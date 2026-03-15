# glassbox-coder Simulation: 10 SWE-bench Issues

🟢 = Works well | 🟡 = Caveats | 🔴 = Challenge | 🏆 = Human-in-loop shines | ⚡ = Insight

## Per-Issue Heatmap

| # | Issue | Diff | understand | reproduce | localize | patch | validate | review | States | HMPRI | Outcome |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | sklearn-10870 | 🟢 Easy | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 10 | ~1m | 🟢 Auto |
| 2 | django-10973 | 🟢 Easy | 🟢 | 🟡 no_repro | 🟢 | 🟢 | 🟡 | 🟢 | 10 | ~2m | 🟢 Auto |
| 3 | django-16983 | 🟡 Tricky | 🟢 | 🟢 | 🟢 | 🟡 string | 🟡 retry | 🟢 | 13 | ~1m | 🟡 Retry |
| 4 | sklearn-14520 | 🟡 Med | 🟢 | 🟢 | 🟡 big file | 🟢 | 🟢 | 🟢 | 10 | ~1m | 🟢 Auto |
| 5 | django-11039 | 🟡 Med | 🟢 | 🟡 | 🟡 3 files | 🟢 | 🟢 | 🟢 | 10 | ~2m | 🟢 Auto |
| 6 | django-13321 | 🟢 Med | 🟢 | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 | 10 | ~1m | 🟢 Auto |
| 7 | mpl-24971 | 🔴 Med | 🟡 visual | 🔴 no assert | 🔴 3 files | 🟡 | 🟡 | 🟡 | 14 | ~12m | 🔴 Human |
| 8 | sympy-17313 | 🔴 Hard | 🟡 math | 🟢 | 🟢 | 🔴 partial | 🟡 | 🏆 catches! | 17 | ~25m | 🏆 Human |
| 9 | sklearn-10774 | 🔴 Hard | 🟢 | 🟢 | 🔴 negative | 🔴 incomplete | 🔴 retry x3 | 🟡 | 20 | ~15m | 🔴 Retry |
| 10 | astropy-12907 | 🟡 Hard | 🟡 domain | 🟢 | 🟢 unique | 🟡 math | 🟢 | 🟡 | 10 | ~10m | 🟡 Auto |

## Aggregate Scores

| Metric | Score | Notes |
|---|---|---|
| 🟢 Resolution rate | **10/10 (100%)** | All resolved (with human help where needed) |
| ⏱️ Avg HMPRI | **~7 min** | Ranges from 1m (easy) to 25m (hard) |
| 🤖 Autonomous (HMPRI < 2m) | **6/10 (60%)** | Issues 1,2,3,4,5,6 |
| 🏆 Human-in-loop value-add | **3/10** | Issues 7,8,9 needed meaningful human steering |
| 🔄 Retries needed | **3/10** | Issues 3 (string), 8 (scope), 9 (files) |
| ↩️ Rediagnose triggered | **0/10** | Never needed backward jump (small sample) |

## Per-Aspect Analysis

### 🟢 What Works Well

- **Easy single-file bugs (Issues 1,2,3,4,5,6):** Pipeline is overkill but works cleanly. 10 states, linear, ~1-2 min HMPRI. The reproducing + localizing + patching flow is natural and fast.
- **Retry with reflection (Issue 3):** Exact-string test failures are self-correcting. Test output contains the expected string, retry agent feeds it back, next attempt succeeds.
- **Review checkpoint (Issue 8):** 🏆 THE showcase. Catches incomplete patches that pass tests. Human spots "you fixed __ge__ but not __gt__, __lt__, __le__" and sends guidance. This is exactly what autonomous agents miss.
- **Hierarchical localization (Issues 4,5):** File -> function -> line narrowing works for medium issues in large codebases. BM25 + LLM agreement signal is reliable for single-file bugs.

### 🟡 What Works With Caveats

- **No-repro path (Issues 2,7):** Pipeline correctly proceeds via `no_repro -> localizing` but validation is weaker without a reproduction test. Human review becomes more important.
- **Domain-heavy math (Issue 10):** Localization is easy (unique function names) but patch correctness depends on LLM math ability. N=5 sampling helps (2/5 get math right) but confidence is low.
- **Multi-candidate localization (Issue 5):** 3 candidate files. The N=5 patching naturally hedges (3/5 patch right file, 2/5 patch wrong file). Validation filters correctly.

### 🔴 What Breaks

- **Visual/geometric bugs (Issue 7):** Cannot reproduce (no testable assertion for "figure looks wrong"). Localization fails (3 interacting files). Human must drive. HMPRI = 12m. **This is the pipeline's worst case for single-file issues.**
- **Multi-file completeness (Issue 9):** Localizer finds 5/6 files, misses 1. Patcher produces incomplete diffs. Requires 3 retry cycles as each test failure reveals another missing file. **Reactive retry is O(n) in missing files.** Should ask human "is this the complete list?" proactively.
- **Scope completeness (Issue 8):** Localizer finds the right file but misses that 4 methods x 2 classes all need changes. Patcher produces partial fix. Tests may pass for the one method tested. **Only the human review catches this.** Without the reviewing state, this would be a false-positive submission.

### ⚡ Key Architectural Insights

1. **Reviewing state is non-negotiable.** Issues 8 and 9 prove it. Partial patches pass tests. Only human review catches incompleteness. Devin submitted the partial fix for Issue 8 and failed. glassbox-coder's human catches it.

2. **Reproduction is high-value but not always possible.** 7/10 reproduced, 2/10 couldn't (external deps, visual bugs), 1/10 partial. The `no_repro` path is essential - blocking on reproduction would stall 20-30% of issues.

3. **N=5 multi-candidate patching is the quiet hero.** Even when localization is ambiguous (Issue 5: 3 files), generating 5 patches means some target the right file. Validation filters naturally. This is better than getting localization perfect.

4. **Retry loop works for additive failures.** Issue 3 (exact string), Issue 9 (missing files) - each retry reveals new info from test output. But it's O(n) in number of failures, so multi-file issues churn.

5. **Rediagnosing was never triggered.** In 10 issues, validation failures were always "bad patch for right location" not "patch for wrong location." Sample too small, but suggests rediagnosing may be rare. Keep it but don't over-invest.

6. **The Localizer needs a "completeness mode."** For issues that say "add X to all Y" (Issue 9), the Localizer should do exhaustive search + ask human to confirm the list, rather than find-best-N.

## Revised HMPRI Projection

| Issue Type | Count in SWE-bench | Expected HMPRI (Week 1) | Expected HMPRI (Month 3) |
|---|---|---|---|
| 🟢 Easy (clean) | ~35% (175) | 1-2 min | 0.5 min (auto-approve) |
| 🟡 Easy (tricky) | ~5% (25) | 1-3 min | 1 min |
| 🟡 Medium (single-file) | ~45% (225) | 2-5 min | 1-2 min |
| 🔴 Medium (visual/domain) | ~6% (30) | 10-15 min | 5-8 min |
| 🔴 Hard (multi-file) | ~5% (25) | 15-20 min | 10-15 min |
| 🔴 Hard (scope/math) | ~4% (20) | 20-30 min | 10-15 min |
| **Weighted Average** | **500** | **~5.2 min** | **~2.1 min** |

## Design Changes Suggested by Simulation

| Change | Why | Priority |
|---|---|---|
| Add "completeness mode" to Localizer | Issue 9: multi-file misses | 🔴 High |
| Add human confirm for file lists | Issue 9: "is this all of them?" | 🔴 High |
| Track no_repro issues separately | Issues 2,7: weaker validation signal | 🟡 Medium |
| Visual bug detection heuristic | Issue 7: flag issues about plots/rendering | 🟡 Medium |
| Scope-expansion prompt in Patcher | Issue 8: "are there related methods?" | 🟡 Medium |
| Rediagnosing: lower priority | 0/10 triggered in simulation | 🟢 Low |
