"""Conversation module - fetches issue comments, detects author references, parses intent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Phases that map to pipeline steps ──

PHASE_CLASSIFY = "classify"
PHASE_FIX = "fix"
PHASE_TEST = "test"
PHASE_PR = "pr"
PHASE_FAIL = "fail"

ALL_PHASES = (PHASE_CLASSIFY, PHASE_FIX, PHASE_TEST, PHASE_PR, PHASE_FAIL)

# ── Intent types ──

INTENT_REDIRECT = "redirect"
INTENT_CONSTRAIN = "constrain"
INTENT_APPROVE = "approve"
INTENT_ABORT = "abort"
INTENT_QUESTION = "question"
INTENT_UNKNOWN = "unknown"

# Hidden tag format embedded in bot comments
_PHASE_TAG_RE = re.compile(r"<!--\s*glassbox:phase=(\w+)(?::attempt=(\d+))?\s*-->")

# ── Keyword maps for reference detection ──

_PHASE_KEYWORDS: dict[str, list[str]] = {
    PHASE_CLASSIFY: ["manager", "briefing", "classify", "template", "aspect", "challenge", "edge case"],
    PHASE_FIX: ["fix", "junior dev", "juniordev", "edit", "code change", "strategy", "attempt"],
    PHASE_TEST: ["test", "tester", "passed", "failed", "tp1", "tp2", "tp3", "suite"],
    PHASE_PR: ["pr", "pull request", "merge", "branch", "approved"],
    PHASE_FAIL: ["fail", "manual fix", "exhausted"],
}

# ── Intent keyword maps ──

_INTENT_KEYWORDS: dict[str, list[str]] = {
    INTENT_REDIRECT: ["try", "instead", "approach", "different", "look at", "use", "switch", "change to"],
    INTENT_CONSTRAIN: ["don't", "do not", "avoid", "skip", "leave", "keep", "never", "not touch"],
    INTENT_APPROVE: ["looks good", "lgtm", "approve", "merge", "ship it", "go ahead", "proceed"],
    INTENT_ABORT: ["never mind", "i'll do it", "i will do it", "close", "cancel", "stop", "abort"],
    INTENT_QUESTION: ["why", "how come", "explain", "what if", "?"],
}


@dataclass
class BotComment:
    """A comment posted by the bot, tagged with its pipeline phase."""
    comment_id: int
    phase: str
    attempt: int = 1
    body: str = ""


@dataclass
class AuthorGuidance:
    """Parsed result of an author's intervention comment."""
    comment_id: int = 0
    comment_body: str = ""
    reference_phase: str = ""
    intent: str = INTENT_UNKNOWN
    guidance_text: str = ""
    constraints: list[str] = field(default_factory=list)


def make_phase_tag(phase: str, attempt: int = 1) -> str:
    """Generate the hidden HTML tag to embed in bot comments."""
    if attempt > 1:
        return f"<!-- glassbox:phase={phase}:attempt={attempt} -->"
    return f"<!-- glassbox:phase={phase} -->"


def extract_phase_tag(body: str) -> tuple[str, int]:
    """Extract phase and attempt from a bot comment body. Returns ("", 0) if none."""
    m = _PHASE_TAG_RE.search(body)
    if not m:
        return "", 0
    phase = m.group(1)
    attempt = int(m.group(2)) if m.group(2) else 1
    return phase, attempt


def build_bot_comments(comments: list[dict], bot_login: str = "glassbox-agent") -> list[BotComment]:
    """Filter and parse bot comments from a list of raw GitHub API comment dicts.

    Each dict should have keys: id, body, user.login (or user.login nested).
    """
    result = []
    for c in comments:
        login = ""
        if isinstance(c.get("user"), dict):
            login = c["user"].get("login", "")
        elif isinstance(c.get("author"), dict):
            login = c["author"].get("login", "")

        if login != bot_login:
            continue

        body = c.get("body", "")
        phase, attempt = extract_phase_tag(body)
        if not phase:
            # Fallback: infer phase from content keywords
            phase = _infer_phase_from_content(body)
        result.append(BotComment(
            comment_id=c.get("id", 0),
            phase=phase,
            attempt=attempt or 1,
            body=body,
        ))
    return result


def detect_reference_phase(author_body: str, bot_comments: list[BotComment]) -> str:
    """Determine which bot phase the author is referencing.

    Priority:
    1. Quoted text (lines starting with >) matched against bot comments
    2. Keyword matching ("the fix", "the test", "the briefing")
    3. Default: latest bot comment's phase
    """
    # 1. Check for quoted text
    quoted_lines = [line.lstrip("> ").strip() for line in author_body.split("\n") if line.strip().startswith(">")]
    if quoted_lines:
        quoted_text = " ".join(quoted_lines).lower()
        best_match = ""
        best_score = 0
        for bc in bot_comments:
            bc_lower = bc.body.lower()
            # Count how many quoted words appear in the bot comment
            score = sum(1 for word in quoted_text.split() if word in bc_lower)
            if score > best_score:
                best_score = score
                best_match = bc.phase
        if best_match and best_score >= 3:
            return best_match

    # 2. Keyword matching
    body_lower = author_body.lower()
    for phase, keywords in _PHASE_KEYWORDS.items():
        for kw in keywords:
            if kw in body_lower:
                return phase

    # 3. Default: latest bot comment
    if bot_comments:
        return bot_comments[-1].phase

    return PHASE_CLASSIFY


def parse_intent(author_body: str) -> tuple[str, list[str]]:
    """Parse author comment into intent + list of constraints.

    Returns (intent, constraints).
    """
    body_lower = author_body.lower()

    # Check for constraints (negative directives)
    constraints = []
    for line in author_body.split("\n"):
        line_lower = line.strip().lower()
        for kw in _INTENT_KEYWORDS[INTENT_CONSTRAIN]:
            if kw in line_lower:
                constraints.append(line.strip())
                break

    # Check intent by keyword priority (abort > approve > redirect > question)
    for kw in _INTENT_KEYWORDS[INTENT_ABORT]:
        if kw in body_lower:
            return INTENT_ABORT, constraints

    for kw in _INTENT_KEYWORDS[INTENT_APPROVE]:
        if kw in body_lower:
            return INTENT_APPROVE, constraints

    for kw in _INTENT_KEYWORDS[INTENT_REDIRECT]:
        if kw in body_lower:
            return INTENT_REDIRECT, constraints

    for kw in _INTENT_KEYWORDS[INTENT_QUESTION]:
        if kw in body_lower:
            return INTENT_QUESTION, constraints

    # If constraints found but no other intent, it's a constrain
    if constraints:
        return INTENT_CONSTRAIN, constraints

    # Default: redirect (author is giving guidance)
    return INTENT_REDIRECT, constraints


def extract_guidance_text(author_body: str) -> str:
    """Extract the actionable guidance from author comment.

    Strips quoted text (references) and keeps the author's own words.
    """
    lines = []
    for line in author_body.split("\n"):
        stripped = line.strip()
        # Skip quoted lines (references to bot)
        if stripped.startswith(">"):
            continue
        # Skip empty lines
        if not stripped:
            continue
        # Skip @mentions at start
        if stripped.startswith("@glassbox"):
            stripped = re.sub(r"^@\S+\s*", "", stripped).strip()
            if not stripped:
                continue
        lines.append(stripped)
    return "\n".join(lines)


def parse_author_comment(
    comment: dict,
    bot_comments: list[BotComment],
) -> AuthorGuidance:
    """Full parse of an author comment into structured guidance.

    Args:
        comment: Raw GitHub API comment dict with id, body keys.
        bot_comments: List of parsed bot comments for reference detection.

    Returns:
        AuthorGuidance with all fields populated.
    """
    body = comment.get("body", "")
    comment_id = comment.get("id", 0)

    reference_phase = detect_reference_phase(body, bot_comments)
    intent, constraints = parse_intent(body)
    guidance_text = extract_guidance_text(body)

    return AuthorGuidance(
        comment_id=comment_id,
        comment_body=body,
        reference_phase=reference_phase,
        intent=intent,
        guidance_text=guidance_text,
        constraints=constraints,
    )


def build_guidance_prompt(guidance: AuthorGuidance) -> str:
    """Format guidance into a prompt section for injection into agent prompts."""
    if not guidance.guidance_text and not guidance.constraints:
        return ""

    lines = ["AUTHOR GUIDANCE (follow this directive closely):"]
    if guidance.guidance_text:
        lines.append(guidance.guidance_text)
    if guidance.constraints:
        lines.append("")
        lines.append("CONSTRAINTS (do NOT violate these):")
        for c in guidance.constraints:
            lines.append(f"- {c}")
    return "\n".join(lines)


def determine_entry_point(reference_phase: str, intent: str) -> str:
    """Given the referenced phase and intent, decide where to re-enter the pipeline.

    Returns the phase to start from.
    """
    if intent == INTENT_ABORT:
        return ""  # empty = don't run
    if intent == INTENT_APPROVE:
        return PHASE_PR
    if intent == INTENT_QUESTION:
        return ""  # questions don't re-run, they get answered

    # For redirect/constrain, start from the referenced phase
    # But if referencing test or PR, start from fix (can't re-test without re-fixing)
    if reference_phase in (PHASE_TEST, PHASE_PR):
        return PHASE_FIX
    if reference_phase == PHASE_FAIL:
        return PHASE_FIX

    return reference_phase or PHASE_CLASSIFY


def _infer_phase_from_content(body: str) -> str:
    """Best-effort phase inference from comment content when no tag is present."""
    body_lower = body.lower()
    if "junior dev" in body_lower or "generating fix" in body_lower:
        return PHASE_FIX
    if "tester" in body_lower or "tp1" in body_lower or "tp2" in body_lower:
        return PHASE_TEST
    if "manager" in body_lower and ("approved" in body_lower or "pr" in body_lower):
        return PHASE_PR
    if "manager" in body_lower:
        return PHASE_CLASSIFY
    if "failed after" in body_lower or "manual fix" in body_lower:
        return PHASE_FAIL
    return ""
