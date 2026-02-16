"""Hardcoded aspects, challenges, and test patterns — frozen, never change per issue."""

from __future__ import annotations

HARD_ASPECTS = (
    {"id": "HA1", "name": "Correctness", "desc": "Fix addresses the bug described in the issue"},
    {"id": "HA2", "name": "Minimal diff", "desc": "Only lines that fix the issue are changed"},
    {"id": "HA3", "name": "Backward compat", "desc": "All existing tests still pass"},
    {"id": "HA4", "name": "Syntax validity", "desc": "Changed file parses without errors"},
    {"id": "HA5", "name": "Import hygiene", "desc": "No broken or unused imports introduced"},
)

HARD_CHALLENGES = (
    {"id": "HC1", "name": "String matching", "desc": "old text must exactly match source — copy-paste, never type from memory"},
    {"id": "HC2", "name": "Unrelated test breakage", "desc": "Fix ONLY what the issue describes — no refactoring"},
    {"id": "HC3", "name": "Over-engineering", "desc": "Fix might break a test you didn't know about"},
    {"id": "HC4", "name": "Stale state", "desc": "Bug might already be fixed by a prior run"},
    {"id": "HC5", "name": "Embedded DSL", "desc": "Numbers/strings inside SQL/regex/prompts are NOT Python"},
)

TEST_PATTERNS = (
    {"id": "TP1", "cmd": "python -c \"import {module}\"", "desc": "Syntax + imports OK"},
    {"id": "TP2", "cmd": "pytest tests/ -v --tb=short", "desc": "Full suite passes"},
    {"id": "TP3", "check": "diff_lines <= max_diff_lines", "desc": "Not over-engineered"},
)
