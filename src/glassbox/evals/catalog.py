"""Bug catalog - 10 easy bugs on the real codebase."""

from .bug_spec import BugSpec

EASY = [
    BugSpec(
        id="E01", difficulty="easy",
        file="src/glassbox/trust_db.py",
        title="[Bug] get_trust() returns 0.50 for unknown agents instead of 0.85",
        body="In trust_db.py, the fallback value for unknown agents is 0.50 but should be 0.85.\nExpected: `db.get_trust('unknown') == 0.85`",
        original="result[0] if result else 0.85",
        mutation="result[0] if result else 0.50",
    ),
    BugSpec(
        id="E02", difficulty="easy",
        file="src/glassbox/trust_db.py",
        title="[Bug] EMA learning rate is 1.0 instead of 0.1 - trust scores jump wildly",
        body="In update_trust(), the EMA factor is 1.0 instead of 0.1.\nThis makes scores jump to extremes on every update.",
        original="old_score + 0.1 * ((1.0",
        mutation="old_score + 1.0 * ((1.0",
    ),
    BugSpec(
        id="E03", difficulty="easy",
        file="src/glassbox/trust_db.py",
        title="[Bug] Trust floor is 0.03 instead of 0.30 - agents can drop to near-zero",
        body="In update_trust(), `max(0.3, ...)` should enforce floor at 0.30 but it's set to 0.03.",
        original="max(0.3, min(1.0,",
        mutation="max(0.03, min(1.0,",
    ),
    BugSpec(
        id="E04", difficulty="easy",
        file="src/glassbox/trust_db.py",
        title="[Bug] min/max swapped in trust update - scores always clamp to 0.3",
        body="In update_trust(), `max(0.3, min(1.0, ...))` is swapped.\nResult: scores always return 0.3.",
        original="max(0.3, min(1.0,",
        mutation="min(0.3, max(1.0,",
    ),
    BugSpec(
        id="E05", difficulty="easy",
        file="src/glassbox/trust_db.py",
        title="[Bug] get_all_scores() queries wrong table name 'trust_score'",
        body="get_all_scores() references `trust_score` (missing trailing 's').\nCauses sqlite3.OperationalError at runtime.",
        original="FROM trust_scores ORDER",
        mutation="FROM trust_score ORDER",
    ),
    BugSpec(
        id="E06", difficulty="easy",
        file="src/glassbox/orchestrator.py",
        title="[Bug] ROUND 1 instruction says 'use bullet points' instead of 'no bullet points'",
        body="ROUNDS[0] says 'use bullet points' but should say 'no bullet points'.\nAgents format responses wrong.",
        original="Be direct, no bullet points.",
        mutation="Be direct, use bullet points.",
    ),
    BugSpec(
        id="E07", difficulty="easy",
        file="src/glassbox/server.py",
        title="[Bug] ImportError: cannot import '__ver__' from glassbox",
        body="server.py imports `__ver__` but the correct attribute is `__version__`.\nCauses ImportError on startup.",
        original="from . import __version__",
        mutation="from . import __ver__",
    ),
    BugSpec(
        id="E08", difficulty="easy",
        file="src/glassbox/orchestrator.py",
        title="[Bug] Typo in critic model name: 'gpt-4o-mni' instead of 'gpt-4o-mini'",
        body="The critic agent config has model 'gpt-4o-mni' (typo).\nCauses OpenAI API NotFoundError.",
        original="gpt-4o-mini",
        mutation="gpt-4o-mni",
    ),
    BugSpec(
        id="E09", difficulty="easy",
        file="src/glassbox/trust_db.py",
        title="[Bug] Seed data inserts 'critics' instead of 'critic'",
        body="In _init_db(), the seed loop has 'critics' (extra s) instead of 'critic'.\nget_trust('critic') always returns the fallback value.",
        original='"critic"',
        mutation='"critics"',
    ),
    BugSpec(
        id="E10", difficulty="easy",
        file="src/glassbox/orchestrator.py",
        title="[Bug] KeyError: 'critic' missing from EMOJIS dict",
        body="EMOJIS dict has key 'critics' but code accesses 'critic'.\nCauses KeyError during debate formatting.",
        original='"critic": "\U0001f7e1"',
        mutation='"critics": "\U0001f7e1"',
    ),
]

CATALOG = EASY  # extend later: + MEDIUM + HARD
