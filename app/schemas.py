from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


class VaultCreate(BaseModel):
    label: Optional[str] = None
    zip_code: Optional[str] = None


class VaultRead(BaseModel):
    id: str
    label: Optional[str]
    zip_code: Optional[str]
    share_token: str
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
    party: str = "tenant"  # "tenant" | "landlord"


class AskResponse(BaseModel):
    answer: Optional[str] = None
    citation: Optional[str] = None
    refusal: Optional[str] = None
    handoff: Optional[dict[str, Any]] = None
