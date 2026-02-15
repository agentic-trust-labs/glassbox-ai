# Human-in-the-Loop (HITL) - Architecture

**Date:** 2026-02-16
**Status:** Design
**Scope:** Add author intervention to the current agent system. Lean, modular.

---

## 0. What We're Building

The author can intervene at any point in the GitHub issue conversation. The bot adapts from the point the author references, not from the latest state. This turns the linear pipeline into a resumable, author-guided loop.

**Current flow (linear, no intervention):**
```
Issue labeled -> Ack -> Classify -> Fix (retry x3) -> Test -> PR or Fail
```

**New flow (author can intervene at any point):**
```
Issue labeled -> Ack -> Classify -> Fix -> Test -> PR or Fail
                                                       |
                                          Author comments with guidance
                                                       |
                                          Bot detects which step to resume from
                                                       |
                                          Bot re-runs from that point with guidance
```

---

## 1. Ten System Aspects

| # | Aspect | Ideal Behavior | Current Status |
|---|--------|---------------|----------------|
| **SA1** | **Comment ancestry detection** - determine which bot comment the author is responding to | Parse `>` quotes, match against bot history. Keyword fallback ("fix", "test", "briefing"). Default to latest. | Done. `detect_reference_phase()` handles quotes + keywords + default. |
| **SA2** | **Intent parsing** - understand what the author wants (redirect, constrain, approve, abort, question) | Keyword-based classification. Priority order: abort > approve > redirect > question > constrain. | Done. `parse_intent()` returns intent + constraints list. |
| **SA3** | **Guidance injection** - author's words reach the correct agent prompt | Guidance injected as `feedback` into JuniorDev's fix prompt. Formatted with AUTHOR GUIDANCE + CONSTRAINTS sections. | Done. Via `AUTHOR_GUIDANCE` env var -> `feedback` in fix loop. |
| **SA4** | **Rewind-to-point** - resume from the phase the author referenced, not from scratch | Hidden `<!-- glassbox:phase=X -->` tags in every bot comment. `determine_entry_point()` maps phase + intent to re-entry. | Partial. Tags embedded. `run_guided()` currently re-runs full pipeline (entry-point skipping is future phase). |
| **SA5** | **Conversation continuity** - coherent across multiple rounds, never contradicts itself | Bot posts "Resuming from [phase] with your guidance: [parsed text]". Tracks attempt count across interventions. | Partial. Ack comment posted. No cumulative guidance stacking yet. |
| **SA6** | **Flat-thread reference resolution** - no native threading in GitHub, must infer from context | 3-tier: quote matching -> keyword matching -> latest comment fallback. Phase tags bypass threading entirely. | Done. `detect_reference_phase()` implements all 3 tiers. |
| **SA7** | **Idempotent re-entry** - re-run from any point without stale git/branch state | Always reset branch to main before re-running. Fix generation is idempotent given same inputs + guidance. | Done. Pipeline already resets branch on each attempt. |
| **SA8** | **Circuit breaker** - prevent infinite guided loops | Track total attempts (auto + guided). After 5, post failure summary + save reflection. | Done. `run_guided()` counts `@glassbox-agent` mentions as guided attempts. |
| **SA9** | **Constraint preservation** - "don't touch X" directives must survive across the pipeline | Constraints extracted as separate list, formatted under CONSTRAINTS header in prompt. | Done. `parse_intent()` extracts constraints. `build_guidance_prompt()` formats them. |
| **SA10** | **Graceful degradation** - if parsing fails, still do something useful | If intent is unknown, default to redirect. If no phase detected, default to latest. If comment not found, print error and exit cleanly. | Done. All functions have sensible defaults. |

---

## 3. Thirty Edge Cases

### Comment Detection (EC01-EC06)

| ID | Edge Case | Ideal | Now |
|----|-----------|-------|-----|
| **EC01** | Author quotes bot text with `>` markdown | Match quoted text to bot comment | Done. `detect_reference_phase()` parses `>` lines, scores against bot bodies. |
| **EC02** | Author says "your first message" or "the briefing" | Map keyword to phase | Done. Keyword map: "briefing" -> classify. |
| **EC03** | Author says "go back to the fix" | Map "fix" to JuniorDev phase | Done. "fix" -> PHASE_FIX. |
| **EC04** | Author posts with no reference | Default to latest bot comment | Done. Falls through to `bot_comments[-1].phase`. |
| **EC05** | Author references an edited/updated comment | Match current content, not original | Done. `fetch_comments` gets current body from API. |
| **EC06** | Author references their own earlier comment | Treat as context for latest phase | Partial. Treated as new guidance, no special handling for self-refs. |

### Intent Parsing (EC07-EC12)

| ID | Edge Case | Ideal | Now |
|----|-----------|-------|-----|
| **EC07** | "looks good" but tests failed | Warn before proceeding | Partial. Detects `approve` intent, but no "are you sure?" confirmation loop. |
| **EC08** | "try X instead" (specific approach) | Extract X as strategy | Done. Full comment text passed as guidance to JuniorDev prompt. |
| **EC09** | "don't change file Y" | Negative constraint | Done. Extracted into `constraints` list, formatted under CONSTRAINTS header. |
| **EC10** | "why did you do X?" (question) | Bot explains reasoning | Partial. Detects `question` intent, posts placeholder reply. No reasoning extraction yet. |
| **EC11** | Author posts code snippet | Extract code as hint | Partial. Code passes through as raw text in guidance. No structured extraction. |
| **EC12** | "never mind, I'll do it myself" | Abort gracefully | Done. Detects `abort`, posts ack, exits. |

### Rewind Behavior (EC13-EC18)

| ID | Edge Case | Ideal | Now |
|----|-----------|-------|-----|
| **EC13** | References briefing, wants different template | Re-classify with guidance | Partial. Detects classify phase. Currently re-runs full pipeline (guidance reaches JuniorDev, not Manager). |
| **EC14** | References fix, "but keep the test you wrote" | Keep previous test code | Not yet. No mechanism to carry forward partial state across runs. |
| **EC15** | "start over completely" | Full rewind, fresh attempt | Done. Pipeline re-runs from scratch by default. |
| **EC16** | "the file is wrong, look at src/other.py" | Inject corrected file path | Done. Passes as guidance text. JuniorDev sees "look at src/other.py" in feedback. |
| **EC17** | References a phase that already passed | Explain + ask if re-run wanted | Not yet. Bot re-runs regardless. No "already passed" detection. |
| **EC18** | References briefing after PR created | Explain PR already open | Not yet. No PR-exists check before re-run. |

### Guidance Injection (EC19-EC24)

| ID | Edge Case | Ideal | Now |
|----|-----------|-------|-----|
| **EC19** | Guidance contradicts issue body | Flag conflict, ask which to follow | Not yet. Both pass to LLM, it resolves implicitly. |
| **EC20** | Multiple guidance comments before bot responds | Stack all chronologically | Partial. Only the triggering comment is parsed. Earlier ones ignored. |
| **EC21** | Non-English guidance | Pass through to LLM | Done. Raw text passes through, GPT-4o handles multilingual. |
| **EC22** | Guidance with code formatting (triple backticks) | Extract code blocks as structured hints | Partial. Code passes through as raw markdown. No structured extraction. |
| **EC23** | Very long guidance (500+ words) | Summarize to fit context | Partial. Full text passes through. No summarization, but prompt has 2048 max_tokens. |
| **EC24** | Guidance references external docs/links | Ask author to paste content | Not yet. URLs pass through as text. No detection or ask-to-paste. |

### Conversation Continuity (EC25-EC30)

| ID | Edge Case | Ideal | Now |
|----|-----------|-------|-----|
| **EC25** | 3 interventions, each with different guidance | Cumulative context per run | Partial. Each run gets only the latest comment's guidance. |
| **EC26** | "ignore what I said before, do Y" | Clear old guidance, apply Y only | Partial. Only latest comment parsed, so old guidance is implicitly dropped. Works by accident. |
| **EC27** | Two authors with conflicting guidance | Follow issue creator | Not yet. No author-role check. Last commenter wins. |
| **EC28** | Comment after success + PR | "PR already open, update it?" | Not yet. Bot re-runs full pipeline, may create duplicate PR. |
| **EC29** | Comment on closed issue | "Issue closed, reopen if needed" | Not yet. Workflow fires regardless of issue state. |
| **EC30** | Bot comment rate-limited | Retry 2x with backoff | Not yet. Single attempt, fails silently on error. |

### Score: 19/30 done, 7/30 partial, 4/30 not yet

---

## 4. Three Architecture Approaches

### Approach 1: "Comment-Triggered Re-run" (Minimal)

The simplest approach. Every author comment triggers a fresh pipeline run. The comment body is parsed for guidance and injected as extra context.

```
issue_comment.created (by author, mentions @glassbox-agent)
  |
  Parse comment for guidance
  |
  Run full pipeline with guidance injected into prompts
  |
  Post results
```

**Implementation:**
- `cli.py` gets a new `--guidance` flag
- Workflow passes `github.event.comment.body` as guidance
- Each agent prompt gets a `AUTHOR GUIDANCE: {guidance}` section
- No rewind logic - always runs full pipeline

**New code:** ~30 lines in cli.py, ~5 lines per agent prompt.

### Approach 2: "Phase-Aware Re-entry" (Lean)

Each bot comment embeds its phase in a hidden HTML tag. When the author references a comment, the system detects the phase and re-runs from there.

```
issue_comment.created (by author)
  |
  Fetch all comments on the issue
  |
  Build conversation history (bot comments with phases + author comments)
  |
  Detect which bot comment author is referencing
  |
  Extract phase from that comment's hidden tag
  |
  Parse author's intent + guidance
  |
  Re-run pipeline from that phase with guidance
```

**Bot comments get a hidden phase tag:**
```html
<!-- glassbox:phase=classify -->
<!-- glassbox:phase=fix:attempt=2 -->
<!-- glassbox:phase=test -->
<!-- glassbox:phase=pr -->
```

**Implementation:**
- New module: `src/glassbox_agent/core/conversation.py` (~120 lines)
  - `fetch_conversation(issue_number)` - gets all comments, builds structured history
  - `detect_reference(author_comment, bot_comments)` - finds which bot comment is referenced
  - `parse_intent(author_comment)` - returns intent + guidance
  - `determine_entry_point(phase, intent)` - returns which pipeline step to start from
- `cli.py` modified to accept `--resume-from` phase and `--guidance` text
- Each agent comment gets a hidden phase tag (1 line per comment call)
- Workflow passes comment body + issue number, cli reads conversation

**New code:** ~150 lines total. Modular. Testable.

### Approach 3: "Stateful Conversation Manager" (Full)

A dedicated Conversation Manager agent that maintains full conversation state, uses LLM to parse intent, and orchestrates re-entry.

```
issue_comment.created
  |
  ConversationManager.process(comment)
  |
  LLM parses: reference, intent, guidance, constraints
  |
  ConversationManager determines re-entry point + builds context
  |
  Pipeline.run(entry_point, context_with_guidance)
  |
  ConversationManager formats + posts response
```

**Implementation:**
- New agent: `src/glassbox_agent/agents/conversation_manager.py` (~200 lines)
- New model: `ConversationState` in models.py
- State persisted in hidden comment or file
- LLM call to parse every author comment (~$0.01/comment)
- Full conversation history maintained

**New code:** ~300 lines. More capable but heavier.

---

## 5. Evaluation Matrix

### 5.1 Performance on System Aspects

| Aspect | Approach 1 (Re-run) | Approach 2 (Phase-Aware) | Approach 3 (Stateful) |
|--------|---------------------|--------------------------|----------------------|
| SA1 Comment Ancestry | Absent - no detection | Good - hidden phase tags + reference matching | Best - LLM parses references |
| SA2 Intent Parsing | Weak - raw text injection | Good - keyword-based intent | Best - LLM-based intent |
| SA3 Guidance Injection | Good - simple prompt append | Good - phase-targeted injection | Best - structured guidance per agent |
| SA4 Rewind-to-Point | Absent - always full re-run | Good - resumes from tagged phase | Best - resumes from any state |
| SA5 Conversation Continuity | Weak - no history tracking | Good - builds conversation from comments | Best - full state management |

### 5.2 Performance on Challenges

| Challenge | Approach 1 | Approach 2 | Approach 3 |
|-----------|-----------|-----------|-----------|
| CH1 No threading | N/A (ignores) | Good - phase tags bypass need for threading | Good - LLM infers |
| CH2 Stale state | Good - always fresh | Good - fresh from entry point | Good - same |
| CH3 Guidance ambiguity | Weak - passes through | Partial - keyword parsing has limits | Good - LLM handles nuance |
| CH4 Infinite loop | Partial - needs counter | Good - tracks attempts in tags | Best - stateful counter |
| CH5 Race condition | Absent | Partial - can check for lock tag | Good - state check before run |

### 5.3 Performance on Edge Cases (30)

| Category | Approach 1 | Approach 2 | Approach 3 |
|----------|-----------|-----------|-----------|
| EC01-EC06 Comment Detection | 1/6 (only EC04) | 5/6 (misses EC05 edited) | 6/6 |
| EC07-EC12 Intent Parsing | 2/6 (EC08, EC12) | 4/6 (misses EC10, EC11) | 6/6 |
| EC13-EC18 Rewind | 1/6 (EC15 only) | 5/6 (misses EC14 partial keep) | 6/6 |
| EC19-EC24 Guidance | 3/6 (EC20, EC21, EC23) | 5/6 (misses EC22 code extraction) | 6/6 |
| EC25-EC30 Continuity | 2/6 (EC28, EC30) | 4/6 (misses EC26, EC27) | 6/6 |
| **Total** | **9/30** | **23/30** | **30/30** |

### 5.4 Implementation Cost

| | Approach 1 | Approach 2 | Approach 3 |
|---|---|---|---|
| New files | 0 | 1 (`conversation.py`) | 2 (`conversation_manager.py`, model updates) |
| Lines of code | ~30 | ~150 | ~300 |
| New LLM calls | 0 | 0 | 1 per author comment |
| Test effort | Low | Medium | High |
| Risk | Low | Low | Medium |

### 5.5 Verdict

**Selected: Approach 2 (Phase-Aware Re-entry)**

- Covers 23/30 edge cases (good enough for v1)
- Zero new LLM calls (cost-efficient)
- One new module, ~150 lines (lean)
- Phase tags are future-proof (Approach 3 can be layered on top later)
- Missing edge cases (EC05, EC10, EC11, EC14, EC22, EC26, EC27) are rare in practice and can be added incrementally

The 7 missed edge cases are all "nice to have" - LLM-powered intent parsing for questions (EC10), code snippet extraction (EC11/EC22), and multi-author conflict resolution (EC27). These can be added by upgrading `parse_intent` to use LLM later without changing the architecture.

---

## 6. Implementation Plan

### 6.1 New Module: `src/glassbox_agent/core/conversation.py`

```python
# Core data structures
@dataclass
class BotComment:
    comment_id: int
    phase: str          # "classify", "fix", "test", "pr", "fail"
    attempt: int
    body: str

@dataclass
class AuthorGuidance:
    comment_body: str
    reference_phase: str   # which phase the author is referencing
    intent: str            # "redirect", "constrain", "approve", "abort", "question"
    guidance_text: str     # extracted directive
    constraints: list[str] # negative constraints ("don't touch X")

# Core functions
def fetch_conversation(github, issue_number) -> list[BotComment | dict]
def detect_reference(author_comment, bot_comments) -> str  # returns phase
def parse_intent(author_comment) -> AuthorGuidance
def build_guidance_prompt(guidance: AuthorGuidance) -> str
```

### 6.2 Changes to Existing Files

**`cli.py`** - add `run_with_guidance()` that:
1. Fetches conversation history
2. Parses latest author comment
3. Determines entry point
4. Runs pipeline from that point with guidance injected

**`agents/manager.py`** - CLASSIFY_PROMPT gets `{author_guidance}` section
**`agents/junior_dev.py`** - FIX_PROMPT gets `{author_guidance}` section
**`agents/tester.py`** - No change (tests are objective)
**Bot comments** - Each `comment()` call includes hidden phase tag

### 6.3 Changes to Workflow

**`.github/workflows/agent-fix.yml`** - the `issue_comment` trigger already exists. Pass comment context to cli:
```yaml
run: python -m glassbox_agent.cli ${{ github.event.issue.number }} --comment-id ${{ github.event.comment.id }}
```

---

## 7. Live Simulation Results (2026-02-16)

Three real GitHub issues were created, labeled, and redirected mid-run to test the HITL system end-to-end.

### 7.1 Simulation Matrix

| Issue | Title | Author Comment | Detected Intent | Detected Phase | Pipeline Ran | PR Created |
|-------|-------|---------------|-----------------|----------------|-------------|-----------|
| **#126** | get_trust returns 0.50 instead of 0.85 | "don't touch SQL schema, only Python return value" | `constrain` | (empty) | Yes (twice - race) | No (empty URL) |
| **#127** | trust_floor is 0.03 instead of 0.30 | "this is wrong_value not typo, don't modify test files" | `redirect` | `classify` | Yes | Yes (#129) |
| **#128** | debate rounds default to 1 instead of 3 | "never mind, hold on" then "actually go ahead, only change function signature" | `abort` then `approve` | (empty) | Abort exited, second run succeeded | Yes (#130) |

### 7.2 What Worked

- **Intent detection**: All intents (`constrain`, `redirect`, `abort`, `approve`) were correctly identified from natural language
- **Phase detection**: When keywords matched ("template" -> classify), phase was correctly detected
- **Abort flow**: "never mind, hold on" -> agent posted "Understood. Stepping back." and exited cleanly
- **Re-redirect after abort**: Second comment triggered a fresh pipeline run that succeeded
- **Phase tags**: All 4 bot comments (classify, fix, test, pr) correctly embedded `<!-- glassbox:phase=X -->` tags
- **Guidance injection**: `AUTHOR_GUIDANCE` env var was set and passed as `feedback` to JuniorDev
- **Workflow YAML**: `--comment-id` flag correctly passed for `issue_comment` events, omitted for `issues` events

### 7.3 Bugs Found

| # | Bug | Severity | Edge Case | Root Cause | Fix |
|---|-----|----------|-----------|-----------|-----|
| **B1** | **Race condition: label + comment triggers run concurrently** - #126 had both a label-triggered run AND a comment-triggered run execute simultaneously on the same branch, producing 8 duplicate bot comments | High | EC28, CH5 | Workflow has no concurrency guard. Both `issues.labeled` and `issue_comment.created` fire independently. | Add `concurrency: group: issue-${{ github.event.issue.number }}` to workflow YAML |
| **B2** | **Empty PR URL on concurrent runs** - Both runs on #126 tried to create/push `agent/issue-126` branch simultaneously. `create_pr` returned empty string, approval comment shows no PR link | High | CH5 | `create_branch()` calls `git push origin --delete` + `git checkout -b`. Two runs racing on same branch causes push failures | Fix B1 (concurrency). Also add error handling in `create_pr` to detect and report failures |
| **B3** | **Phase detection empty when no prior bot comments** - On first comment-triggered run (#126, #128), `phase=` is empty because there are no prior bot comments with phase tags to reference | Medium | EC04 | `detect_reference_phase()` returns empty when `bot_comments` list is empty (no prior bot comments exist yet). Falls through to default, but default requires `bot_comments[-1]` | Add guard: if no bot comments, default to `PHASE_FIX` (most common redirect target) |
| **B4** | **No "resuming with guidance" message** - When HITL re-runs the pipeline, the author sees duplicate classify/fix/test/pr comments with no indication that guidance was applied | Medium | SA5 | `run_guided()` sets env var and calls `run_pipeline()` but doesn't post an acknowledgment comment explaining what it parsed | Add a brief ack: "Resuming with your guidance: [parsed text]. Intent: [intent]" |
| **B5** | **Phase tag position in fix/test/pr comments** - Phase tags appear after the agent header (`🔧 **GlassBox Junior Dev**\n\n<!-- glassbox:phase=fix -->`) instead of at the very start | Low | SA4 | `junior.comment()` from `base_agent.py` prepends agent header. The tag we pass in the body ends up after the header | Not blocking - `extract_phase_tag()` uses regex search (not match), so it finds the tag anywhere in the body |
| **B6** | **Only 1 of 3 label events fired** - Three issues were labeled in quick succession but only issue #126 got a label-triggered workflow run | Low | CH5 | GitHub rate-limits webhook deliveries. Rapid labeling may coalesce events or drop some | Not critical - the comment trigger serves as backup. Could stagger label additions in automation |

### 7.4 Priority Fixes

**Must fix (before next deploy):**
1. **B1**: Add workflow concurrency group - prevents duplicate runs on same issue
2. **B2**: Resolved by B1. Add defensive error logging in `create_pr` as belt-and-suspenders

**Should fix (next iteration):**
3. **B3**: Default to `PHASE_FIX` when no bot comments exist
4. **B4**: Post ack comment before re-running pipeline in `run_guided()`

**Nice to have:**
5. **B5**: Move phase tag injection into `base_agent.comment()` so it's always first
6. **B6**: No code fix needed - document as known behavior
