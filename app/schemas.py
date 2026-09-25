from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator

# The two framings every rule in statutes.yaml carries under party_framing.
Party = Literal["tenant", "landlord"]


class VaultCreate(BaseModel):
    label: Optional[str] = None
    zip_code: Optional[str] = None
    # The address the record belongs to. Optional so existing callers and
    # tests keep working, but it is the intended entry point: the record
    # attaches to the property, not to whoever happens to hold it now.
    address: Optional[str] = None
    unit: Optional[str] = None

    @field_validator("zip_code")
    @classmethod
    def _five_digit_zip(cls, value: Optional[str]) -> Optional[str]:
        """The Right to Counsel check is an exact-string match against
        statutes.yaml's covered_zips, so "19121 " or "19121-1234" would
        silently route a covered tenant to the generic fallback instead of
        the hotline. Normalize and reject anything that isn't 5 digits."""
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not (len(value) == 5 and value.isdigit()):
            raise ValueError("zip_code must be 5 digits")
        return value


class VaultRead(BaseModel):
    id: str
    label: Optional[str]
    zip_code: Optional[str]
    share_token: str
    created_at: datetime
    acknowledged_at: Optional[datetime]
    owner_user_id: Optional[str] = None
    address: Optional[str] = None
    address_normalized: Optional[str] = None


class VaultShareRead(BaseModel):
    """What a counterparty holding only a share link may see about the vault.

    Deliberately omits `id` and `share_token`. The vault id IS the owner
    credential — every write route (events, documents) is addressed by it and
    has no other gate — so returning it here would have made the "read-only"
    share link a full write credential. The read-only surface is served by
    app/routers/share.py, addressed by the token instead.
    """

    label: Optional[str]
    zip_code: Optional[str]
    created_at: datetime
    acknowledged_at: Optional[datetime]


class EventCreate(BaseModel):
    event_type: str
    occurred_at: date
    facts: dict[str, Any] = {}
    notes: Optional[str] = None


class DocumentRead(BaseModel):
    """One stored file within an event. A real lease is ~25 of these under a
    single 'lease signed' entry — see app/models.py:VaultDocument."""

    id: int
    original_filename: Optional[str]
    triage_category: str
    extraction_status: str
    extraction_note: Optional[str] = None


class EventRead(BaseModel):
    id: int
    event_type: str
    occurred_at: date
    recorded_at: datetime
    facts: dict[str, Any]
    notes: Optional[str]
    source_document_ref: Optional[str] = None
    original_filename: Optional[str] = None
    documents: list[DocumentRead] = []


class ExtractionInfo(BaseModel):
    """Why an upload's facts look the way they do.

    Computed per-request and never persisted, so this needed no new model
    field (and therefore no manual ALTER TABLE against the live database —
    see the SQLModel migration note in CLAUDE.md). `status` is one of:
    ok, no_facts, not_configured, unsupported_type, rate_limited,
    upstream_error, failed.
    """

    status: str
    message: Optional[str] = None


class DocumentUploadRead(EventRead):
    """EventRead plus the extraction outcome. The document is always stored
    regardless — extraction is strictly best-effort on top of that — but a
    document that produced zero facts because the daily model quota ran out
    is not the same as one that genuinely stated none, and the UI cannot tell
    those apart from an empty dict alone."""

    extraction: ExtractionInfo


class FlagRead(BaseModel):
    id: int
    statute_id: str
    severity: str
    citation: str
    message_tenant: Optional[str]
    message_landlord: Optional[str]
    created_at: datetime


class DeadlineRead(BaseModel):
    id: int
    statute_id: str
    due_date: date
    description: str
    resolved: bool
    created_at: datetime


# Fixed vocabularies. Free text here would be useless for filtering and
# carries no weight in a record — and urgency in particular has legal
# consequences, since losing heat in winter is not the same kind of problem
# as a slow drain.
IncidentCategory = Literal[
    "heat", "hot_water", "water_leak", "electrical", "pest", "mold",
    "security", "appliance", "structural", "other",
]
IncidentUrgency = Literal["emergency", "urgent", "routine"]


class IncidentCreate(BaseModel):
    category: IncidentCategory
    urgency: IncidentUrgency
    summary: str
    detail: Optional[str] = None
    # Heat, water, electricity or security being affected is the question that
    # changes which protections apply, so it is asked explicitly rather than
    # inferred from free text.
    affects_essential_service: bool = False
    previously_reported: bool = False
    reported_at: Optional[date] = None
    management_email: Optional[str] = None
    insurance_email: Optional[str] = None
    reporter_name: Optional[str] = None


class IncidentDraft(BaseModel):
    """A drafted notice, for the user to read and send themselves.

    Never sent by us: a notice that arrives from casavault.app is weaker
    evidence that the *resident* gave notice, and sending a housing dispute
    on someone's behalf is not a thing this app should do silently.
    """

    subject: str
    body: str
    to: Optional[str] = None
    mailto: str


class IncidentRead(BaseModel):
    id: int
    reference_code: str
    category: str
    urgency: str
    summary: str
    affects_essential_service: bool
    previously_reported: bool
    reported_at: Optional[date]
    acknowledged_at: Optional[date]
    work_started_at: Optional[date]
    resolved_at: Optional[date]
    draft: Optional[IncidentDraft] = None


class AskRequest(BaseModel):
    question: str
    # Literal, not str: an unrecognized party used to fall through to the
    # landlord framing of every rule, silently showing a tenant the wrong
    # side of the same rule. statutes.yaml defines exactly these two.
    party: Party = "tenant"


class AskResponse(BaseModel):
    answer: Optional[str] = None
    citation: Optional[str] = None
    refusal: Optional[str] = None
    handoff: Optional[dict[str, Any]] = None
    # True when the agent could not reach the model at all, as opposed to
    # declining to answer. Both are refusals to guess; only one is a fault.
    unavailable: bool = False
