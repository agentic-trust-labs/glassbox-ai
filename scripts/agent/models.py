"""GlassBox Agent v0.3-beta - Pydantic models for typed everything."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Aspect(BaseModel):
    id: str = Field(description="e.g. A1, A2")
    emoji: str = Field(description="e.g. 🗄️")
    name: str = Field(description="e.g. SQL-Python boundary")
    why: str = Field(description="Why this aspect matters")
    ideal: str = Field(description="How the ideal solution performs")


class Challenge(BaseModel):
    id: str = Field(description="e.g. C1, C2")
    name: str = Field(description="Short challenge name")
    risk: str = Field(description="Why this is a risk")
    mitigation: str = Field(description="How to mitigate")


class EdgeCase(BaseModel):
    id: str = Field(description="e.g. E1, E2")
    scenario: str = Field(description="Input or scenario description")
    expected: str = Field(description="Expected behavior")


class Analysis(BaseModel):
    aspects: list[Aspect] = Field(min_length=1, max_length=50)
    challenges: list[Challenge] = Field(min_length=1, max_length=50)
    edge_cases: list[EdgeCase] = Field(min_length=1, max_length=50)


class CodeChange(BaseModel):
    file: str = Field(description="Relative path to file")
    old: str = Field(description="Exact string to replace")
    new: str = Field(description="Replacement string")
    replace_all: bool = False


class NotChanged(BaseModel):
    file: str
    line_desc: str = Field(description="e.g. Line 7: DEFAULT 0.85 in SQL CREATE")
    reason: str = Field(description="Why it was intentionally left alone")


class Fix(BaseModel):
    changes: list[CodeChange]
    not_changed: list[NotChanged] = []
    test_code: str = Field(description="Complete pytest function")
    summary: str = Field(description="One-line commit message")
    strategy: str = Field(description="Brief description of the approach taken")


class Grade(BaseModel):
    id: str = Field(description="A1, C3, E7 etc.")
    item: str = Field(description="Name of the aspect/challenge/edge case")
    passed: bool
    remark: str


class DebateVote(BaseModel):
    agent: str = Field(description="architect, pragmatist, or critic")
    approve: bool
    reason: str
    grades: list[Grade] = Field(description="Grades for each A#, C#, E#")


class ReviewResult(BaseModel):
    approved: bool
    votes: list[DebateVote]
    aspect_score: str = Field(description="e.g. 5/5")
    challenge_score: str = Field(description="e.g. 4/4")
    edge_case_score: str = Field(description="e.g. 18/20")


class Reflection(BaseModel):
    issue_number: int
    issue_title: str
    failure_modes: list[str] = Field(description="e.g. ['F1', 'F5', 'F13']")
    reflection: str = Field(description="Verbal description of why it failed")
    edge_case_missed: str = Field(default="", description="The edge case that caught us")
