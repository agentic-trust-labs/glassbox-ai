"""
GlassBox Use Case — GitHub Issues
=====================================

The flagship use case: automatically fix GitHub issues by routing them through
easy, medium, or hard pipelines based on difficulty classification.

This is the FIRST "app" on the GlassBox platform. It demonstrates the full
platform capability: state machine routing, agent composition, trust (reviewer),
human-in-the-loop (conversationalist), and audit logging.

Pipelines:
    EASY (fully automated):
        received → classifying → easy_localizing → easy_fixing → easy_testing → creating_pr → done
        Target: 90% success rate on single-file bug fixes.

    MEDIUM (orchestrated multi-step):
        received → classifying → med_planning → med_step_executing → med_step_testing →
        [med_checkpoint?] → ... → med_integrating → creating_pr → done
        Target: 60% auto, 85% with 1 human checkpoint.

    HARD (research report + conversation):
        received → classifying → hard_researching → hard_report_posted →
        hard_author_guided → [try_fix → med_planning | more_research | manual → done]
        Target: 70% eventually via conversation.

Activation:
    This use case is activated when:
        1. A GitHub issue is labeled (webhook fires).
        2. The CLI is called: python -m glassbox.cli <issue_number>
        3. The GitHub App webhook handler processes an issue event.

Folder contents:
    states.py    → EASY_*, MED_*, HARD_* states extending BaseState
    pipeline.py  → Agent wiring: which agent runs at which state
    settings.py  → Configuration (model names, temperatures, paths)
    agents/      → Empty escape hatch for future local agents
    tools/       → Empty escape hatch for future local tools
    templates/   → Bug pattern YAML files (typo_fix, wrong_value, etc.)
    memory/      → Reflexion memory store
"""

# Use case metadata — used by the CLI to discover and describe use cases.
USE_CASE_NAME = "github_issues"
USE_CASE_DESCRIPTION = "Fix GitHub issues automatically (easy/medium/hard routing)"
