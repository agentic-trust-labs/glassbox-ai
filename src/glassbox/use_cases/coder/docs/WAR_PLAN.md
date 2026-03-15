# GlassBox Coder — War Plan v2

> **Decision:** Approach B (Own Loop + litellm) — 100 lines, 4 files, 1 dependency.
> **Research:** 35+ sources (7 FAANG blogs, 9 papers, 6 repos, 4 commercial agents, 10+ patterns).

## Why Approach B

| Criteria | Approach B | A (mini-swe-agent) | C (Claude SDK) | D (Agentless) |
|---|---|---|---|---|
| Lines | **100** | ~90 | ~60 | ~120 |
| Dependency | litellm (15MB) | mini-swe-agent (20MB) | claude-sdk (200MB) | litellm (15MB) |
| Lock-in | None | Princeton release | **Claude only** | None |
| Perf (SWE-bench) | 70-74% | 74%+ | 75%+ | 27-40% |
| We own loop | **Yes** | No | No | N/A (no loop) |
| HITL | First-class | Bolted-on | Bolted-on | First-class |

**Key validations from research:**
- Agent loop is commodity code — 15-30 lines, every SOTA agent uses the same pattern (Anthropic, OpenAI, mini-swe-agent, Augment Code)
- System prompt = biggest lever — OpenAI: +20% from 3 ingredients (persistence, tool-calling, planning)
- Single agent for coding — Anthropic: multi-agent uses 15x tokens, not suited for coding
- grep+find sufficient — Augment Code (65.4%): "embedding-based retrieval was not the bottleneck"
- Model quality > architecture — Augment: "scores largely driven by foundation model quality"
- HITL essential — HULA (ICSE 2025): 54% said code had defects without human review

## 30 System Design Aspects

| # | Aspect | How Handled | Expected |
|---|---|---|---|
| 1 | Domain-agnostic engine | Engine unchanged; states.py+pipeline.py = full use case | Swap use case = 0 engine changes |
| 2 | HITL as first-class state | `reviewing` in PAUSE_STATES — engine halts | Zero unreviewed patches ship |
| 3 | Append-only audit trail | AuditEntry on every engine.step() | Full issue reconstruction |
| 4 | Model-agnostic | litellm + env var `GLASSBOX_MODEL` | 100+ models, zero code changes to swap |
| 5 | Agents as plain functions | `def fn(ctx, **kw) -> dict` | New agent = 1 function + 1 pipeline line |
| 6 | External system prompt | Loaded from file or fallback constant | A/B test prompts without deploy |
| 7 | Single agent loop | One `for step in range(...)` loop | 70-74% autonomous (same as mini-swe-agent) |
| 8 | Bash-only tool | Single `bash(command)` tool via litellm tools param | Same coverage as 5-tool agents |
| 9 | Output truncation | head/tail at 10K chars + guidance message | Agent never loses context to large output |
| 10 | Cost tracking | litellm `response_cost` accumulated per step | Per-issue cost in audit trail |
| 11 | Step limiting | `step_limit` from env var (default 30) | Bounds compute; stuck → human |
| 12 | Subprocess timeout | `timeout=120` on every subprocess.run() | No single command blocks >2min |
| 13 | Retry with feedback | Failure detail appended to task on retry | 10-20% stuck issues recover |
| 14 | Human guidance injection | Feedback appended to task, agent re-runs | 50%+ stuck issues resolve with guidance |
| 15 | Structured questions | _ask_author formats recent failures as bullets | Human responds in <2min |
| 16 | Patch via git diff | `git diff` captures actual filesystem changes | Ground truth, not reconstructed |
| 17 | Env var config | All settings from os.environ + defaults | 12-factor, zero-config startup |
| 18 | Lazy imports | litellm imported inside _solve only | Pipeline import <10ms |
| 19 | History-based recovery | ctx.history scanned by retry/review/ask_author | No hidden state |
| 20 | Backward-compatible core | pause_states param defaults to existing PAUSE_STATES | Existing tests pass unchanged |
| 21 | AX/UX separation | Agent sees messages (AX), human sees AuditEntry (UX) | Decoupled views |
| 22 | Stateless subprocess | subprocess.run(cwd=cwd) each call, no persistent shell | Deterministic, reproducible |
| 23 | Graceful degradation | Missing agent → error event, not crash | Misconfigured pipeline → failed state |
| 24 | Tool desc as prompt | Bash tool description guides efficient command usage | Agent uses sed -n, head, etc. |
| 25 | Completion sentinel | `GLASSBOX_TASK_COMPLETE` echo = explicit done signal | Unambiguous termination |
| 26 | Progressive automation | AuditEntry data enables threshold tuning over time | Audit→Assist→Auto path |
| 27 | Prompt caching | litellm auto-caches static prefix | 50-90% input token cost reduction |
| 28 | Multi-tool-call | `for tc in msg.tool_calls` handles parallel calls | Future-proof for parallel bash |
| 29 | Error as information | Exceptions → string messages fed back to LLM | Self-correction, not crash |
| 30 | Zero coupling | coder/ imports only core.state.BASE_TRANSITIONS | Independent dev/test/deploy |

## 50 Edge Cases

| # | Edge Case | Handling | Expected Resolution |
|---|---|---|---|
| 1 | Empty issue body | LLM reasons from title; `stuck` → human | 90% with human |
| 2 | Feature request (not bug) | Agent attempts; _classify filters in future | 60% simple features |
| 3 | Stack trace in body | Agent extracts file:line from trace | 85%+ autonomous |
| 4 | External URL reference | Can't access; `stuck` → human pastes content | 95% with human |
| 5 | Duplicate issue | Agent finds fix applied; reports no-repro | Clean termination |
| 6 | Contradictory requirements | Best-effort; `stuck` if tests conflict | 80% with guidance |
| 7 | Non-English issue | Modern LLMs handle multilingual | 70%+ major languages |
| 8 | Images/screenshots | Can't see; `stuck` → human describes | 85% with description |
| 9 | References commit hash | `git log`/`git diff` for localization | 80%+ |
| 10 | 10K+ char issue body | LLM handles long context | 75% |
| 11 | Requires external deps | Discovers missing dep; `stuck` → human | 70% with guidance |
| 12 | Repro script provided | Copies, runs, confirms failure | 85%+ |
| 13 | Intermittent/flaky bug | Multiple runs; proceeds from description if unreproducible | 50% auto, 80% human |
| 14 | Infinite loop in repro | `timeout=120` kills process; agent adjusts | 70% |
| 15 | OS/version specific | Checks `python --version`; notes mismatch | 75% controlled env |
| 16 | Complex setup (Docker) | Reads Makefile/tox.ini; `stuck` if too complex | 60% with human |
| 17 | No test file exists | Writes own repro script | 70% |
| 18 | Performance regression | Timing scripts; human judges | 60% |
| 19 | Bug in test itself | Doesn't modify tests (prompt rule); `stuck` + analysis | 80% with human |
| 20 | Import error blocks repro | Runs `pip install`; fails if unavailable | 75% |
| 21 | Common filename (15 utils.py) | `find` + `grep` for content matching | 70% |
| 22 | Generated/minified code | Reads headers/.gitignore; avoids editing | 65% |
| 23 | 5000+ line file | `sed -n`, `grep -n`; tool desc guides this | 70% |
| 24 | Bug in import chain | `grep -r "from X import"` traces imports | 65% |
| 25 | 10K+ files in repo | Targeted `find`; never lists all | 70% |
| 26 | Bug in test fixture | Identifies root cause in test; `stuck` + analysis | 75% with human |
| 27 | Copy-paste bug (3 places) | `grep -rn` finds all; fixes all | 75% |
| 28 | Non-Python code (C ext) | sed edits; `stuck` if compilation fails | 50% with human |
| 29 | Misleading variable names | LLM reasons semantically | 70% |
| 30 | Fix requires reading docs | Reads docstrings/comments | 75% |
| 31 | Create new file | `cat > newfile.py << 'EOF'` via bash | 75% |
| 32 | Delete a file | `rm file.py`; git diff shows deletion | 80% |
| 33 | Single-char fix (> to >=) | `sed -i 's/old/new/'` | 90%+ |
| 34 | 100+ line change | Multi-step iteration; may use full step budget | 60% |
| 35 | Hallucinated API | Tests fail → NameError → self-corrects next step | 70% |
| 36 | Syntax error in patch | `python -c "import ast..."` catches; self-corrects | 85% |
| 37 | Patch breaks existing tests | pytest output → revises patch (core loop strength) | 75% |
| 38 | Indentation error | python catches it; agent fixes | 80% |
| 39 | 5+ file change | Sequential edits; step budget may be tight | 55% |
| 40 | Fix = revert commit | `git revert` if identified | 40% auto, 80% human |
| 41 | Test suite >5min | Runs targeted tests only | 70% |
| 42 | 100K+ chars test output | Truncated at MAX_OUTPUT with guidance | 80% |
| 43 | Flaky test | May false-pass; human review catches | 60% auto, 90% human |
| 44 | Overfitting patch | `reviewing` PAUSE — human judges quality | 95% with human |
| 45 | No existing tests | Writes own verification script | 65% |
| 46 | Tests need env vars | Reads conftest.py/tox.ini | 60% |
| 47 | Human gives wrong guidance | Follows it, tests fail, retries | 70% second attempt |
| 48 | Human says "I don't know" | Retries with different strategy | 40% |
| 49 | Human provides code fix | Applies code from guidance | 95% |
| 50 | Human never responds | `awaiting_author` → timeout → `failed` | Clean termination |

## File Structure

```
src/glassbox/use_cases/coder/
    __init__.py      (3 lines)   Module identity
    states.py        (14 lines)  TRANSITIONS + PAUSE_STATES
    settings.py      (11 lines)  load_settings() from env vars
    pipeline.py      (72 lines)  build_pipeline() + 6 agent functions
    prompts/
        default.txt  (~25 lines) External system prompt (not counted)
    docs/
        WAR_PLAN.md              This file
        DESIGN.md                Architecture overview
        SIMULATION.md            SWE-bench simulation
```

Core changes: `engine.py` (+3 lines), `tools/llm.py` (~7 lines swapped).

## Expected Performance

| Metric | Value | Basis |
|---|---|---|
| Autonomous (SWE-bench) | 70-74% | Same pattern as mini-swe-agent 74%+ |
| With HITL (easy) | 80-85% | Human catches overfitting + guides stuck |
| With full HITL | 95-100% | Human solves what agent can't |
| Cost per issue | $0.50-$3.00 | 5-30 steps × $0.01-$0.10/step |
| Median steps | 12 | Anthropic reports 12 for successful |
| Time per issue | 2-10 min | LLM latency dominated |

## Future Roadmap (not in 100 lines)

| When | What | Lines | Source |
|---|---|---|---|
| Week 2 | Context compaction | ~10 | Codex CLI pattern |
| Week 3 | str_replace_editor tool | ~15 | Anthropic SWE-bench |
| Month 2 | Ensemble (3 models) | ~20 | TRAE/Augment pattern |
| Month 3 | MCTS search | ~30 | SWE-Search (ICLR 2025) |
| Month 3 | Progressive auto-merge | ~5 | MightyBot pattern |
