import json
import logging
import time
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.models import Deadline, Flag, VaultEvent
from app.statutes_loader import StatuteTable

logger = logging.getLogger(__name__)


class AgentUnavailable(RuntimeError):
    """No LLM key configured. Callers should fall back to the safe refusal
    stub — see app/routers/agent.py."""


class AgentUpstreamError(RuntimeError):
    """The model provider could not be reached (503/429/timeout), as opposed
    to the agent declining to answer.

    Both outcomes are safe — neither ever produces a guess — but they are not
    the same thing, and conflating them is actively misleading here: a
    refusal is this product's designed behaviour (PLAN.md: "That last
    refusal goes in the demo video. It is the point."), while an upstream
    outage is a fault. Showing "I can't ground that in your vault" when the
    truth is "Gemini returned 503" teaches the user to distrust a refusal
    that was working exactly as intended.
    """


class AgentRateLimited(AgentUpstreamError):
    """The provider refused on quota (429).

    Split from the retryable case deliberately: the configured key's limit is
    a DAILY one (20 requests on the free tier), so retrying cannot clear it —
    it just burns ~2 minutes per attempt, since the SDK does its own internal
    backoff before surfacing the 429. Fail fast and say what happened.
    """


# Matched against exception text rather than class: google-genai raises these
# from private _gaos.* modules whose import paths are not a stable API.
_RATE_LIMIT_MARKERS = ("429", "rate limit", "ratelimit", "too_many_requests", "quota", "resource_exhausted")
_TRANSIENT_MARKERS = (
    "503",
    "500",
    "service_unavailable",
    "unavailable",
    "high demand",
    "overloaded",
    "timeout",
    "timed out",
    "deadline exceeded",
    "connection",
)


def _error_text(exc: Exception) -> str:
    return f"{getattr(exc, 'code', '')} {getattr(exc, 'status_code', '')} {exc}".lower()


def _is_rate_limit(exc: Exception) -> bool:
    return any(marker in _error_text(exc) for marker in _RATE_LIMIT_MARKERS)


def _looks_transient(exc: Exception) -> bool:
    return any(marker in _error_text(exc) for marker in _TRANSIENT_MARKERS)


class GroundedAnswer(BaseModel):
    """Schema-constrained model output. `grounded` alone is NOT trusted —
    ask_agent independently checks citation_value against this vault's
    actual events and the statute table's actual citations before ever
    returning an answer. That check, not this schema, is what makes
    grounding structural rather than a prompt request (PLAN.md: 'enforced
    structurally... not by prompt instruction alone')."""

    grounded: bool = Field(
        description="True only if the question can be fully answered using ONLY the vault events and statute rows given in context"
    )
    answer: Optional[str] = Field(None, description="The answer text. Required if grounded is true, else null.")
    citation_type: Optional[Literal["statute", "vault_event"]] = Field(
        None, description="What kind of source grounds this answer. Required if grounded is true."
    )
    citation_value: Optional[str] = Field(
        None,
        description=(
            "For citation_type 'statute': the exact citation string from context (e.g. '68 P.S. § 250.512'). "
            "For citation_type 'vault_event': the exact numeric event id from context. "
            "Must match something given in context exactly — never paraphrase or invent one."
        ),
    )


class AgentResult(BaseModel):
    grounded: bool
    answer: Optional[str] = None
    citation_display: Optional[str] = None
    refusal_reason: Optional[str] = None


_SYSTEM_PROMPT = (
    "You are a query interface over ONE tenant/landlord vault, answering for the "
    "{party} side. Answer ONLY using the vault events and statute rows given below "
    "as context — never from general legal knowledge, and never a legal conclusion "
    "(e.g. whether someone will win a case). If the question cannot be fully "
    "answered from the given context, set grounded=false and leave answer/citation "
    "null — do not guess. A grounded answer must cite exactly one vault event or "
    "one statute row from context; copy its identifier exactly."
)


def _build_context(vault_id: str, session: Session, table: StatuteTable, party: str) -> dict[str, Any]:
    events = session.exec(
        select(VaultEvent).where(VaultEvent.vault_id == vault_id).order_by(VaultEvent.occurred_at)
    ).all()
    flags = session.exec(select(Flag).where(Flag.vault_id == vault_id)).all()
    deadlines = session.exec(select(Deadline).where(Deadline.vault_id == vault_id)).all()

    return {
        "events": [
            {"id": e.id, "type": e.event_type, "date": str(e.occurred_at), "notes": e.notes, "facts": e.facts}
            for e in events
        ],
        "flags": [
            {
                "statute_id": f.statute_id,
                "severity": f.severity,
                "citation": f.citation,
                "message": f.message_tenant if party == "tenant" else f.message_landlord,
            }
            for f in flags
        ],
        "deadlines": [
            {"statute_id": d.statute_id, "due_date": str(d.due_date), "description": d.description, "resolved": d.resolved}
            for d in deadlines
        ],
        # Full verified table, not just this vault's current flags — lets the
        # agent answer general "how does X work" questions (e.g. the deposit
        # clock) even before that rule has fired for this vault.
        #
        # Pass every field a rule has, not a fixed subset: rules aren't
        # uniform (a `condition` rule has `detail`; a `type: deadline` rule
        # like deposit_return_clock instead carries its substance in
        # `clock`/`on_expiry`/`requires`). An earlier version only forwarded
        # `detail`, so the model had no way to answer "how long does he have
        # to return my deposit" — the "30 days" lives in `clock`, which
        # wasn't in context at all. Caught by a live test against exactly
        # that PLAN.md example question.
        "statutes": [
            {
                **{k: v for k, v in rule.items() if k not in ("party_framing", "status")},
                "framing": (rule.get("party_framing") or {}).get(party),
            }
            for rule in table.verified_rules
        ],
    }


def _call_model(question: str, party: str, context: dict[str, Any]) -> GroundedAnswer:
    from google import genai  # imported lazily so tests can patch config before this loads

    client = genai.Client(api_key=GEMINI_API_KEY)
    interaction = client.interactions.create(
        model=GEMINI_MODEL,
        input=[
            {"type": "text", "text": _SYSTEM_PROMPT.format(party=party)},
            {"type": "text", "text": f"Context (JSON): {json.dumps(context)}"},
            {"type": "text", "text": f"Question: {question}"},
        ],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": GroundedAnswer.model_json_schema(),
        },
    )
    return GroundedAnswer.model_validate_json(interaction.output_text)


def _call_model_with_retry(
    question: str, party: str, context: dict[str, Any], attempts: int = 3
) -> GroundedAnswer:
    """One transient 503 from the provider should not become a refusal the
    user reads as the agent's own judgement. Retries only provider-side
    failures; a schema/validation error is raised immediately, since retrying
    it would just burn quota for the same result."""
    delay = 1.5
    for attempt in range(attempts):
        try:
            return _call_model(question, party, context)
        except Exception as exc:
            if _is_rate_limit(exc):
                logger.warning("agent hit the provider quota: %s", exc)
                raise AgentRateLimited(str(exc)) from exc
            if not _looks_transient(exc):
                raise
            if attempt == attempts - 1:
                logger.warning("agent model call failed after %d attempts: %s", attempts, exc)
                raise AgentUpstreamError(str(exc)) from exc
            logger.info("transient model failure (attempt %d/%d): %s", attempt + 1, attempts, exc)
            time.sleep(delay)
            delay *= 2
    raise AgentUpstreamError("model call exhausted retries")  # unreachable, kept for type-checkers


def _verify_citation(candidate: GroundedAnswer, context: dict[str, Any]) -> bool:
    if candidate.citation_type == "statute":
        return any(s["citation"] == candidate.citation_value for s in context["statutes"])
    if candidate.citation_type == "vault_event":
        return any(str(e["id"]) == str(candidate.citation_value) for e in context["events"])
    return False


def _display_citation(candidate: GroundedAnswer, context: dict[str, Any]) -> str:
    if candidate.citation_type == "statute":
        return candidate.citation_value
    event = next(e for e in context["events"] if str(e["id"]) == str(candidate.citation_value))
    return f"event #{event['id']}, {event['type']}, {event['date']}"


def ask_agent(question: str, party: str, vault_id: str, session: Session, table: StatuteTable) -> AgentResult:
    if not GEMINI_API_KEY:
        raise AgentUnavailable("GEMINI_API_KEY is not configured")

    context = _build_context(vault_id, session, table, party)
    candidate = _call_model_with_retry(question, party, context)

    if not candidate.grounded or not candidate.answer or not candidate.citation_value:
        return AgentResult(
            grounded=False,
            refusal_reason="I can't ground an answer to that in your vault or the statute table, so I won't guess.",
        )

    if not _verify_citation(candidate, context):
        logger.warning("agent claimed groundedness with an unverifiable citation: %r", candidate.citation_value)
        return AgentResult(
            grounded=False,
            refusal_reason="I couldn't verify a source for that answer, so I won't guess.",
        )

    return AgentResult(grounded=True, answer=candidate.answer, citation_display=_display_citation(candidate, context))
