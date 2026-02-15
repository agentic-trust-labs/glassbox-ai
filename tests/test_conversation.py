"""Tests for glassbox_agent.core.conversation — HITL comment parsing."""

import pytest
from glassbox_agent.core.conversation import (
    make_phase_tag, extract_phase_tag, build_bot_comments,
    detect_reference_phase, parse_intent, extract_guidance_text,
    parse_author_comment, build_guidance_prompt, determine_entry_point,
    BotComment, PHASE_CLASSIFY, PHASE_FIX, PHASE_TEST, PHASE_PR,
)


# ── make_phase_tag / extract_phase_tag ──

def test_phase_tag_roundtrip():
    tag = make_phase_tag("fix", attempt=2)
    phase, attempt = extract_phase_tag(f"{tag}\nsome body text")
    assert phase == "fix"
    assert attempt == 2


def test_phase_tag_default_attempt():
    tag = make_phase_tag("classify")
    phase, attempt = extract_phase_tag(tag)
    assert phase == "classify"
    assert attempt == 1


def test_extract_no_tag():
    assert extract_phase_tag("no tag here") == ("", 0)


# ── build_bot_comments ──

def test_build_bot_comments_filters_by_login():
    comments = [
        {"id": 1, "body": "<!-- glassbox:phase=classify -->", "user": {"login": "glassbox-agent"}},
        {"id": 2, "body": "human comment", "user": {"login": "sourabh"}},
        {"id": 3, "body": "<!-- glassbox:phase=fix:attempt=2 -->", "user": {"login": "glassbox-agent"}},
    ]
    bots = build_bot_comments(comments)
    assert len(bots) == 2
    assert bots[0].phase == "classify"
    assert bots[1].phase == "fix"
    assert bots[1].attempt == 2


# ── detect_reference_phase ──

def test_detect_reference_by_keyword():
    bots = [BotComment(1, "classify"), BotComment(2, "fix")]
    assert detect_reference_phase("the fix is wrong", bots) == "fix"
    assert detect_reference_phase("change the template", bots) == "classify"


def test_detect_reference_by_quote():
    bots = [BotComment(1, "classify", body="Manager picked up issue"),
            BotComment(2, "fix", body="Junior Dev generating fix for trust_db")]
    body = "> Junior Dev generating fix for trust_db\nthis is wrong"
    assert detect_reference_phase(body, bots) == "fix"


def test_detect_reference_defaults_to_latest():
    bots = [BotComment(1, "classify"), BotComment(2, "test")]
    assert detect_reference_phase("hello", bots) == "test"


# ── parse_intent ──

def test_intent_redirect():
    intent, _ = parse_intent("try a different approach instead")
    assert intent == "redirect"


def test_intent_constrain():
    intent, constraints = parse_intent("don't touch the SQL strings")
    assert intent == "constrain"
    assert len(constraints) == 1


def test_intent_approve():
    intent, _ = parse_intent("looks good, ship it")
    assert intent == "approve"


def test_intent_abort():
    intent, _ = parse_intent("never mind, I'll do it myself")
    assert intent == "abort"


# ── extract_guidance_text ──

def test_extract_strips_quotes_and_mentions():
    body = "> some quoted bot text\n@glassbox-agent try approach B\nuse f-strings"
    text = extract_guidance_text(body)
    assert "quoted bot text" not in text
    assert "try approach B" in text
    assert "use f-strings" in text


# ── parse_author_comment (integration) ──

def test_parse_author_comment_full():
    bots = [BotComment(1, "classify"), BotComment(2, "fix")]
    comment = {"id": 3, "body": "@glassbox-agent the fix should not touch SQL. Try using f-strings instead."}
    g = parse_author_comment(comment, bots)
    assert g.reference_phase == "fix"
    assert g.intent == "redirect"  # "Try" triggers redirect (higher priority than constrain)
    assert len(g.constraints) == 1  # "should not touch SQL" is still captured
    assert "f-strings" in g.guidance_text


# ── build_guidance_prompt ──

def test_guidance_prompt_empty():
    from glassbox_agent.core.conversation import AuthorGuidance
    g = AuthorGuidance()
    assert build_guidance_prompt(g) == ""


def test_guidance_prompt_with_text():
    from glassbox_agent.core.conversation import AuthorGuidance
    g = AuthorGuidance(guidance_text="use f-strings", constraints=["don't touch SQL"])
    prompt = build_guidance_prompt(g)
    assert "AUTHOR GUIDANCE" in prompt
    assert "f-strings" in prompt
    assert "CONSTRAINTS" in prompt


# ── determine_entry_point ──

def test_entry_point_redirect_fix():
    assert determine_entry_point("fix", "redirect") == "fix"


def test_entry_point_redirect_test_falls_back_to_fix():
    assert determine_entry_point("test", "redirect") == "fix"


def test_entry_point_abort_returns_empty():
    assert determine_entry_point("fix", "abort") == ""


def test_entry_point_approve_goes_to_pr():
    assert determine_entry_point("test", "approve") == "pr"
