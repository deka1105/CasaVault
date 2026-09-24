import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Vault(SQLModel, table=True):
    """One vault per tenancy. No auth — the id and share_token are the
    access control (PLAN.md: 'Single vault, no signup')."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    label: Optional[str] = None
    zip_code: Optional[str] = None
    share_token: str = Field(default_factory=_uuid, index=True, unique=True)
    created_at: datetime = Field(default_factory=_now)


class VaultEvent(SQLModel, table=True):
    """A timeline entry: a document upload or a dated event (repair request,
    notice received, inspection, payment, photo, move-in/out, forwarding
    address). `facts` holds the extractor's schema-bound output — the
    extractor never judges legality, it only fills this dict."""

    id: Optional[int] = Field(default=None, primary_key=True)
    vault_id: str = Field(foreign_key="vault.id", index=True)
    event_type: str
    occurred_at: date
    recorded_at: datetime = Field(default_factory=_now)
    facts: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    source_document_ref: Optional[str] = None
    notes: Optional[str] = None


class Flag(SQLModel, table=True):
    """One adjudication result. statute_id must match a verified rule's `id`
    in statutes.yaml — never persist a flag for a draft rule."""

    id: Optional[int] = Field(default=None, primary_key=True)
    vault_id: str = Field(foreign_key="vault.id", index=True)
    event_id: Optional[int] = Field(default=None, foreign_key="vaultevent.id")
    statute_id: str
    severity: str
    citation: str
    message_tenant: Optional[str] = None
    message_landlord: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Deadline(SQLModel, table=True):
    """A dated obligation derived from a statutory clock (e.g. the 30-day
    deposit-return clock in statutes.yaml)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    vault_id: str = Field(foreign_key="vault.id", index=True)
    event_id: Optional[int] = Field(default=None, foreign_key="vaultevent.id")
    statute_id: str
    due_date: date
    description: str
    resolved: bool = False
    created_at: datetime = Field(default_factory=_now)
