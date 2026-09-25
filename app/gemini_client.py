"""One place that builds the Gemini client, so timeout and retry policy are
set identically for extraction and for the agent.

Why this exists: google-genai retries on its own, and its defaults (verified
against the installed package's `types.HttpRetryOptions` field docs, not the
public docs) are 5 attempts with exponential backoff up to 60s per delay, on
a retryable set that includes 408, 429 and every 5xx.

That default turned an exhausted daily quota into a 2-minute-19-second hang
before the 429 surfaced — measured, not estimated. Two things make that bad
here rather than merely slow:

  * The free tier's cap is a DAILY one. Retrying a 429 cannot clear it, so
    every one of those retries is guaranteed waste.
  * Vercel Functions on this project cap at 300s (vercel.json). A single ask
    burning 140s sits uncomfortably close to that ceiling, and in a live demo
    a two-minute wait for an error message is indistinguishable from a hang.

So: retries are disabled at the SDK layer and owned by the application, which
can tell a daily quota apart from a transient 5xx (see app/agent.py). A hard
timeout is set so no single call can run away.
"""

from google.genai import Client, types

from app.config import GEMINI_API_KEY

# Generous enough for document understanding on a real lease PDF (calls timed
# at ~90s during development) while still bounded well inside Vercel's 300s.
DEFAULT_TIMEOUT_MS = 120_000

_NO_SDK_RETRIES = types.HttpRetryOptions(attempts=1)


def build_client(timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Client:
    return Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=timeout_ms, retry_options=_NO_SDK_RETRIES),
    )
