from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator

# The two framings every rule in statutes.yaml carries under party_framing.
Party = Literal["tenant", "landlord"]


class VaultCreate(BaseModel):
    label: Optional[str] = None
    zip_code: Optional[str] = None

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


class EventRead(BaseModel):
    id: int
    event_type: str
    occurred_at: date
    recorded_at: datetime
    facts: dict[str, Any]
    notes: Optional[str]
    source_document_ref: Optional[str] = None
    original_filename: Optional[str] = None


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
