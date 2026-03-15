"""Coder states: 3 new + 6 inherited = 9 total.
Flow: received -> classifying -> solving -> reviewing -> creating_pr -> done"""
from glassbox.core.state import BASE_TRANSITIONS

TRANSITIONS = {
    **BASE_TRANSITIONS,
    "classifying": {"ready": "solving", "skip": "done"},
    "solving": {"solved": "reviewing", "stuck": "asking_author", "failed": "retrying"},
    "reviewing": {"approved": "creating_pr", "rejected": "solving", "guidance": "solving"},
}

PAUSE_STATES = {"awaiting_author", "reviewing"}
