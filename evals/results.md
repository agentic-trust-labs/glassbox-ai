# GlassBox Agent v2 — Eval Results

**Run date:** 2026-02-15
**Agent version:** v2 (template-driven multi-agent)
**Model:** gpt-4o-mini (Manager + JuniorDev + Tester)

## Bug Definitions

| # | ID | File | Line | Original | Mutation | Template | Catching Test |
|---|-----|------|------|----------|----------|----------|---------------|
| 1 | E08 | orchestrator.py | 12 | `gpt-4o-mini` | `gpt-4o-mni` | typo_fix | test_critic_model_name |
| 2 | E01 | trust_db.py | 32 | `else 0.85` | `else 0.50` | wrong_value | test_01, test_02 |
| 3 | E11 | trust_db.py | 59 | `max(0.3,` | `max(0.0,` | wrong_value | test_05 |
| 4 | E12 | trust_db.py | 24 | `VALUES (?, 0.85)` | `VALUES (?, 0.50)` | wrong_value | test_01 |
| 5 | E13 | orchestrator.py | 11 | `0.5` | `1.5` | wrong_value | test_16 |
| 6 | E14 | trust_db.py | 23 | `"critic"` in list | removed | wrong_name | test_01 |
| 7 | E15 | trust_db.py | 59 | `min(1.0,` | `min(0.9,` | wrong_value | test_14 |
| 8 | E16 | trust_db.py | 36 | `DESC` | `ASC` | wrong_name | test_13 |
| 9 | E17 | trust_db.py | 47 | `* 100` | `* 10` | wrong_value | test_10 |
| 10 | E18 | orchestrator.py | 10 | `design review` | `code review` | wrong_name | test_22 |

## Results

| # | Bug | Status | Attempts | Template Match | Issue | PR |
|---|-----|--------|----------|----------------|-------|-----|
| 1 | E08 typo `gpt-4o-mni` | ✅ Solved | 1/2 | typo_fix 95% | [#52](https://github.com/agentic-trust-labs/glassbox-ai/issues/52) | [#53](https://github.com/agentic-trust-labs/glassbox-ai/pull/53) |
| 2 | E01 default trust `0.50` | ✅ Solved | 1/2 | wrong_value 95% | [#54](https://github.com/agentic-trust-labs/glassbox-ai/issues/54) | [#55](https://github.com/agentic-trust-labs/glassbox-ai/pull/55) |
| 3 | E11 floor `0.0` | ✅ Solved | 1/2 | wrong_value 95% | [#56](https://github.com/agentic-trust-labs/glassbox-ai/issues/56) | [#57](https://github.com/agentic-trust-labs/glassbox-ai/pull/57) |
| 4 | E12 seed value `0.50` | ✅ Solved | 1/2 | wrong_value 95% | [#58](https://github.com/agentic-trust-labs/glassbox-ai/issues/58) | [#59](https://github.com/agentic-trust-labs/glassbox-ai/pull/59) |
| 5 | E13 temp `1.5` | ✅ Solved | 1/2 | wrong_value 95% | [#60](https://github.com/agentic-trust-labs/glassbox-ai/issues/60) | [#61](https://github.com/agentic-trust-labs/glassbox-ai/pull/61) |
| 6 | E14 missing critic seed | ✅ Solved | 1/2 | wrong_value 95% | [#62](https://github.com/agentic-trust-labs/glassbox-ai/issues/62) | [#63](https://github.com/agentic-trust-labs/glassbox-ai/pull/63) |
| 7 | E15 ceiling `0.9` | ✅ Solved | 1/2 | wrong_value 95% | [#64](https://github.com/agentic-trust-labs/glassbox-ai/issues/64) | [#65](https://github.com/agentic-trust-labs/glassbox-ai/pull/65) |
| 8 | E16 sort `ASC` | ⏸️ Pending | — | — | — | — |
| 9 | E17 accuracy `*10` | ⏸️ Pending | — | — | — | — |
| 10 | E18 `code review` | ⏸️ Pending | — | — | — | — |

## Summary

| Metric | Value |
|--------|-------|
| Total bugs | 10 |
| ✅ Solved | **7** |
| ⏸️ Pending | 3 |
| ❌ Failed | 0 |
| Pass rate | **100%** (7/7 attempted) |
| Avg attempts | **1.0** |
| First-try rate | **100%** |
