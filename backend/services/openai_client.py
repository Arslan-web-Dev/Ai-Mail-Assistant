"""
openai_client.py

Thin wrapper around the OpenAI Chat Completions API used by both the AI
analyzer and the reply generator. Centralized here so:
- there is exactly one place that holds/creates the OpenAI client
- callers get a single, simple failure mode (AIResponseError) instead of
  needing to know about the OpenAI SDK's exception hierarchy
- tests can mock a single function (`chat_json_completion`) instead of the
  SDK/network layer
"""
from __future__ import annotations

import json
from functools import lru_cache

from openai import OpenAI

from app.config import settings


class AIResponseError(Exception):
    """Raised when the OpenAI call fails, or returns content that isn't valid JSON."""


@lru_cache
def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.openai_api_key)


def chat_json_completion(system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> dict:
    """
    Call the configured OpenAI model in JSON mode and return the parsed
    dict. Raises AIResponseError on any failure — callers own retry policy
    and fallback behavior, this function does not retry.
    """
    try:
        response = _client().chat.completions.create(
            model=settings.openai_model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:  # openai.OpenAIError subclasses, network errors, etc.
        raise AIResponseError(f"OpenAI request failed: {exc}") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise AIResponseError("OpenAI returned an empty response")

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIResponseError(f"OpenAI returned invalid JSON: {exc}") from exc
