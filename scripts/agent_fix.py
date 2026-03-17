#!/usr/bin/env python3
"""GlassBox AI Agent v2 — reads a GitHub issue, generates a fix with tests, retries on failure."""

import json, os, subprocess, sys, traceback

from openai import OpenAI

MAX_RETRIES = 2
REPO = None
ISSUE = None
SOURCE_FILES = [
    "src/glassbox/__init__.py",
    "src/glassbox/server.py",
    "src/glassbox/orchestrator.py",
    "src/glassbox/trust_db.py",
    "tests/test_glassbox.py",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def sh(cmd):
    """Run shell command, return CompletedProcess."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def gh_api(endpoint, method="POST", data=None):
    """Call GitHub REST API via gh cli."""
    cmd = f"gh api {endpoint}"
    if method != "GET":
        cmd += f" -X {method}"
    if data:
        cmd += f" --input -"
        return subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            input=json.dumps(data),
        )
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def comment(msg):
    """Post a comment on the issue via GitHub API (no shell escaping issues)."""
    gh_api(f"repos/{REPO}/issues/{ISSUE}/comments", data={"body": msg})
    print(f"💬 Commented: {msg[:80]}...")


def read_sources():
    """Read all source files into a dict."""
    sources = {}
    for path in SOURCE_FILES:
        with open(path) as f:
            sources[path] = f.read()
    return sources


# ── Core Logic ───────────────────────────────────────────────────────────────

def call_openai(client, issue_title, issue_body, sources, prev_error=None):
    """Ask GPT-4o to generate a fix. Includes previous error context on retries."""
    retry_context = ""
    if prev_error:
        retry_context = f"""

⚠️ PREVIOUS ATTEMPT FAILED. Here is the error:
{prev_error}

Fix your previous fix. Make sure ALL occurrences are handled and the test passes."""

    prompt = f"""You are a senior Python developer fixing a GitHub issue for GlassBox AI.

Issue #{ISSUE}: {issue_title}
{issue_body}
{retry_context}

Current source files:
{json.dumps(sources, indent=2)}

Return ONLY valid JSON:
{{
  "changes": [
    {{
      "file": "path/to/file.py",
      "old": "exact string to replace",
      "new": "replacement string",
      "replace_all": false
    }}
  ],
  "test_code": "def test_N_description():\\n    ...a complete pytest function...",
  "summary": "one-line commit message"
}}

Rules:
- Minimal fix only.
- "old" must be an EXACT substring of the current file content.
- Set "replace_all": true ONLY if every occurrence is in the SAME language context.
- NEVER replace literals inside SQL strings, f-strings, or embedded DSLs with Python variables.
  Example: `DEFAULT 0.85` in SQL must stay as `DEFAULT 0.85`, not `DEFAULT MY_CONST`.
  Only replace Python-context usages (assignments, returns, function args).
- Use SEPARATE change entries for different contexts (one for Python, keep SQL untouched).
- Include ONE test function that verifies the fix works.
- The test MUST check ALL changed locations, not just one.
- Follow existing code style exactly.
- Do not change comments or docstrings unless the issue requires it."""

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def debate_fix(client, fix, issue_title, sources):
    """3 GlassBox agents review the proposed fix with resulting code. Returns (approved, summary, votes)."""
    # Build preview of what the code looks like AFTER applying the fix
    preview = {}
    for change in fix.get("changes", []):
        fpath = change["file"]
        content = sources.get(fpath, "")
        if change.get("replace_all"):
            content = content.replace(change["old"], change["new"])
        else:
            content = content.replace(change["old"], change["new"], 1)
        preview[fpath] = content

    reviewers = {
        "architect": "Check correctness. Will SQL strings, imports, or runtime behavior break?",
        "pragmatist": "Is this the minimal change? Any over-engineering or unnecessary changes?",
        "critic": "Find flaws. Are Python variables leaking into SQL strings or other embedded languages?",
    }
    votes = {}
    for name, instruction in reviewers.items():
        resp = client.chat.completions.create(
            model="gpt-4o", temperature=0.3,
            messages=[{"role": "user", "content": (
                f"You are @{name} reviewing a code fix.\n"
                f"Issue: {issue_title}\n"
                f"Resulting code after fix:\n{json.dumps(preview, indent=2)}\n\n"
                f"{instruction}\n\n"
                f'Respond JSON: {{"approve": true/false, "reason": "one line"}}'
            )}],
            response_format={"type": "json_object"},
        )
        vote = json.loads(resp.choices[0].message.content)
        votes[name] = vote
        print(f"  @{name}: {'✅' if vote['approve'] else '❌'} {vote['reason']}")
    approvals = sum(1 for v in votes.values() if v["approve"])
    summary = "\n".join(f"- **@{n}:** {'✅' if v['approve'] else '❌'} {v['reason']}" for n, v in votes.items())
    return approvals >= 2, summary, approvals


def apply_fix(fix, sources):
    """Apply code changes. Returns (success, error_msg)."""
    for change in fix.get("changes", []):
        fpath = change["file"]
        if fpath not in sources:
            return False, f"File `{fpath}` not found in source files."

        content = sources[fpath]
        if change["old"] not in content:
            return False, f"String not found in `{fpath}`:\n```\n{change['old']}\n```"

        count = 0 if change.get("replace_all", False) else 1
        if count == 0:
            content = content.replace(change["old"], change["new"])
        else:
            content = content.replace(change["old"], change["new"], 1)

        with open(fpath, "w") as f:
            f.write(content)
        sources[fpath] = content

    if fix.get("test_code"):
        with open("tests/test_glassbox.py", "a") as f:
            f.write("\n\n" + fix["test_code"] + "\n")
        with open("tests/test_glassbox.py") as f:
            sources["tests/test_glassbox.py"] = f.read()

    return True, None


def syntax_check():
    """Syntax + import check on all source modules. Catches SQL/Python boundary bugs."""
    for path in SOURCE_FILES:
        if path.startswith("tests/"):
            continue
        module = path.replace("/", ".").replace(".py", "").replace("src.", "")
        result = sh(f'PYTHONPATH=src python -c "import {module}"')
        if result.returncode != 0:
            err = result.stderr[-400:]
            return False, f"Import failed for `{path}`:\n```\n{err}\n```\nYour fix likely put a Python variable inside an SQL string or broke module-level code."
    return True, None


def run_tests():
    """Run pytest. Returns (ok, output)."""
    result = sh("python -m pytest tests/test_glassbox.py -v --tb=short")
    print(result.stdout)
    return result.returncode == 0, result.stdout


def create_pr(branch, summary):
    """Create PR via GitHub API. Returns PR URL."""
    body = (
        f"Closes #{ISSUE}\n\n"
        f"## Changes\n{summary}\n\n"
        f"## Generated by\n"
        f"🤖 **GlassBox AI Agent** — automated fix triggered by `agent` label.\n\n"
        f"## Tests\n"
        f"✅ All unit tests passing.\n"
        f"CI pipeline will verify integration tests and Docker build."
    )
    payload = {
        "title": f"fix: {summary}",
        "body": body,
        "head": branch,
        "base": "main",
    }
    # Write JSON to temp file to avoid stdin/shell escaping issues
    tmp = "/tmp/pr_payload.json"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    result = sh(f"gh api repos/{REPO}/pulls --input {tmp}")
    os.remove(tmp)
    print(f"PR API stdout: {result.stdout[:300]}")
    print(f"PR API stderr: {result.stderr[:300]}")
    try:
        pr = json.loads(result.stdout)
        url = pr.get("html_url", "")
        if url:
            return url
        return pr.get("url", "")
    except Exception as e:
        print(f"PR JSON parse error: {e}")
        return ""


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    global REPO, ISSUE
    ISSUE = sys.argv[1]
    REPO = os.environ.get("GITHUB_REPOSITORY", "glassbox-ai-labs/glassbox-ai")
    branch = f"agent/issue-{ISSUE}"

    # 1. Read issue
    result = sh(f"gh issue view {ISSUE} --repo {REPO} --json title,body")
    issue = json.loads(result.stdout)
    issue_title = issue["title"]
    issue_body = issue.get("body", "")
    print(f"Issue #{ISSUE}: {issue_title}")

    # 2. Comment: picked up
    comment("🤖 **Agent picked this up.** Analyzing the issue and generating a fix...")

    # 3. Setup
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    print(f"API key loaded: {len(api_key)} chars")
    client = OpenAI(api_key=api_key)

    # 4. Delete old branch if exists
    sh(f"git push origin --delete {branch} 2>/dev/null")
    sh(f"git branch -D {branch} 2>/dev/null")

    # 5. Retry loop
    prev_error = None
    for attempt in range(1, MAX_RETRIES + 2):  # attempts 1, 2, 3
        print(f"\n{'='*60}\nAttempt {attempt}/{MAX_RETRIES + 1}\n{'='*60}")

        # Reset to clean main
        sh("git checkout main")
        sh("git clean -fd")
        sh("git checkout -- .")
        sh(f"git branch -D {branch} 2>/dev/null")
        sh(f"git checkout -b {branch}")

        # Read fresh sources
        sources = read_sources()

        # Call OpenAI
        try:
            fix = call_openai(client, issue_title, issue_body, sources, prev_error)
        except Exception as e:
            comment(f"❌ **OpenAI API error (attempt {attempt}):** `{str(e)[:200]}`")
            if attempt > MAX_RETRIES:
                sys.exit(1)
            continue

        if not fix.get("changes"):
            comment("❌ **Agent couldn't generate changes.** Manual fix needed.")
            sys.exit(1)

        print(f"Fix: {fix['summary']}")

        # Debate the fix
        approved, debate_summary, n_approvals = debate_fix(client, fix, issue_title, sources)
        if not approved:
            prev_error = f"Debate rejected ({n_approvals}/3):\n{debate_summary}"
            comment(f"🗣️ **Debate rejected fix (attempt {attempt}, {n_approvals}/3):**\n{debate_summary}")
            if attempt > MAX_RETRIES:
                comment("❌ **Debate could not approve after all attempts.** Manual fix needed.")
                sys.exit(1)
            continue

        if attempt == 1:
            comment(f"🔧 **Fix generated:** {fix['summary']}\n\n🗣️ **Debate ({n_approvals}/3 approved):**\n{debate_summary}\n\nApplying and running tests...")
        else:
            comment(f"🔄 **Retry {attempt}:** {fix['summary']}\n\n🗣️ **Debate ({n_approvals}/3):**\n{debate_summary}")

        # Apply
        ok, err = apply_fix(fix, sources)
        if not ok:
            prev_error = f"Apply failed: {err}"
            print(f"Apply error: {err}")
            if attempt > MAX_RETRIES:
                comment(f"❌ **Fix failed after {attempt} attempts.** Could not apply changes.\n\n{err}")
                sys.exit(1)
            continue

        # Syntax check
        ok, err = syntax_check()
        if not ok:
            prev_error = f"Syntax error: {err}"
            print(f"Syntax error: {err}")
            if attempt > MAX_RETRIES:
                comment(f"❌ **SyntaxError after {attempt} attempts.**\n\n{err}")
                sys.exit(1)
            continue

        # Tests
        ok, output = run_tests()
        if not ok:
            last_lines = "\n".join(output.strip().split("\n")[-20:])
            prev_error = f"Tests failed:\n{last_lines}"
            print(f"Tests failed on attempt {attempt}")
            if attempt > MAX_RETRIES:
                comment(
                    f"❌ **Tests failed after {attempt} attempts.** Manual fix needed.\n\n"
                    f"```\n{last_lines}\n```"
                )
                sys.exit(1)
            continue

        # ✅ All passed!
        print(f"✅ All tests passed on attempt {attempt}")
        break

    # 6. Commit and push
    sh("git add -A")
    subprocess.run(
        ["git", "commit", "-m", f"fix: {fix['summary']} (agent-fix #{ISSUE})"],
        capture_output=True, text=True,
    )
    push = sh(f"git push origin {branch}")
    print(push.stderr)

    # 7. Create PR via API
    pr_url = create_pr(branch, fix["summary"])
    print(f"PR created: {pr_url}")
    if not pr_url:
        pr_url = f"https://github.com/{REPO}/compare/main...{branch}"
        comment(f"⚠️ PR auto-creation failed. Branch pushed. Create PR manually:\n{pr_url}")

    # 8. Final comment with diff
    diff_lines = ""
    for c in fix["changes"]:
        ra = "(all)" if c.get("replace_all") else ""
        diff_lines += f"**`{c['file']}`** {ra}\n```diff\n- {c['old']}\n+ {c['new']}\n```\n"
    comment(
        f"✅ **PR ready for review:** {pr_url}\n\n"
        f"**Summary:** {fix['summary']}\n\n"
        f"### Diff\n{diff_lines}\n"
        f"**Tests:** ✅ All passing | **Attempts:** {attempt}\n\n"
        f"Waiting for CI pipeline and maintainer approval."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        if REPO and ISSUE:
            comment(f"❌ **Agent crashed:** `{str(e)[:200]}`\n\nManual fix needed.")
        sys.exit(1)
