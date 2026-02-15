# GlassBox AI - Adaptive Complexity Architecture

**Date:** 2026-02-15
**Status:** RFC (Request for Comments)
**Owner:** @sourabharsh

---

## 0. Executive Summary

GlassBox currently handles **easy cases only** - single-file, single-boundary, grep-and-replace bugs. This document architects the system to handle **easy, medium, and hard cases** with adaptive UX: easy cases are fully automated, medium cases use orchestrated multi-step solving, and hard cases produce structured reasoning for human-agent collaboration via GitHub's chat interface.

The core insight from industry research: **no coding agent today solves hard problems autonomously**. The best systems (Devin, Rovo Dev, SWE-agent) succeed by knowing their limits and collaborating with humans effectively. Our competitive advantage is making that collaboration transparent and progressively automated.

---

## 1. Research Landscape

### 1.1 How Leading Coding Agents Handle Complexity

| System | Architecture | Complexity Strategy | Key Insight |
|--------|-------------|---------------------|-------------|
| **Devin** (Cognition) | Multi-agent, full sandbox | Clear upfront scoping. Escalates ambiguity. "Start fresh > iterate". 67% PR merge rate. | Fails on mid-task scope changes. Junior execution at infinite scale. |
| **Rovo Dev** (Atlassian) | CLI agent + Jira/Confluence/Bitbucket. Adaptive memory. | #1 SWE-bench Full (41.98%). Memory persists across sessions. MCP extensible. | Deep ecosystem integration. Per-project memory is key. |
| **SWE-agent** (Princeton) | Agent-Computer Interface. ReAct loop. Custom shell commands. | Iterative explore-edit-test cycle. Custom ACI reduces action space. | Clean interface design. No planning phase = struggles multi-file. |
| **AutoCodeRover** | LLM + Spectrum-Based Fault Localization. AST search. | Executes failing tests to locate faults. Function-level localization. | Interpretable but requires existing failing tests. |
| **Agentless** (UIUC) | Two-stage workflow: hierarchical localization, then majority-vote patches. | File -> function -> line narrowing. Multiple candidates, best selected. | Simple, predictable cost. No agent loop overhead. |
| **MASAI** (Microsoft) | Modular sub-agents, each with tuned objectives + strategies. | Different sub-agents for different sub-tasks. Divide-and-conquer. | Modularity wins. Each sub-agent optimized independently. |
| **MarsCode** (ByteDance) | Code knowledge graph + Reproducer Agent + graph reasoning. | Repro-first. Graph reasoning for fine-grained localization. Top SWE-bench Lite. | Reproduction-driven validation is powerful. |
| **GitHub Copilot Agent** | Async agent in GitHub. Uses CI. Creates draft PRs. | Works asynchronously. Native GitHub integration. | Limited to well-scoped issues. No iterative collaboration. |
| **AutoDev** (Microsoft) | Fully autonomous. Docker sandbox. LATS planning. | Language Agent Tree Search for planning. Full tool access. | Overkill for simple bugs. Planning overhead. |

### 1.2 OpenAI Deep Research

Key insight: for hard problems, producing a **research report** (not a code fix) may be the right output. Powered by o3, reasons over 5-30 min, browses dozens of sources, synthesizes with citations.

### 1.3 Key Patterns Across All Systems

| ID | Pattern | Who Uses It |
|----|---------|-------------|
| P1 | Difficulty-aware routing | MASAI, our proposal |
| P2 | Reproduction-first | MarsCode, AutoCodeRover |
| P3 | Hierarchical localization (file->function->line) | Agentless, MarsCode |
| P4 | Code knowledge graph | MarsCode, Alibaba Lingma |
| P5 | Candidate patches + majority vote | Agentless, MarsCode |
| P6 | Checkpoint collaboration (pause for human) | Devin, Rovo Dev |
| P7 | Memory across sessions | Rovo Dev, Reflexion |
| P8 | Start fresh > iterate on broken state | Devin |
| P9 | Test-driven validation (tests are truth) | All top systems |
| P10 | Modular sub-agents | MASAI, MarsCode |

---

## 2. Requirements

### 2.1 Adaptive UX by Difficulty

```
         ISSUE ARRIVES (labeled 'agent')
                   |
              CLASSIFIER
            /      |      \
         EASY    MEDIUM    HARD
          |        |         |
       Auto-fix  Orchestr-  Research Report
       + PR      ated       + Conversation
                 multi-step  with Author
                 + PR
```

### 2.2 Difficulty Classification Criteria

| Signal | Easy | Medium | Hard |
|--------|------|--------|------|
| Files affected | 1 | 2-5 | 5+ or unknown |
| Boundary crossings | 0 | 1-2 | 3+ or novel |
| Requires reproduction | No | Maybe | Yes |
| Fix pattern | Template-matched | Decomposable into steps | Architectural reasoning |
| Test coverage | Existing tests cover area | Partial | No tests or misleading |
| Issue clarity | Explicit acceptance criteria | Partially specified | Ambiguous |
| Confidence | >= 0.85 | 0.50-0.84 | < 0.50 |

### 2.3 Pipeline Specifications

**EASY** (current - keep, refine): Manager -> Junior Dev -> Tester -> PR. Zero human involvement. Target 90% pass.

**MEDIUM** (new): Planner decomposes -> step-by-step execution with checkpoints -> integration test -> PR. Optional human checkpoints. Target 60% autonomous, 85% with one checkpoint.

**HARD** (new): Researcher analyzes -> posts structured report -> awaits author conversation -> iterates. NOT a PR initially. A research report. Target 70% eventually resolved through conversation.

### 2.4 The Conversational Loop (GitHub Chat Interface)

The GitHub issue comment thread becomes a structured conversation:

```
  AUTHOR creates issue, labels 'agent'
           |
  BOT: "Picked up. Classified as [MEDIUM/HARD]. Here's my plan:"
  - Step 1: ...
  - Step 2: ...
  "Proceeding with Step 1."
           |
      BOT attempts Step 1
        /          \
    SUCCESS        FAIL
      |              |
  BOT: "Step 1    BOT: "Step 1 failed. Here's what I tried
   done. Moving    and why it didn't work: [reasoning]
   to Step 2."
                   I see two possible next approaches:
                   A) ...
                   B) ...

                   @author - which direction?"
                       |
                   AUTHOR: "Try A, but also
                   consider that module X
                   depends on Y."
                       |
                   BOT: "Got it. Retrying with A
                   + considering X->Y dependency."
```

**Design principles:**
1. **Show reasoning, not just results** - author needs to understand *why*
2. **On failure, present options** - don't retry blindly. Present 2-3 alternatives with tradeoffs
3. **Accept direction from author** - parse comment for guidance, incorporate into next attempt
4. **Progressive automation** - if the same guidance pattern appears 3+ times, encode it as a rule
5. **Never go silent** - if working, post updates. If stuck, say so immediately.
6. **Bounded attempts** - max 3 autonomous retries, then MUST ask author

---

## 3. The 38 System Cases

### 3.1 Easy Cases (E01-E12) - Fully Automated

| ID | Case | Why Easy | Approach |
|----|------|----------|----------|
| **E01** | Wrong literal value (0.50 should be 0.85) | Single line, single file, value swap | Template: `wrong_value`. Locate, replace, test. |
| **E02** | Typo in string ("gpt-4o-mni" -> "gpt-4o-mini") | Character-level error, grep-findable | Template: `typo_fix`. String match, replace, test. |
| **E03** | Wrong variable name (`__ver__` -> `__version__`) | Single identifier, import error gives exact info | Template: `wrong_name`. Error message pinpoints it. |
| **E04** | Wrong table name in SQL string | Single string inside SQL, still single-file | Template: `wrong_name`. Locate SQL, fix name, test. |
| **E05** | Swapped function arguments (min/max inverted) | Arguments in wrong order, single expression | Template: `swapped_args`. Swap, test. |
| **E06** | Missing import statement | ImportError gives exact module name | Add import at top. Test. |
| **E07** | Off-by-one in loop boundary | Single numeric change in loop condition | Locate loop, adjust boundary, test. |
| **E08** | Wrong dict key ("critics" vs "critic") | Single string mismatch, KeyError gives key | Template: `wrong_name`. Replace key, test. |
| **E09** | Hardcoded value should be constant (same file) | Single value extraction, same file | Template: `wrong_value`. Extract, replace refs, test. |
| **E10** | Wrong comparison operator (< instead of <=) | Single character change | Locate, fix operator, test. |
| **E11** | Duplicate dict key / list entry | Syntactically valid but logically wrong | Remove duplicate, test. |
| **E12** | Wrong default parameter value | Single function signature change | Fix default, test callers. |

### 3.2 Medium Cases (M01-M14) - Orchestrated Multi-Step

| ID | Case | Why Medium | Steps |
|----|------|-----------|-------|
| **M01** | Cross-boundary constant extraction (Python var in SQL) | Value in Python AND SQL - naive replace breaks SQL | 1. Classify occurrences as Python vs DSL. 2. Extract constant. 3. Handle DSL via f-string or leave literal. 4. Test. |
| **M02** | Multi-file rename (function used across 3-5 files) | Change propagates. Missing one ref breaks imports. | 1. Build reference graph. 2-N. Rename per file. N+1. Test after each. |
| **M03** | API return type mismatch (dict vs object) | Requires understanding SDK types | 1. Read API docs for actual return type. 2. Map access patterns. 3. Fix each. 4. Test with typed mock. |
| **M04** | Add new endpoint / API route | Multiple files: route, handler, model, test | 1. Design API. 2. Implement handler. 3. Register route. 4. Write test. Checkpoint after step 1. |
| **M05** | Database schema migration + code update | Schema change cascades to queries + models | 1. Design schema. 2. Update model. 3. Update queries. 4. Migration script. 5. Test. Checkpoint after 1. |
| **M06** | Async/await flow bug | Timing-dependent, requires execution model | 1. Trace async flow. 2. Identify race/missing await. 3. Fix. 4. Timing test. |
| **M07** | Replace a dependency (library swap) | Multiple files, different API interface | 1. Map old usages. 2. Document new equivalents. 3. Replace per file. 4. Update deps. 5. Test. |
| **M08** | Test asserting wrong behavior | Test "passes" but checks wrong thing | 1. Understand intended behavior. 2. Identify wrong assertion. 3. Fix. 4. Verify. |
| **M09** | Environment-specific bug (local vs CI) | Env differences | 1. Compare envs. 2. Identify divergence. 3. Fix to be env-agnostic. 4. Test both. |
| **M10** | Configuration drift (missing config key) | Requires tracing config loading + usage | 1. Trace config loading. 2. Identify missing keys. 3. Fix. 4. Add validation. 5. Test. |
| **M11** | Flaky test (passes sometimes) | Non-deterministic | 1. Run 10x, collect pattern. 2. Identify source (time, random, ordering). 3. Fix isolation. 4. Verify. |
| **M12** | Security vulnerability (SQL injection, XSS) | Fix without breaking functionality | 1. Audit injection points. 2. Apply parameterized queries. 3. Test functionality. 4. Test injection blocked. |
| **M13** | Error handling gap (unhandled exception) | Requires call chain understanding | 1. Trace call chain. 2. Determine handling strategy. 3. Implement. 4. Test happy + error. |
| **M14** | Performance regression | Profiling or complexity reasoning | 1. Profile/analyze. 2. Identify bottleneck. 3. Optimize. 4. Benchmark. 5. Test correctness. |

### 3.3 Hard Cases (H01-H12) - Research + Conversation

| ID | Case | Why Hard | Approach |
|----|------|---------|----------|
| **H01** | Architectural refactor (monolith -> modular) | Touches every file. Design decisions needed. | Report: 2-3 decomposition strategies with tradeoffs. Author picks, agent executes in chunks. |
| **H02** | Emergent behavior bug (per-component OK, integration fails) | Can't unit test. Component interaction failure. | Report: map interactions, 2-3 hypotheses with test plans. Author validates, agent writes integration test. |
| **H03** | "Find and fix all bugs" (open-ended) | No specific target. Judgment required. | Report: audit, categorize (bugs vs smells vs style), rank by severity. Author triages, agent fixes approved items. |
| **H04** | Design feature from vague requirements | Multiple valid interpretations. | Report: structured spec, ambiguities identified, 2-3 design options. Author selects, agent implements via medium pipeline. |
| **H05** | Race condition in distributed system | Non-deterministic. State machine reasoning. | Report: model state transitions, identify race window, propose strategies. Author reviews model. |
| **H06** | Data migration with backward compatibility | Must transform without downtime. Old + new coexist. | Report: schema diff, migration strategies (dual-write, blue-green, flags), risk per strategy. Author picks. |
| **H07** | Third-party API breaking change | Upstream changed. Must update without breaking downstream. | Report: diff old vs new API, map usage points, propose adaptation layer vs direct migration. |
| **H08** | Performance at scale (100 users OK, 10K breaks) | Load modeling, architectural changes | Report: bottleneck analysis, scaling strategies (cache, queue, shard). Author prioritizes. |
| **H09** | Security audit (find all vulnerabilities) | Open-ended. Threat modeling. | Report: threat model, OWASP categorization, severity ratings, remediation plan. Author triages. |
| **H10** | Legacy modernization (no tests, no docs) | No safety net. Unknown consumers. | Report: dependency map, critical paths, test-first modernization strategy. Author approves phases. |
| **H11** | Cross-team dependency change | Requires coordination, not just code. | Report: downstream consumers, backward-compatible approach or migration plan. Author coordinates. |
| **H12** | "Works on my machine" - no repro | Cannot reproduce. Detective work needed. | Report: diagnostic steps, hypothesis tree. Author runs diagnostics, feeds results, agent narrows. |

---

## 4. The 10 Challenges

| # | Challenge | Description | Impact if Unaddressed |
|---|-----------|-------------|----------------------|
| **C01** | **Cross-boundary reasoning** | Fixes spanning Python-SQL, Python-API, Python-config. Agent treats all code as Python. | 100% failure rate on cross-boundary tasks (our current state) |
| **C02** | **Same-mistake retry loop** | Agent retries exact same approach after failure, gets same error 3 times. | Wasted tokens + time. User loses trust. |
| **C03** | **Hallucinated API knowledge** | Agent assumes wrong return types, nonexistent methods, outdated APIs. | Introduces new bugs while "fixing". |
| **C04** | **Context window pressure** | As difficulty increases, agent needs more files. Large repos exceed limits. | Agent loses relevant info mid-reasoning. |
| **C05** | **False confidence** | Debate agents approve broken fixes - they review text, not runtime. | Bad PRs opened. Human review is only safety net. |
| **C06** | **Issue ambiguity** | Vague issues lead to wrong assumptions. Agent can't ask mid-fix. | Agent "fixes" the wrong thing. |
| **C07** | **Multi-file coordination** | Change in file A requires changes in B, C, D. Missing one breaks system. | Partial fixes that compile but fail at runtime. |
| **C08** | **Test oracle problem** | For hard cases, no existing test to validate. Agent must write tests - but what tests? | Tautological tests that pass for wrong reasons. |
| **C09** | **Conversation state management** | In GitHub chat loop, agent must track multi-turn state, remember author guidance. | Conversation becomes confusing. Agent ignores prior guidance. |
| **C10** | **Progressive automation boundary** | Deciding when a pattern is stable enough to automate vs needing human judgment. | Premature automation encodes mistakes. Too-late wastes human time. |

---

## 5. Architecture Approaches

### Approach A: "Tiered Pipeline" (Minimal Extension)

Extend current Manager -> Junior Dev -> Tester with two additional tiers.

```
              MANAGER (classify)
             /       |        \
          EASY     MEDIUM      HARD
           |         |           |
       JuniorDev  Planner    Researcher
           |       + Step       |
        Tester     Executor   Post report
           |         |        + await author
          PR       Tester
                     |
                    PR
```

**New agents:** Planner (medium) + Researcher (hard). Additive, no refactor.
**Pros:** Minimal change. Easy pipeline unchanged.
**Cons:** Planner/Researcher are monolithic. No reuse. No conversation state machine.

### Approach B: "Modular Sub-Agents" (MASAI-inspired)

Each capability is a separate sub-agent. Orchestrator composes them by difficulty.

| Sub-Agent | Responsibility | Used In |
|-----------|---------------|---------|
| Classifier | Difficulty + template + plan sketch | All |
| Localizer | Find files, functions, lines. Tag boundaries. | All |
| Reproducer | Build repro script | Medium, Hard |
| Planner | Decompose into ordered steps | Medium, Hard |
| FixGenerator | Generate code patches | Easy, Medium |
| TestRunner | Execute tests, parse results (not LLM) | Easy, Medium |
| Reviewer | Adversarial review (different model for diversity) | Medium, Hard |
| Researcher | Deep analysis, produce reasoning report | Hard |
| Conversationalist | Parse author comments, update state | Medium (checkpoints), Hard (loop) |
| MemoryStore | Reflexion-style verbal memory (not LLM) | All |

**Composition:**
- **Easy**: Localizer -> FixGenerator -> TestRunner -> PR
- **Medium**: Localizer -> Reproducer -> Planner -> (FixGenerator -> TestRunner -> Reviewer) x N -> PR
- **Hard**: Localizer -> Reproducer -> Researcher -> post report -> Conversationalist loop -> eventually Medium pipeline

**Pros:** Maximum reuse. Each sub-agent testable independently. Matches MASAI research.
**Cons:** More complex orchestration. More code upfront.

### Approach C: "State Machine with Human Checkpoints" (Conversation-First)

Entire system is a state machine where every state can pause for human input.

```
  START -> CLASSIFY -> easy/medium/hard routing
                         |
  EASY path:    LOCALIZE -> FIX -> TEST -> PR
  MEDIUM path:  PLAN -> STEP_N -> TEST_STEP -> CHECKPOINT(opt) -> ... -> INTEGRATE -> PR
  HARD path:    RESEARCH -> REPORT_POSTED -> AUTHOR_RESPONDS -> (back to PLAN or more RESEARCH)

  Any failure:  -> RETRY (must use different strategy)
  3 failures:   -> ASK_AUTHOR (present options, await guidance)
  Author reply: -> Route to appropriate state based on parsed intent
```

**Key states:** CLASSIFY, EASY_*, MED_PLAN, MED_STEP_N, CHECKPOINT, HARD_RESEARCH, ASK_AUTHOR, AWAITING_AUTHOR, RETRY, PR, DONE, FAILED

**Pros:** Explicit state management. Every state can pause for human. Natural conversation flow. Testable.
**Cons:** State machine complexity. Must persist state across webhook events. Async state transitions.

---

## 6. Approach Evaluation Matrix

### 6.1 Performance on 38 Cases

| | A (Tiered) | B (Modular) | C (State Machine) |
|---|---|---|---|
| Easy (E01-E12) | 12/12 | 12/12 | 12/12 |
| Medium (M01-M14) | 8/14 | 12/14 | 13/14 |
| Hard (H01-H12) | 4/12 | 7/12 | 10/12 |
| **Total** | **24/38** | **31/38** | **35/38** |

### 6.2 Performance on 10 Challenges

| Challenge | A (Tiered) | B (Modular) | C (State Machine) |
|-----------|-----------|-----------|-----------|
| C01 Cross-boundary | Partial | Good (Localizer tags boundaries) | Good + checkpoint before boundary steps |
| C02 Same-mistake retry | Partial | Good (tracks strategies) | Best (RETRY state requires different strategy) |
| C03 Hallucinated APIs | Weak | Good (Reviewer cross-checks) | Good (same as B) |
| C04 Context pressure | Weak (monolithic) | Best (per-sub-agent context) | Good (per-state context) |
| C05 False confidence | Weak | Good (adversarial Reviewer) | Good (TEST mandatory before PR) |
| C06 Issue ambiguity | Weak (no ask mechanism) | Partial | Best (ASK_AUTHOR is first-class) |
| C07 Multi-file coordination | Weak | Good (Localizer maps all) | Good (STEP_N per file) |
| C08 Test oracle | Weak | Partial | Good (checkpoint: "does this test make sense?") |
| C09 Conversation state | Absent | Partial | Best (state machine IS conversation state) |
| C10 Progressive automation | Absent | Partial (memory) | Good (auto vs checkpoint threshold) |
| **Score** | 2 good, 5 partial | 6 good, 4 partial | 8 good, 2 partial |

### 6.3 Verdict

**Selected: Approach C (State Machine) with Approach B's sub-agent modularity.**

- State machine from C = orchestration layer (explicit, testable state transitions, human checkpoints, conversation persistence)
- Modular sub-agents from B = execution layer (reusable, independently testable, per-agent context)

---

## 7. Selected Architecture: Stateful Orchestrator + Modular Sub-Agents

### 7.1 System Diagram

```
  GITHUB LAYER (webhooks: issue.labeled, issue_comment.created)
         |
  STATE MACHINE ENGINE
  |  States: CLASSIFY, EASY_*, MED_*, HARD_*, RETRY, ASK_AUTHOR, PR, DONE
  |  State store: JSON in GitHub issue (hidden comment) or SQLite
  |  Transitions triggered by: sub-agent results OR author comments
         |
  SUB-AGENT POOL
  |  Classifier | Localizer | Reproducer | Planner
  |  FixGenerator | TestRunner | Reviewer | Researcher
  |  Conversationalist | MemoryStore
```

### 7.2 State Enum (Python)

```python
class IssueState(str, Enum):
    RECEIVED = "received"
    CLASSIFYING = "classifying"
    # Easy
    EASY_LOCALIZING = "easy_localizing"
    EASY_FIXING = "easy_fixing"
    EASY_TESTING = "easy_testing"
    # Medium
    MED_PLANNING = "med_planning"
    MED_STEP_EXECUTING = "med_step_executing"
    MED_STEP_TESTING = "med_step_testing"
    MED_CHECKPOINT = "med_checkpoint"
    MED_INTEGRATING = "med_integrating"
    # Hard
    HARD_RESEARCHING = "hard_researching"
    HARD_REPORT_POSTED = "hard_report_posted"
    HARD_AUTHOR_GUIDED = "hard_author_guided"
    # Common
    RETRYING = "retrying"
    ASKING_AUTHOR = "asking_author"
    AWAITING_AUTHOR = "awaiting_author"
    CREATING_PR = "creating_pr"
    DONE = "done"
    FAILED = "failed"
```

### 7.3 Key State Transitions

```python
TRANSITIONS = {
    "received":      {"on_label": "classifying"},
    "classifying":   {"easy": "easy_localizing", "medium": "med_planning", "hard": "hard_researching", "skip": "done"},
    # Easy
    "easy_localizing": {"found": "easy_fixing", "not_found": "asking_author"},
    "easy_fixing":     {"fixed": "easy_testing", "failed": "retrying"},
    "easy_testing":    {"passed": "creating_pr", "failed": "retrying"},
    # Medium
    "med_planning":       {"planned": "med_step_executing", "too_hard": "hard_researching"},
    "med_step_executing": {"done": "med_step_testing", "failed": "retrying"},
    "med_step_testing":   {"more_steps": "med_step_executing", "last_step": "med_integrating", "failed": "retrying"},
    "med_checkpoint":     {"ok": "med_step_executing", "redirect": "med_planning"},
    "med_integrating":    {"passed": "creating_pr", "failed": "retrying"},
    # Hard
    "hard_researching":    {"ready": "hard_report_posted"},
    "hard_report_posted":  {"author_responds": "hard_author_guided"},
    "hard_author_guided":  {"try_fix": "med_planning", "more_research": "hard_researching", "manual": "done"},
    # Common
    "retrying":        {"retry_ok": "<back to source>", "exhausted": "asking_author"},
    "asking_author":   {"posted": "awaiting_author"},
    "awaiting_author": {"direction": "<route based on intent>", "give_up": "failed"},
    "creating_pr":     {"created": "done"},
}
```

### 7.4 Sub-Agent Specs

| Sub-Agent | Input | Output | Model |
|-----------|-------|--------|-------|
| **Classifier** | Issue + file contents | difficulty, confidence, template_id, plan_sketch | GPT-4o |
| **Localizer** | Issue + codebase structure | files with relevance scores + boundary tags | GPT-4o |
| **Reproducer** | Issue + affected code | repro_script, repro_result, is_reproducible | GPT-4o |
| **Planner** | Issue + localization | ordered steps with checkpoint flags | GPT-4o |
| **FixGenerator** | Step desc + code context | LineEdits + strategy description | GPT-4o |
| **TestRunner** | Fix diff + test files | passed/failed + output (subprocess, not LLM) | N/A |
| **Reviewer** | Diff + test results + issue | approved/rejected + concerns | Claude 3.5 (diversity) |
| **Researcher** | Issue + full context + localization | analysis, hypotheses, approaches, questions | GPT-4o (high temp) |
| **Conversationalist** | Author comment + history + state | intent (approve/redirect/clarify/abort) + guidance | GPT-4o |
| **MemoryStore** | Issue outcome + conversation | reflections, patterns, rules | N/A (storage) |

### 7.5 GitHub Comment Format

**State is embedded as hidden HTML comment:**

```markdown
<!-- glassbox-state: {"state":"med_step_executing","step":2,"retries":0} -->

### Step 2 of 4: Update SQL queries

**What I'm doing:** Replacing raw `0.85` in SQL with f-string interpolation.

**Changes:**
- `trust_db.py:15` - `DEFAULT 0.85` -> `DEFAULT {DEFAULT_TRUST}`
- `trust_db.py:28` - `VALUES (?, 0.85)` -> `VALUES (?, {DEFAULT_TRUST})`

**Test result:** 169/169 pass.

Moving to Step 3.

---
<sub>Step 2/4 | Retries: 0/3 | Confidence: 0.88</sub>
```

**On failure (presenting options):**

```markdown
<!-- glassbox-state: {"state":"asking_author","retries":2} -->

### I'm stuck on Step 2

**Tried:**
1. Direct replacement - broke SQLite (Python var in SQL string)
2. F-string interpolation - works for VALUES, breaks CREATE TABLE

**Options:**
**A)** Keep `0.85` in CREATE TABLE, extract only in Python (linked by convention)
**B)** Migration script reads constant from Python, updates schema (single source of truth)
**C)** Remove DEFAULT from schema, always pass value explicitly

@author - which direction? Or do you see another approach?

---
<sub>Asking author | Retries: 2/3 | Strategies tried: 2</sub>
```

### 7.6 Progressive Automation Engine

For each resolved issue, the system records:
- `difficulty_classified` vs `difficulty_actual`
- `author_guidance` (list of guidance comments)
- `resolution_path` (states traversed)
- `strategies_that_worked`

**Automation rules:**
- Same guidance pattern 3+ times -> propose encoding as a rule
- Medium issues that always pass without checkpoints -> downgrade checkpoint to optional
- Hard issues that always get same author direction -> propose upgrade to medium (auto-apply direction)

**Example:** "Author always says 'keep SQL literals as-is'" x4 -> new rule: HC5 (Embedded DSL) - never replace literals in SQL/regex/config strings.

---

## 8. How Each Case Is Handled (Summary)

### Easy (E01-E12)
Path: `CLASSIFY -> EASY_LOCALIZE -> EASY_FIX -> EASY_TEST -> PR`
No human. Template-driven. If fails 3x, ASK_AUTHOR.

### Medium (M01-M14)

| Case | Key Step | Checkpoint? |
|------|----------|-------------|
| M01 cross-boundary | Classify Python vs DSL occurrences | After classification |
| M02 multi-file rename | Build reference graph first | No (test after each file) |
| M03 API type mismatch | Research actual return type | After type research |
| M04 new endpoint | Design API first | After API design |
| M05 schema migration | Design schema change | After schema design |
| M06 async bug | Trace async flow | After root cause ID |
| M07 dependency swap | Map old -> new API equivalents | After mapping |
| M08 wrong test | Understand intended behavior | After behavior clarification |
| M09 env-specific | Identify env divergence | After divergence found |
| M10 config drift | Trace config loading | No |
| M11 flaky test | Identify non-determinism source | After source identified |
| M12 security fix | Audit all injection points | After audit |
| M13 error handling | Determine handling strategy | After strategy decision |
| M14 performance | Identify bottleneck | After bottleneck + approach |

### Hard (H01-H12)
All produce a research report, then enter conversational loop. Author directs next steps.

---

## 9. Short-Term Plan (Next 7 Days)

### Day 1-2: Foundation

- [ ] **Add difficulty field to Classifier output** - enhance `TriageResult` to include `difficulty: easy|medium|hard` with classification logic based on signals in section 2.2
- [ ] **Add 10 medium bug specs to eval catalog** - `evals/catalog.py` gets MEDIUM list (M01-M10 adapted to our codebase: cross-boundary constant, multi-file rename, etc.)
- [ ] **State enum + state store** - `src/glassbox_agent/core/state.py` with `IssueState` enum and JSON-based state persistence (SQLite or hidden GitHub comment)

### Day 3-4: Medium Pipeline Skeleton

- [ ] **Planner sub-agent** - `src/glassbox_agent/agents/planner.py` that decomposes an issue into ordered steps. Input: issue + localization. Output: list of steps with checkpoint flags.
- [ ] **Step executor loop** - modify orchestrator (or new `src/glassbox_agent/core/state_machine.py`) to execute steps sequentially, running tests after each step
- [ ] **Checkpoint mechanism** - bot posts "checkpoint" comment with current state + asks author. Webhook handler detects author reply and resumes.

### Day 5-6: Conversational Loop

- [ ] **Comment parser (Conversationalist)** - `src/glassbox_agent/agents/conversationalist.py` that takes author comment + current state and outputs intent + guidance
- [ ] **Webhook handler for `issue_comment.created`** - in GitHub App, detect when author replies to a checkpoint or ASK_AUTHOR state, parse, and resume state machine
- [ ] **"I'm stuck" flow** - when retries exhausted, format options clearly and post to issue, await author

### Day 7: Integration + Eval

- [ ] **End-to-end test with M01** (cross-boundary constant extraction) running through full medium pipeline
- [ ] **Run easy eval suite** to verify no regressions
- [ ] **Document learnings** - update this architecture doc with what worked and what needs adjustment

### Deliverables by Day 7:
1. Difficulty classifier (easy/medium/hard) integrated into Manager
2. State machine with state persistence
3. Planner agent that decomposes medium issues
4. Step-by-step execution with tests after each step
5. Basic conversational loop (bot posts options on failure, parses author reply)
6. 10 medium eval specs
7. One end-to-end medium case working

---

## 10. Long-Term Plan (8 weeks)

### Week 2-3: Harden Medium Pipeline
- Reproducer sub-agent (build repro script before fixing)
- Reviewer sub-agent using Claude (different model for diversity, adversarial)
- Boundary detection in Localizer (tag Python-SQL, Python-API crossings)
- Run all 10 medium evals, measure pass rate

### Week 4-5: Hard Pipeline
- Researcher sub-agent (deep analysis, structured report output)
- Research report template and GitHub comment formatting
- Hard-to-medium transition (author gives direction, system treats as medium)
- 5 hard eval specs added to catalog
- End-to-end hard case: report -> author reply -> fix

### Week 6-7: Progressive Automation
- Pattern tracker (record outcomes, guidance, resolution paths)
- Rule extraction from repeated guidance patterns
- Checkpoint auto-skip for patterns that always pass
- Hard-to-medium auto-promotion for recurring patterns
- Memory store integration (Reflexion-style reflections persisted across issues)

### Week 8: Polish + Metrics
- Dashboard: difficulty distribution, pass rate by difficulty, conversation turn count
- Cost tracking per difficulty tier
- Documentation and blog post on the architecture
- Publish medium + hard eval results

### Success Metrics

| Metric | Current | Week 4 Target | Week 8 Target |
|--------|---------|---------------|---------------|
| Easy pass rate | 50% (2/4 real) | 90% (eval suite) | 95% |
| Medium pass rate (autonomous) | 0% | 40% | 60% |
| Medium pass rate (with 1 checkpoint) | 0% | 60% | 85% |
| Hard issues with useful research report | 0% | N/A | 70% |
| Hard issues eventually resolved via conversation | 0% | N/A | 50% |
| Avg conversation turns for medium | N/A | 3 | 1.5 |
| Patterns auto-encoded from guidance | 0 | 0 | 5+ |

---

## 11. Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| State machine over ad-hoc flow | Explicit, testable, persistable. Every state can pause for human. | Tiered pipeline (simpler but no conversation support) |
| Modular sub-agents over monolithic | Reusable, independently testable, per-agent context. Matches MASAI research. | Single agent with different prompts (simpler but less reusable) |
| Hard = research report, not code | No agent solves hard problems autonomously (Devin confirms). Better to produce useful reasoning than broken code. | Attempt fix anyway (leads to false confidence + bad PRs) |
| Hidden HTML comment for state | Works with GitHub API. No external state store needed initially. | SQLite (more queryable but requires separate infra) |
| Different model for Reviewer | Same model = same blind spots (our debate failure analysis confirms). Claude vs GPT catches different errors. | Same model with different temperature (cheaper but less diverse) |
| Checkpoint = optional for medium | Author can enable/disable per-issue. Default: checkpoint after first step of novel pattern. | Always checkpoint (slower) or never (riskier) |
| Progressive automation from conversation | The human-agent loop IS the training data. Every conversation teaches the system. | Manual rule creation (slower, misses patterns) |

---

## 12. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| State machine becomes too complex | Medium | High | Keep states minimal. Add new states only when needed. Test transitions exhaustively. |
| Author never responds to checkpoints | High | Medium | Timeout after 24h. Post reminder. After 48h, mark as stale. |
| Conversationalist misparses author intent | Medium | Medium | Always confirm parsed intent before acting. "I understood you want X - proceeding." |
| Medium pipeline is slower than easy for simple cases | Low | Medium | Classifier must be accurate. Threshold tuning. If medium pipeline finishes in 1 step, it's working. |
| Cost explosion for hard cases (many LLM calls) | Medium | High | Budget per issue. Hard pipeline uses single researcher call, not iterative. Conversation turns are cheap (parsing, not generation). |
| Progressive automation encodes wrong patterns | Low | High | Require 5+ occurrences (not 3) before auto-encoding. Human review of proposed rules. |

---

## 13. References

| Source | Key Takeaway |
|--------|-------------|
| Devin 2025 Performance Review | Junior execution at scale. Fails on ambiguity. Start fresh > iterate. |
| Devin Agents 101 | Checkpoints for large tasks. Teach agent to verify. Cut losses early. |
| Rovo Dev CLI | #1 SWE-bench. Adaptive memory. Ecosystem integration. |
| SWE-agent (NeurIPS 2024) | ACI design reduces action space. Iterative explore-edit-test. |
| MASAI (Microsoft) | Modular sub-agents with tuned strategies per sub-task. |
| MarsCode (ByteDance) | Reproduction-first. Code knowledge graph. |
| Agentless (UIUC) | Hierarchical localization. Candidate + vote. Simple workflow beats complex agents sometimes. |
| arXiv:2411.10213 | Check patch completeness. Line-level localization > file-level. Reproduction correctness is critical. |
| Reflexion (NeurIPS 2023) | Verbal failure reflections improve future attempts. |
| Code Repair Exploration-Exploitation (NeurIPS 2024) | Branch out on retry, don't repeat same strategy. |
| OpenAI Deep Research | For hard problems, structured research output > attempted fix. |
| Our failure analysis (Issues #18, #19) | 100% failure on cross-boundary. Debate approves broken fixes. Same-mistake loops. |
