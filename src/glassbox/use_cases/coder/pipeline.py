"""Coder pipeline - maps states to agent functions.
The _solve agent runs an autonomous loop: litellm + subprocess + str_replace_editor.
Tools are vendored from Anthropic (MIT). Prompt borrowed from OpenAI's GPT-4.1 guide."""
import json, logging, os, subprocess

from glassbox.use_cases.coder.tools import TOOLS, handle_editor, MAX_RESPONSE_LEN

log = logging.getLogger("glassbox.coder")

# ──────────────────────────────────────────────────────────────────────────────
# System Prompt — borrowed from OpenAI's GPT-4.1 Prompting Guide (public)
# Source: https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide/
#
# The 3 magic ingredients proven to add ~20% on SWE-bench Verified:
#   1. Persistence  — "keep going until fully solved"
#   2. Tool-calling — "use tools to read files, do NOT guess"
#   3. Planning     — "plan before each call, reflect on outcomes"
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You will be tasked to fix an issue from an open-source repository. \
Your thinking should be thorough and so it's fine if it's very long. \
You can think step by step before and after each action you decide to take.

You MUST keep going until the issue is fully resolved. Only call the `complete` \
tool when you are sure the problem is solved. \
NEVER end your turn without having solved the problem.

If you are not sure about file content or codebase structure, use your tools to \
read files and gather information — do NOT guess or make up an answer.

You MUST plan extensively before each function call, and reflect extensively on \
the outcomes of the previous function calls. DO NOT do this entire process by \
making function calls only, as this can impair your ability to solve the problem \
and think insightfully.

# Workflow

## 1. Understand the Problem
Carefully read the issue and think hard about what is required before touching any code.

## 2. Investigate the Codebase
- Use bash (grep, find) to locate relevant files.
- Use str_replace_editor with command=view to read files. Do NOT use bash cat/sed for reading.
- Identify the root cause of the problem.

## 3. Reproduce the Bug
Create a minimal script to reproduce the error and execute it with bash to confirm the error.

## 4. Fix the Code
- Use str_replace_editor with command=str_replace to make targeted edits.
- Make small, incremental changes. Do NOT refactor unnecessarily.
- Do NOT modify test files. Only edit source/library code.

## 5. Verify the Fix
- Re-run your reproduction script to confirm the bug is fixed.
- Run existing tests with bash to check for regressions.
- Think about edge cases and handle them.

## 6. Complete
When the fix is verified and all tests pass, call the `complete` tool with a summary.

# Environment
- You already have everything you need to solve this problem in the repository folder, even without internet connection.
- THE PROBLEM CAN DEFINITELY BE SOLVED WITHOUT THE INTERNET.
- The package is already installed in the current Python environment. Do NOT run pip install, create virtual environments, or run setup.py. Just run tests directly with python3 or pytest.

# Rules
- If tests fail after your fix, analyze the failure and iterate — do NOT give up.
- The repository root is your working directory. Use absolute paths with str_replace_editor.
- Make minimal, targeted changes.
"""


def build_pipeline():
    return {"classifying": _classify, "solving": _solve, "reviewing": _review,
            "retrying": _retry, "asking_author": _ask_author, "creating_pr": _create_pr}




def _classify(ctx, **kw):
    log.info("[classify] Accepting issue for resolution")
    return {"event": "ready", "detail": "Issue accepted for resolution"}


def _solve(ctx, **kw):
    from litellm import completion
    model = ctx.config["model"]
    cwd = ctx.config.get("repo_root", os.getcwd())
    prompt_path = ctx.config.get("prompt_file", "")
    system = open(prompt_path).read() if prompt_path and os.path.isfile(prompt_path) else SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": (
            f"The repository is at: {cwd}\n\n"
            f"Please fix the following issue:\n\n{ctx.config.get('task', '')}"
        )},
    ]
    log.info("[solve] Starting agent loop | model=%s step_limit=%d repo=%s",
             model, ctx.config.get("step_limit", 30), cwd)

    cost = 0.0
    step = 0
    done = False
    for step in range(ctx.config.get("step_limit", 30)):
        log.info("[solve] Step %d | messages=%d cost=$%.4f", step + 1, len(messages), cost)
        # No tool_choice="required" — let the model stop naturally or call complete
        resp = completion(model=model, messages=messages, tools=TOOLS, max_tokens=16000)
        step_cost = getattr(resp, "_hidden_params", {}).get("response_cost", 0) or 0
        cost += step_cost
        msg = resp.choices[0].message
        messages.append(msg)

        if not getattr(msg, "tool_calls", None):
            log.info("[solve] Step %d | no tool calls — model finished", step + 1)
            break

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)

            if name == "complete":
                # Augment Code's CompleteTool pattern — clean exit mechanism
                log.info("[solve] complete tool called: %s", args.get("result", "")[:120])
                done = True
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                  "content": "Task marked as complete."})
                break

            elif name == "str_replace_editor":
                # Anthropic's str_replace_editor — vendored in tools.py (MIT)
                log.info("[solve] Step %d | editor %s: %s",
                         step + 1, args.get("command"), args.get("path", "")[:80])
                result = handle_editor(cwd=cwd, **args)
                log.info("[solve] Step %d | editor result: %s", step + 1, result[:120])
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            elif name == "bash":
                cmd = args.get("command", "")
                log.info("[solve] Step %d | bash: %s", step + 1, cmd[:120])
                try:
                    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                                       text=True, timeout=120)
                    out = (r.stdout + r.stderr).strip()
                    if len(out) > MAX_RESPONSE_LEN:
                        half = MAX_RESPONSE_LEN // 2
                        out = (out[:half]
                               + f"\n\n[...truncated {len(out) - MAX_RESPONSE_LEN} chars...]\n\n"
                               + out[-half:])
                    out = out or "(no output)"
                    log.debug("[solve] Step %d | output (%d chars): %s",
                              step + 1, len(out), out[:200])
                except subprocess.TimeoutExpired:
                    out = "Error: command timed out after 120s. Try a simpler command."
                    log.warning("[solve] Step %d | TIMEOUT: %s", step + 1, cmd[:80])
                except Exception as e:
                    out = f"Error: {e}"
                    log.error("[solve] Step %d | ERROR: %s", step + 1, e)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})

            else:
                log.warning("[solve] Step %d | unknown tool: %s", step + 1, name)
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                  "content": f"Error: unknown tool '{name}'"})

        if done:
            break

    # git diff HEAD catches both edited tracked files and new untracked files
    subprocess.run("git add -N .", shell=True, cwd=cwd, capture_output=True)
    diff = subprocess.run("git diff HEAD", shell=True, cwd=cwd, capture_output=True, text=True)
    patch = diff.stdout.strip()
    event = "solved" if patch else "stuck"
    log.info("[solve] Done | event=%s steps=%d cost=$%.4f patch=%d chars",
             event, step + 1, cost, len(patch))
    return {"event": event, "patch": patch, "messages": messages, "cost": cost,
            "detail": f"{'Patch' if patch else 'No changes'} in {step + 1} steps, ${cost:.4f}"}


def _review(ctx, **kw):
    resp = ctx.config.get("human_response", "approved").lower()
    patch = next((e["result"]["patch"] for e in reversed(ctx.history) if "patch" in e.get("result", {})), "")
    log.info("[review] human_response=%r patch=%d chars", resp[:40], len(patch))
    if any(w in resp for w in ("approv", "lgtm", "ship")):
        log.info("[review] Approved")
        return {"event": "approved", "patch": patch, "detail": "Human approved"}
    if "reject" in resp:
        log.info("[review] Rejected")
        return {"event": "rejected", "detail": f"Human rejected: {resp}"}
    log.info("[review] Guidance received — re-solving")
    ctx.config["task"] += f"\n\nHuman feedback: {resp}"
    return {"event": "guidance", "detail": f"Human guided: {resp[:80]}"}


def _retry(ctx, **kw):
    n = sum(1 for e in ctx.history if e.get("state") == "retrying")
    max_r = ctx.config.get("max_retries", 2)
    log.info("[retry] attempt=%d max=%d", n + 1, max_r)
    if n >= max_r:
        log.warning("[retry] Exhausted all %d retries", n)
        return {"event": "exhausted", "detail": f"Exhausted {n} retries"}
    prev = next((e["result"].get("detail", "") for e in reversed(ctx.history) if e.get("event") in ("failed", "stuck")), "")
    log.info("[retry] Injecting failure context: %s", prev[:100])
    ctx.config["task"] += f"\n\nPrevious attempt failed: {prev}"
    return {"event": "retry_ok", "detail": f"Retry {n + 1}"}


def _ask_author(ctx, **kw):
    fails = [e["result"].get("detail", "") for e in ctx.history if e.get("event") in ("failed", "stuck", "exhausted")]
    q = "I need guidance on this issue.\n" + "\n".join(f"- {f[:200]}" for f in fails[-3:])
    log.info("[ask_author] Posting question with %d failure summaries", len(fails))
    return {"event": "posted", "detail": "Asked human", "question": q}


def _create_pr(ctx, **kw):
    patch = next((e["result"]["patch"] for e in reversed(ctx.history) if "patch" in e.get("result", {})), "")
    log.info("[create_pr] Packaging patch (%d chars)", len(patch))
    return {"event": "created", "patch": patch, "detail": f"PR ready ({len(patch)} chars)"}
