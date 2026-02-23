"""
GlassBox Core — The Kernel
===========================

This package is the heart of the platform. It contains ONLY:

    state.py    → State enum + transition rules. What states exist, how they connect.
    models.py   → Typed data contracts. What agents receive and return.
    engine.py   → The state machine loop. Step through states, call agents, log everything.

Design rules for this package:
    1. Core NEVER imports from agents/, tools/, or use_cases/.
       (The dependency arrow always points inward: use_cases → agents → core, never reverse.)
    2. Core has ZERO external dependencies beyond Python stdlib + dataclasses.
       (No OpenAI, no GitHub, no pydantic. Just pure Python.)
    3. Every file in core must stay under 200 lines.
       (If it grows beyond that, it's doing too much. Split it.)
    4. Core is the ONLY package protected by CODEOWNERS.
       (Changes here require owner approval. Everything else is open.)

Think of this as the Linux kernel: small, stable, well-tested.
Agents and tools are userland programs that run on top of it.
"""
