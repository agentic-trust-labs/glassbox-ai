# glassbox-coder Design

**Target:** 100% SWE-bench Verified resolution. Metric: Human Minutes Per Resolved Issue (HMPRI), trending to zero.

## The Idea

Human + agent = 100% from day 1. The agent does heavy lifting. The human steers when confidence is low. Over time, the agent needs less steering.

## States (8 new + 6 base = 14 total)

```
received -> classifying -> understanding -> reproducing -> localizing -> patching -> validating -> reviewing -> ranking -> creating_pr -> done
                                                              ^                          |
                                                              +---- rediagnosing <-------+  (backward jump when localization was wrong)
```

Any state can route to `asking_author -> awaiting_author` when confidence is low. `retrying` handles failures with reflection. Both inherited from core.

## Transitions

| State | Events | Next State |
|---|---|---|
| classifying | ready / skip | understanding / done |
| understanding | understood / confused | reproducing / asking_author |
| reproducing | reproduced / no_repro / unclear | localizing / localizing / asking_author |
| localizing | found / not_found | patching / asking_author |
| patching | fixed / failed | validating / retrying |
| validating | passed / failed / rediagnose | reviewing / retrying / rediagnosing |
| rediagnosing | relocalize / ask_human | localizing / asking_author |
| reviewing (pause) | approved / rejected / guidance | ranking / retrying / patching |
| ranking | selected | creating_pr |

## Agents (7)

1. **Understander** - parse issue, build context. Single LLM call.
2. **Reproducer** - generate failing test for the bug. LLM + shell.
3. **Localizer** - find buggy code. Hierarchical: file -> function -> line. BM25 + LLM.
4. **Patcher** - generate N=5 candidate diffs at varying temperatures. Linter-gated.
5. **Validator** - run tests on each patch. Triggers rediagnose if failures suggest wrong localization.
6. **Ranker** - select best patch by majority vote + minimality + LLM review.
7. **Rediagnoser** - analyze test failures, decide: re-localize or ask human.

## Tools (5)

LLM (model API), Shell (subprocess.run), FileViewer (100 lines at a time), CodeSearch (grep + BM25), Linter (py_compile gate).

## Confidence (external, never self-reported)

- **Localization:** BM25 top-3 vs LLM top-3 overlap? Agree = proceed. Disagree = ask human.
- **Patching:** Are 3/5 candidates structurally similar? Yes = confident. All different = ask human.
- **Validation:** Passes repro test AND existing tests? Both = confident. Mixed = review closely.

## Human Interaction

Questions are precise, not vague. Always include: summary, the question, context, 2-3 options.
Review checkpoint (reviewing state) is mandatory before PR - catches patch overfitting.

## Progressive Automation (HMPRI Reduction)

| Phase | HMPRI | What Changes |
|---|---|---|
| Week 1-2 | ~30 min | Agent asks often, human drives |
| Month 1-3 | ~3-10 min | Agent handles easy/medium autonomously, human reviews PRs |
| Month 3+ | ~0.5-3 min | Confidence thresholds tuned from data, human rubber-stamps |

Primary drivers: better models, better prompts, calibrated thresholds. Memory/rules are secondary.

## Known Weaknesses (from devil's advocate)

1. Day-1 HMPRI may exceed human-only time (context-switching overhead)
2. Confidence calibration needs ~50-100 issues of data before reliable
3. Patch overfitting not fully solved - human review helps but is imperfect
4. Linear pipeline struggles with hard multi-file issues (9% of SWE-bench)
5. No easy/medium/hard branching - agents adapt internally instead

## Folder Structure

```
src/glassbox/use_cases/coder/
  __init__.py        states.py          pipeline.py         settings.py
  agents/            tools/             docs/DESIGN.md
```

## Key Design Decisions

- **No difficulty routing** - same pipeline for all, agents adapt depth internally
- **Dedicated reproducing state** - SOTA agents that reproduce bugs score higher
- **Reviewing is a PAUSE state** - human sees patch before PR (patch overfitting defense)
- **Rediagnosing enables backward jumps** - validating can route back to localizing
- **Single-agent pipeline, human as second agent** - simpler than multi-agent, human provides what multi-agent tries to provide (verification, course correction)
