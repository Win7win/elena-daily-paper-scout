from __future__ import annotations

import os

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.settings import OPENAI_API_KEY_ENV, OPENAI_BASE_URL, OPENAI_MODEL, OPENAI_TIMEOUT_SECONDS


class LLMUnavailableError(RuntimeError):
    """Raised when the OpenAI client cannot be used."""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.RequestException, LLMUnavailableError)),
)
def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 500,
) -> str:
    """Small OpenAI Chat Completions wrapper with retry and basic errors."""
    api_key = os.getenv(OPENAI_API_KEY_ENV)
    if not api_key:
        raise LLMUnavailableError(f"Missing {OPENAI_API_KEY_ENV}")

    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": OPENAI_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=OPENAI_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise LLMUnavailableError(f"OpenAI API error {response.status_code}: {response.text[:300]}")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMUnavailableError(f"Unexpected OpenAI response: {data}") from exc

