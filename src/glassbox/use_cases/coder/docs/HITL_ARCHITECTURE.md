# HITL Learning System - Architecture Plan

**Status:** Approved for implementation
**Date:** 2025-03-16
**Approach:** B (Rules + Episode Store + Offline Reflection)
**Budget:** ~50-70 lines of implementation code, 0 new dependencies, 0 core changes

---

## Grounding

- 60+ research sources, 20+ papers
- Current codebase: pipeline.py (227 lines), tools.py (435 lines), states.py (13 lines), settings.py (14 lines), run_swebench.py (156 lines), core/engine.py (257 lines)
- Every production agent (Claude Code, Cursor, Codex CLI, Aider) converged on plain markdown for rules

## Selected Approach: B (Rules + Episode Store + Offline Reflection)

- `RULES.md` (always-on, injected into system prompt)
- `episodes.jsonl` (correction store, append-only)
- `recall_episodes` tool (agent-initiated retrieval)
- `reflect.py` (offline analysis script, proposes rules for human review)
- Human reviews ALL rule promotions (strict evaluator = +3.4%, add-all = -12%)

### Why B Wins

| Criterion | A (Manual) | B (Lean) | C (Vector DB) | D (Fine-tune) |
|---|---|---|---|---|
| Design aspects covered | 15/30 | 28/30 | 18/30 | 8/30 |
| Edge cases handled | 12/30 | 26/30 | 15/30 | 8/30 |
| Lines of code | ~10 | ~50-70 | ~300+ | 1000+ |
| New dependencies | 0 | 0 | 2+ | Training infra |
| Human quality gate | Manual only | Structured review | None (dangerous) | Manual data curation |
| Time to implement | 1 hour | 2-3 hours | 1-2 weeks | 2-4 weeks |

---

## 30 System Design Aspects

### Storage & Format
- **D01. Rule storage format** - Plain markdown (`RULES.md`), one-line imperative bullets, version-controlled in git. Every production agent converged on this.
- **D02. Episode storage format** - JSONL (`episodes.jsonl`), one correction per line. Fields: id, timestamp, instance_id, problem_summary, agent_strategy, failure_reason, human_correction, tags[], importance.
- **D03. Rule ordering** - Most important/frequently-triggered first. IFScale: primacy effect means first rules get highest compliance.
- **D04. Context budget** - Hard limit: 30-50 rules (~700-1100 tokens). Soft limit: 3 episodes per retrieval (~500 tokens each). Total learning budget: <2500 tokens.
- **D05. Rule format spec** - Each rule is one imperative sentence: `- WHEN [trigger], DO [action] BECAUSE [reason]`. No vague language.

### Injection & Retrieval
- **D06. Rule injection point** - Append RULES.md content to SYSTEM_PROMPT after `# Rules` section. Read at `_solve()` start. Missing file = proceed without rules.
- **D07. Episode retrieval** - New `recall_episodes` tool. Agent calls it voluntarily. BM25 keyword matching, returns top 3.
- **D08. Retrieval integration** - Tool response in message history, like any other tool output. Zero changes to core engine.
- **D09. Cold start** - Day 0: no RULES.md, system works as-is. First human correction creates first episode. After 3-5 corrections, first reflection proposes first rules.
- **D10. Prompt caching** - Rules in static system prompt prefix. Rules change rarely (weekly), cache hit rate stays high.

### Correction Capture & Lifecycle
- **D11. Correction capture point** - In `_review()` when human provides guidance. Zero new states. Happens in EXISTING review flow.
- **D12. Episode structure** - Captures: what agent tried, why it failed, what human corrected, root cause category, strategy learned.
- **D13. Importance scoring** - Initial=2. Success after correction=+1. Cross-task pattern confirmed=+2. Decay by 1 every 50 issues if untriggered. Max=10, prune at 0.
- **D14. Rule promotion path** - Episode -> pattern across 3+ episodes -> proposed rule -> human reviews -> merged to RULES.md. Never auto-promote.
- **D15. Rule deprecation** - Flag if target error absent for 100+ issues. Human confirms removal. Never auto-delete.

### Safety & Quality
- **D16. Conflict detection** - LLM check before merge: "Do any of these rules contradict?" Use different model than coding agent.
- **D17. Regression testing** - After RULES.md change, re-run 5-10 SWE-bench instances. Regression > 5% = reject change.
- **D18. Error cascade prevention** - If correction strategy fails on re-run, mark episode as `contested` (importance=-1). Don't retrieve contested episodes.
- **D19. Negative transfer guards** - Domain tags on rules: `[django]`, `[astropy]`. Only activate when domain matches.
- **D20. Rule compliance monitoring** - Per-run logging: was rule relevant? Was it followed? Did following it help?

### Integration & Architecture
- **D21. Zero core changes** - All HITL learning in `use_cases/coder/`. No changes to core/engine.py, core/models.py, core/state.py.
- **D22. No new states** - Correction capture in existing `_review()`. Retrieval is a tool call in existing `_solve()`. Reflection is offline.
- **D23. No new dependencies** - BM25 via stdlib `re` + `collections.Counter`. JSON via stdlib `json`. Zero pip packages.
- **D24. Offline reflection** - Standalone `reflect.py`. Runs manually or on cron. Keeps agent loop fast.
- **D25. Benchmark integration** - `--rules-file` flag in `run_swebench.py` for A/B testing.

### Observability & Evolution
- **D26. Git audit trail** - RULES.md committed like code. `git blame` shows provenance of each rule.
- **D27. Observability logging** - Log at `_solve()` start: "Loaded N rules, M episodes available."
- **D28. Graceful degradation** - Missing RULES.md = skip. Corrupted episodes.jsonl = skip. Failed recall = continue. Never crash.
- **D29. Multi-project support** - Section headers in RULES.md: `## Universal` and `## Project: <name>`. Only matching rules injected.
- **D30. Migration path** - JSONL -> any DB trivially. Episode schema is embedding-friendly for future vector DB upgrade.

---

## 30 Edge Cases

### Rule Quality Issues
- **E01. Contradictory rules** - D16 conflict detection catches at review time. Make both conditional with WHEN triggers. -> Caught at review.
- **E02. Stale rule after model upgrade** - D15 deprecation: flag if target error absent 100+ issues. Human removes. -> Pruned within 2 months.
- **E03. Rule helps Domain A, hurts Domain B** - D19 domain tags. Only activate when domain matches. -> Tags prevent cross-contamination.
- **E04. 80 rules exceed budget** - D04 hard limit at 50. Loader truncates + warns. D17 regression testing catches degradation. -> Hard limit enforced.
- **E05. Rule too vague** - D05 format spec: must have WHEN trigger + DO action. Flagged at proposal time. -> Never merged.
- **E06. Rule too specific** - D05 format spec: must be generalizable. Reflection checks for specific issue IDs/line numbers. -> Caught at reflection.
- **E07. Bad correction stored** - D18: if correction strategy fails on re-run, mark episode as `contested`. Importance=-1. -> Bad correction quarantined.
- **E08. Agent ignores rule** - D20 compliance monitoring. Diagnose: buried? vague? context overflow? -> Requires human diagnosis.
- **E09. Duplicate rules** - D19 deduplication: cosine > 0.85 = flag as duplicate. Human merges. -> Caught at reflection.
- **E10. Rule fails at high temp** - D17 regression test at operational temperature. -> Tested at real conditions.

### Episode Store Issues
- **E11. 10K+ episodes** - Archive old episodes (>6 months). Optional SQLite upgrade. -> Archive script handles.
- **E12. Irrelevant episodes retrieved** - Agent can ignore. Limit to 3 results. Worst case: minor context waste. -> Minor context waste.
- **E13. No relevant episodes** - System works without episodes (current behavior). Rules still apply. -> Graceful fallback.
- **E14. Conflicting episodes** - Importance scoring ranks. Conflict check at reflection. -> Human resolves at reflection.
- **E15. Sensitive code in episode** - Episode stores strategy, not raw code. Human reviews at capture. -> Redacted at capture.

### Runtime Integration Issues
- **E16. RULES.md missing** - `_solve()` checks `is_file()`. Missing = use SYSTEM_PROMPT as-is + log warning. -> Graceful fallback.
- **E17. RULES.md malformed** - try/except around file read. On error, skip rules + log warning. -> Graceful fallback.
- **E18. recall_episodes fails** - Return "Episode retrieval unavailable. Proceed with your own analysis." -> Graceful fallback.
- **E19. Excessive retrieval calls** - Tool description says max 2 calls. Handler tracks per session if needed. -> Soft limit via prompt.
- **E20. Agent over-relies on rules** - System prompt still says "plan extensively." Rules supplement reasoning. -> Monitor for decline.

### Human-in-the-Loop Issues
- **E21. Human never reviews proposals** - Proposed rules stay in RULES_PROPOSED.md. Never auto-merge. System works with existing rules. -> Learning stalls but system works.
- **E22. Multiple humans conflict** - Git attribution + team discussion. -> Requires team discussion.
- **E23. Human gives wrong guidance** - Outcome tracked after re-run. Contested flag. Importance=-1. -> Self-healing.
- **E24. Cold start day 1** - System runs exactly as today. First correction creates first episode. -> Current behavior preserved.
- **E25. Correction too long** - Episode correction_text truncated to 500 chars. Reflection extracts actionable insight. -> Truncation + distillation.

### Evolution & Scale Issues
- **E26. Context window changes** - Budget is conservative (2500 tokens). Increase limits in config when model changes. -> Config change only.
- **E27. Rule references nonexistent tool** - D05: rules reference actions, not tool names. -> Caught at review.
- **E28. Episode format migration** - JSONL: new fields added with defaults. Old episodes missing new field simply lack it. -> Backward compatible.
- **E29. Rules across branches** - RULES.md is git-tracked. Branch-specific rules work naturally. -> Git handles it.
- **E30. Error cascade compounding** - Rules prevent early mistakes. Illusion of Diminishing Returns: preventing one early error prevents the cascade. -> Rules break the chain.

---

## Implementation Plan

### Code Changes (50-70 lines total, lean v1)

**Modified files (3):**
1. `pipeline.py` - Load RULES.md into prompt (~8 lines), capture episodes in `_review()` (~12 lines), handle `recall_episodes` tool (~18 lines)
2. `tools.py` - RECALL_EPISODES_TOOL definition (~25 lines), update TOOLS list
3. `run_swebench.py` - `--rules-file` flag (~5 lines)

**New files (2):**
4. `memory/episodes.py` - Episode store: append, load, search (~70 lines)
5. `memory/reflect.py` - Offline reflection: propose rules (~100 lines, standalone script, not counted in core 50-70)

**Data files (created at runtime):**
6. `RULES.md` - Starts empty, grows from corrections
7. `episodes.jsonl` - Starts empty, grows from corrections

### Principles
- 0 new dependencies
- 0 core/ changes
- 0 new states
- Everything degrades gracefully (missing file = skip, error = continue)
- Human reviews ALL rule promotions
- reflect.py is offline, never runs during agent loop
