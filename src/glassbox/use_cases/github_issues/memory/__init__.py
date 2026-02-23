"""
GlassBox Use Case — GitHub Issues Memory
==========================================

Memory subsystem for the GitHub Issues use case.

Contains the Reflexion memory store: a simple JSON-based persistence layer
that saves verbal failure reflections so agents can learn from past mistakes.

Based on: Reflexion (NeurIPS 2023) — "Verbal failure reflections improve future attempts."

How it works:
    1. When a fix attempt fails, the pipeline records a Reflection:
       issue number, template, failure modes, and a natural language reflection.
    2. On the next issue, the classifier queries the memory store for similar past issues.
    3. Matching reflections are injected into the LLM prompt as "PAST REFLECTIONS".
    4. The LLM uses these to avoid repeating the same mistakes.

Example reflection:
    Issue #18 (wrong_value): "Failed because the value was inside a SQL string.
    The fix changed the Python variable but not the hardcoded SQL. Need to check
    if the target value appears in SQL strings too."

This memory is use-case-specific. A security-audit use case would have its own
memory (vulnerability patterns, false positive history, etc.).
"""
