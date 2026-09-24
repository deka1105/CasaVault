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


class AskRequest(BaseModel):
    question: str
    party: str = "tenant"  # "tenant" | "landlord"


class AskResponse(BaseModel):
    answer: Optional[str] = None
    citation: Optional[str] = None
    refusal: Optional[str] = None
    handoff: Optional[dict[str, Any]] = None
