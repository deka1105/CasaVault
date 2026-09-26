"""Gemini client with API key rotation.

Supports multiple comma-separated keys in GEMINI_API_KEY. On a 429 (daily
quota exhausted), the caller can request the next key via build_client(key_index=N).
This lets extraction and agent calls cycle through keys before giving up.

SDK retries are disabled — see the original rationale below — and retry
policy is owned by the application layer (app/agent.py, app/extractor.py).

Why SDK retries are off: google-genai's defaults (5 attempts, exponential
backoff up to 60s, retrying 408/429/5xx) turned a daily-quota 429 into a
2m19s hang. The free tier cap is daily, so retrying cannot clear it.
"""

import logging
from google.genai import Client, types

from app.config import GEMINI_API_KEYS

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 120_000
_NO_SDK_RETRIES = types.HttpRetryOptions(attempts=1)


def available_key_count() -> int:
    return len(GEMINI_API_KEYS)


def build_client(key_index: int = 0, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Client:
    if not GEMINI_API_KEYS:
        raise RuntimeError("No GEMINI_API_KEY configured")
    idx = key_index % len(GEMINI_API_KEYS)
    return Client(
        api_key=GEMINI_API_KEYS[idx],
        http_options=types.HttpOptions(timeout=timeout_ms, retry_options=_NO_SDK_RETRIES),
    )
