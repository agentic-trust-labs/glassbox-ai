"""
GlassBox Tool — LLM Abstraction
==================================

CORE TOOL. Requires owner approval to modify.

Purpose:
    Provide a single, consistent interface for calling Large Language Models.
    Every agent that needs an LLM goes through this tool — no direct OpenAI/
    Anthropic imports in agent code.

Why a single LLM abstraction:
    1. Model swapping: Change the default model in ONE place, not in every agent.
    2. Cost tracking: Every LLM call goes through call_llm(), so we can add
       token counting, cost estimation, and rate limiting in one place.
    3. Provider flexibility: Today it's OpenAI. Tomorrow it might be Claude,
       Gemini, or a local model. Agents don't care — they call call_llm().
    4. Testing: In tests, you mock call_llm() once instead of mocking OpenAI
       client creation in every agent file.

Current implementation:
    Wraps the OpenAI Python SDK (openai>=1.0). Supports:
        - Any OpenAI model (gpt-4o, gpt-4o-mini, o1, etc.)
        - JSON mode (for structured agent responses)
        - Temperature control (per agent needs)

    Claude support is planned but not yet implemented. When added, the function
    signature stays the same — agents won't need to change.

Environment:
    Requires OPENAI_API_KEY environment variable to be set.
    For Claude: ANTHROPIC_API_KEY (future).
"""

from __future__ import annotations

import os
from typing import Any


def call_llm(
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.5,
    max_tokens: int = 4096,
    json_mode: bool = False,
) -> str:
    """
    Call an LLM and return the response text.

    This is the ONLY function that makes LLM API calls in the entire platform.
    All agents go through this. If you need to add logging, cost tracking,
    retries, or rate limiting, do it here.

    Args:
        model       → Model identifier (e.g., "gpt-4o", "gpt-4o-mini").
        messages    → List of message dicts: [{"role": "user", "content": "..."}].
                       Follows the OpenAI chat completions format.
        temperature → Sampling temperature. Lower = more deterministic.
                       Classification: 0.3. Code generation: 1.0. Review: 0.3.
        max_tokens  → Maximum response length. Default 4096 is generous for most agents.
        json_mode   → If True, the LLM is instructed to return valid JSON.
                       Most agents use this for structured output parsing.

    Returns:
        The LLM's response text as a string.

    Raises:
        openai.AuthenticationError: If OPENAI_API_KEY is invalid.
        openai.RateLimitError: If the API rate limit is hit.
        openai.APIError: For other API errors.

    Note on Claude:
        When Anthropic support is added, this function will check the model name
        prefix ("claude-" vs "gpt-") to route to the correct provider.
        The function signature will NOT change.
    """

    # Lazy import: only import openai when actually calling.
    # This avoids import errors in tests that mock this function.
    from openai import OpenAI

    # Create a client using the API key from the environment.
    # We create a new client per call (not per module) because:
    #   1. It's stateless — no connection pooling needed for our call volume.
    #   2. It picks up env var changes without restart.
    #   3. It's simpler than managing a global client instance.
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Build the API call kwargs.
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # JSON mode: tells the LLM to return valid JSON.
    # This is critical for agents that parse the response as structured data.
    # Without it, the LLM might return markdown, explanations, or code blocks
    # mixed with JSON, causing parse failures.
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)

    # Extract the text content from the response.
    # The OpenAI SDK returns a ChatCompletion object; we just want the text.
    return response.choices[0].message.content or ""
