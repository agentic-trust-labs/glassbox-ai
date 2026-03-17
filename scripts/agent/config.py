"""GlassBox Agent - configuration and constants. Single source of truth."""

import os

AGENT_NAME = "GlassBox Agent"
AGENT_VERSION = "v0.3-beta"
AGENT_LABEL = f"{AGENT_NAME} {AGENT_VERSION}"

REPO = os.environ.get("GITHUB_REPOSITORY", "agentic-trust-labs/glassbox-ai")

MAX_RETRIES = 2

MODEL = "gpt-4o"
TEMPERATURE_ANALYZE = 0.3
TEMPERATURE_CODE = 0.1
TEMPERATURE_REVIEW = 0.3

SOURCE_FILES = [
    "src/glassbox/__init__.py",
    "src/glassbox/server.py",
    "src/glassbox/orchestrator.py",
    "src/glassbox/trust_db.py",
    "tests/test_glassbox.py",
]

REPO_MAP_TOKENS = 2048
REPO_FILE_EXTENSIONS = ["py"]

DEBATE_AGENTS = {
    "architect": "Check correctness. Will SQL strings, imports, or runtime behavior break? Grade every aspect, challenge, and edge case.",
    "pragmatist": "Is this the minimal change? Any over-engineering? Grade every aspect, challenge, and edge case.",
    "critic": "Find flaws. Are Python variables leaking into SQL/HTML/regex? Try to BREAK the fix. Grade every aspect, challenge, and edge case.",
}

REFLECTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reflections.json")

# Universal aspects that EVERY analysis must include.
# LLM adds issue-specific ones on top of these.
CORE_ASPECTS = [
    {"id": "A1", "emoji": "📖", "name": "Readability", "why": "Code must be clear to the next developer", "ideal": "Any engineer can understand the change in 30 seconds"},
    {"id": "A2", "emoji": "🧩", "name": "Modularity", "why": "Changes should be isolated, not tangled", "ideal": "Change touches minimal files, no ripple effects"},
    {"id": "A3", "emoji": "🔒", "name": "No hardcoding", "why": "Magic strings/numbers break on change", "ideal": "All values externalized to config or constants"},
    {"id": "A4", "emoji": "✅", "name": "Test coverage", "why": "Untested code is broken code you haven't found yet", "ideal": "Every changed path has a test (MRU: happy + error + edge)"},
    {"id": "A5", "emoji": "🔄", "name": "Backward compatibility", "why": "Existing users/tests must not break", "ideal": "All existing tests pass, no API changes"},
    {"id": "A6", "emoji": "🎯", "name": "Minimal diff", "why": "Smaller changes are easier to review and less risky", "ideal": "Only the lines that fix the issue are changed"},
    {"id": "A7", "emoji": "🛡️", "name": "Error handling", "why": "Failures must be visible, not silent", "ideal": "Every error path logged/raised, no bare except"},
    {"id": "A8", "emoji": "🗄️", "name": "Cross-boundary safety", "why": "Python vars must not leak into SQL/HTML/regex", "ideal": "Embedded DSLs are treated as separate languages"},
    {"id": "A9", "emoji": "📦", "name": "Import hygiene", "why": "Unused/wrong imports cause runtime failures", "ideal": "Only used imports, correct module paths"},
    {"id": "A10", "emoji": "🔁", "name": "Idempotency", "why": "Operations must be safe to retry", "ideal": "Running the fix twice produces the same result"},
    {"id": "A11", "emoji": "📐", "name": "Type correctness", "why": "SDK objects are not dicts, strings are not ints", "ideal": "All types verified against actual API/SDK signatures"},
    {"id": "A12", "emoji": "📊", "name": "Marginal Return of Utility", "why": "Test count follows diminishing returns", "ideal": "T1 happy path + T2 input + T3 error + T4 boundary per function"},
]
