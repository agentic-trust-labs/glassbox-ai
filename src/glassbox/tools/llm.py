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
    Wraps litellm (100+ providers via a single interface). Supports:
        - Any model: OpenAI, Anthropic, Gemini, Llama, Mistral, Qwen, DeepSeek
        - JSON mode (for structured agent responses)
        - Temperature control (per agent needs)

Environment:
    Set the API key for your chosen provider:
        OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, etc.
"""

from __future__ import annotations

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
        litellm.AuthenticationError: If the provider API key is invalid.
        litellm.RateLimitError: If the API rate limit is hit.
        litellm.APIError: For other API errors.
    """

    # Lazy import: only import litellm when actually calling.
    # This avoids import errors in tests that mock this function.
    # litellm supports 100+ providers (OpenAI, Anthropic, Gemini, etc.)
    # via a single completion() interface.
    from litellm import completion as _litellm_completion

    response = _litellm_completion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **({"response_format": {"type": "json_object"}} if json_mode else {}),
    )
    return response.choices[0].message.content or ""
