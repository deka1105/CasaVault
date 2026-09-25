from pathlib import Path
from typing import Any

from google import genai

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.extraction_schema import ExtractedFacts

# google-genai's DocumentContent/ImageContent types only recognize these
# mime types (checked against the installed SDK's type defs, see below).
# .txt is handled separately, as an inline text block, rather than as a
# "document" — text/plain isn't in DocumentContentMimeType's known list.
_DOCUMENT_MIME_TYPES = {".pdf": "application/pdf"}
_IMAGE_MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".heic": "image/heic"}

_EXTRACTION_PROMPT = (
    "You are a document-parsing engine for a tenant/landlord recordkeeping vault. "
    "Extract only facts explicitly stated in the attached document into the given "
    "schema. Do not infer, guess, or reach any legal conclusion — a separate "
    "deterministic system decides what any fact means. Leave a field null if the "
    "document does not state it; never fabricate a value."
)


class ExtractionUnavailable(RuntimeError):
    """No LLM key configured. Callers should treat this as 'facts stay
    empty', not as a request failure — see app/routers/documents.py."""


class ExtractionUnsupported(ValueError):
    """File type has no content-block mapping (e.g. .docx)."""


class ExtractionRateLimited(RuntimeError):
    """The provider refused for quota reasons (429).

    Worth its own type because it is neither a bug nor a property of the
    document: the upload succeeded and the file is stored, but no facts could
    be read and no amount of retrying within the day will change that. The
    caller surfaces this to the user verbatim — a document that silently
    produced zero facts is indistinguishable from a document that genuinely
    stated none, and during a demo that reads as a broken product.
    """


class ExtractionUpstreamError(RuntimeError):
    """The provider could not be reached (503/timeout/connection)."""


_RATE_LIMIT_MARKERS = ("429", "rate limit", "too_many_requests", "quota", "resource_exhausted")
_TRANSIENT_MARKERS = ("503", "500", "service_unavailable", "unavailable", "high demand", "overloaded", "timeout", "timed out", "connection")


def _classify(exc: Exception) -> Exception:
    """Map a provider exception onto our own taxonomy. Matched on text, not
    class: google-genai raises these from private _gaos.* modules whose import
    paths are not a stable API."""
    text = f"{getattr(exc, 'code', '')} {getattr(exc, 'status_code', '')} {exc}".lower()
    if any(m in text for m in _RATE_LIMIT_MARKERS):
        return ExtractionRateLimited(str(exc))
    if any(m in text for m in _TRANSIENT_MARKERS):
        return ExtractionUpstreamError(str(exc))
    return exc


def _content_block_for_file(path: Path) -> dict[str, Any]:
    ext = path.suffix.lower()
    if ext in _DOCUMENT_MIME_TYPES:
        return {"type": "document", "data": path, "mime_type": _DOCUMENT_MIME_TYPES[ext]}
    if ext in _IMAGE_MIME_TYPES:
        return {"type": "image", "data": path, "mime_type": _IMAGE_MIME_TYPES[ext]}
    if ext == ".txt":
        return {"type": "text", "text": path.read_text(encoding="utf-8", errors="replace")}
    raise ExtractionUnsupported(f"no extraction support for file type: {ext}")


def extract_facts_from_file(path: Path) -> dict[str, Any]:
    """Runs the fixed-schema extractor against an uploaded file and returns
    a plain dict of only the facts the document actually stated (None
    fields dropped). Raises ExtractionUnavailable / ExtractionUnsupported
    rather than silently returning {} so the caller can log/skip explicitly.

    The request/response shape here (client.interactions.create, the
    text/document/image content-block dicts, response_format, and
    interaction.output_text) was checked directly against the installed
    google-genai package's type definitions (_gaos/types/interactions/*),
    not just documentation — so the wire shape should be right. What's
    still unverified is an actual live call: no GEMINI_API_KEY was
    available while building this, including whether GEMINI_MODEL below
    is a real, currently-served model id. Check that first if this errors.
    """
    if not GEMINI_API_KEY:
        raise ExtractionUnavailable("GEMINI_API_KEY is not configured")

    content_block = _content_block_for_file(path)

    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=[
                {"type": "text", "text": _EXTRACTION_PROMPT},
                content_block,
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": ExtractedFacts.model_json_schema(),
            },
        )
    except Exception as exc:
        raise _classify(exc) from exc

    facts = ExtractedFacts.model_validate_json(interaction.output_text)
    return facts.model_dump(exclude_none=True)
