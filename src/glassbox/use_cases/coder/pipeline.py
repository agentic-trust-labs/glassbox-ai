"""Coder pipeline - maps states to agent functions.
The _solve agent contains a 25-line autonomous loop: litellm + subprocess.
System prompt loaded from file or built-in default."""
import json, logging, os, subprocess

log = logging.getLogger("glassbox.coder")

SYSTEM_PROMPT = (
    "You are an expert software engineering agent tasked with fixing a GitHub issue.\n"
    "You MUST fully resolve the issue. Do NOT stop until the fix is complete and verified.\n"
    "If you are not sure about the code, use bash to READ FILES and gather information — do NOT guess.\n"
    "Plan extensively before each function call. Reflect extensively on the results of each command.\n\n"
    "Workflow:\n"
    "1. Explore the repository structure to understand the codebase\n"
    "2. Find the relevant files using grep/find — read them carefully\n"
    "3. Create a minimal script to reproduce the bug and confirm the error\n"
    "4. Identify the root cause, then EDIT THE SOURCE FILES to fix it\n"
    "5. Re-run the reproduction script to confirm the bug is fixed\n"
    "6. Run targeted existing tests to check for regressions\n"
    "7. Think about edge cases and handle them\n"
    "8. When fully done, run: echo GLASSBOX_TASK_COMPLETE\n\n"
    "CRITICAL RULES:\n"
    "- You MUST actually EDIT source files. Exploring without editing is NOT solving.\n"
    "- After reading files, you must proceed to make the fix. Do not give up.\n"
    "- cd is NOT persistent between commands. Always prefix with cd /path/to/repo if needed.\n"
    "- For files >200 lines, use sed -n 'START,ENDp' to view specific ranges.\n"
    "- Do NOT modify test files. Only edit source/library code.\n"
    "- Make minimal, targeted changes. Avoid unnecessary refactoring.\n"
    "- If tests fail after your fix, analyze the failure and iterate — do NOT give up.\n"
    "- Pipe large outputs through head -100 to avoid truncation."
)

BASH_TOOL = [{"type": "function", "function": {
    "name": "bash", "description": (
        "Run a shell command. State is NOT persistent between calls (no cd). "
        "Output is truncated to 10000 chars. For large files use sed -n '1,100p'. "
        "Avoid commands with huge output; pipe through head -200 if uncertain."),
    "parameters": {"type": "object",
                   "properties": {"command": {"type": "string", "description": "The bash command to run"}},
                   "required": ["command"]}}}]

MAX_OUTPUT = 10000


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
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"Solve this issue in {cwd}:\n\n{ctx.config.get('task', '')}"}]
    log.info("[solve] Starting agent loop | model=%s step_limit=%d repo=%s",
             model, ctx.config.get("step_limit", 30), cwd)
    NUDGE_AT_STEP = 10  # if no file edit by this step, inject a reminder

    cost = 0.0
    step = 0
    done = False
    nudged = False
    for step in range(ctx.config.get("step_limit", 30)):
        # At step 10, check git diff — if nothing changed, the agent is only reading. Nudge it.
        if not nudged and step == NUDGE_AT_STEP:
            check = subprocess.run("git add -N . && git diff HEAD --stat", shell=True,
                                   cwd=cwd, capture_output=True, text=True)
            if not check.stdout.strip():
                nudge = ("You have spent 10 steps reading files. You now have enough context. "
                         "STOP reading. START editing source files now to fix the issue. "
                         "Use sed -i or write a Python script to apply your change. "
                         "Do NOT read any more files unless absolutely necessary.")
                messages.append({"role": "user", "content": nudge})
                log.warning("[solve] Nudge injected at step %d — no file edits yet", step + 1)
                nudged = True

        log.info("[solve] Step %d | messages=%d cost=$%.4f", step + 1, len(messages), cost)
        resp = completion(model=model, messages=messages, tools=BASH_TOOL,
                          tool_choice="required", max_tokens=16000)
        step_cost = getattr(resp, "_hidden_params", {}).get("response_cost", 0) or 0
        cost += step_cost
        msg = resp.choices[0].message
        messages.append(msg)
        if not getattr(msg, "tool_calls", None):
            log.warning("[solve] Step %d | no tool calls despite tool_choice=required — stopping", step + 1)
            break
        for tc in msg.tool_calls:
            cmd = json.loads(tc.function.arguments).get("command", "")
            log.info("[solve] Step %d | bash: %s", step + 1, cmd[:120])
            if "GLASSBOX_TASK_COMPLETE" in cmd:
                log.info("[solve] Task complete sentinel received")
                done = True
                break
            try:
                r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
                out = (r.stdout + r.stderr).strip()
                if len(out) > MAX_OUTPUT:
                    half = MAX_OUTPUT // 2
                    out = out[:half] + f"\n\n[...truncated {len(out) - MAX_OUTPUT} chars...]\n\n" + out[-half:]
                out = out or "(no output)"
                log.debug("[solve] Step %d | output (%d chars): %s", step + 1, len(out), out[:200])
            except subprocess.TimeoutExpired:
                out = "Error: command timed out after 120s. Try a less expensive command."
                log.warning("[solve] Step %d | TIMEOUT: %s", step + 1, cmd[:80])
            except Exception as e:
                out = f"Error: {e}"
                log.error("[solve] Step %d | ERROR: %s", step + 1, e)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
        if done:
            break
    # git diff only shows changes to tracked files; git diff HEAD also catches new files.
    # We add untracked files first so they appear in the diff.
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
