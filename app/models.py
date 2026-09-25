import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Property(SQLModel, table=True):
    """An address. The thing a record attaches to, the way a CARFAX report
    attaches to a VIN rather than to an owner.

    `address_normalized` is the join key — the building-level form produced by
    app/city_data.py:normalize_address, which strips the unit because a
    Philadelphia rental licence is issued to the property, not the apartment.
    `address_display` keeps what the user actually typed, unit included.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    address_normalized: str = Field(index=True, unique=True)
    address_display: str
    zip_code: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class PropertyLink(SQLModel, table=True):
    """Which vault covers which address, and for what period.

    Deliberately a join table rather than a `Vault.property_id` column:
    SQLModel.metadata.create_all() creates tables that don't exist but never
    alters existing ones, so a new column on `vault` would need a manual
    ALTER TABLE against the live Neon database (see CLAUDE.md). A new table
    needs none. It is also the truthful shape — one address has many
    tenancies over time, which is the whole point of a record that outlives
    its occupants.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    vault_id: str = Field(foreign_key="vault.id", index=True)
    property_id: int = Field(foreign_key="property.id", index=True)
    unit: Optional[str] = None
    moved_in: Optional[date] = None
    moved_out: Optional[date] = None
    created_at: datetime = Field(default_factory=_now)


class Incident(SQLModel, table=True):
    """Something that went wrong, and the lifecycle of getting it fixed.

    The four timestamps are the work-order history: reported → acknowledged →
    started → resolved. `reported_at` is the valuable one, because the
    accompanying email gives it provenance outside this app: a send time, a
    named recipient, and a copy in the resident's own mailbox. Written notice
    is load-bearing under PA and Philadelphia law, so this is the difference
    between a diary entry and evidence that notice was given.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    vault_id: str = Field(foreign_key="vault.id", index=True)
    property_id: Optional[int] = Field(default=None, foreign_key="property.id", index=True)
    reference_code: str = Field(index=True)

    category: str
    urgency: str
    summary: str
    detail: Optional[str] = None
    # Habitability: heat, water, electricity or security being affected
    # changes both the urgency and which law applies.
    affects_essential_service: bool = False
    previously_reported: bool = False

    reported_at: Optional[date] = None
    acknowledged_at: Optional[date] = None
    work_started_at: Optional[date] = None
    resolved_at: Optional[date] = None
    impact: Optional[str] = None

    management_email: Optional[str] = None
    event_id: Optional[int] = Field(default=None, foreign_key="vaultevent.id")
    created_at: datetime = Field(default_factory=_now)


class Vault(SQLModel, table=True):
    """One vault per tenancy. The id and share_token remain the actual
    access control (PLAN.md: 'Single vault, no signup') — owner_user_id is
    purely additive, for a signed-in creator to find their own vaults later
    via GET /api/vaults/mine. It does not gate access to the vault itself;
    anonymous id/share-token access is unchanged whether or not this is set."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    label: Optional[str] = None
    zip_code: Optional[str] = None
    share_token: str = Field(default_factory=_uuid, index=True, unique=True)
    created_at: datetime = Field(default_factory=_now)
    acknowledged_at: Optional[datetime] = None
    owner_user_id: Optional[str] = Field(default=None, index=True)


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
    original_filename: Optional[str] = None
    notes: Optional[str] = None


class VaultDocument(SQLModel, table=True):
    """One stored file. Many of these can hang off a single VaultEvent.

    A real Philadelphia lease arrives as ~25 PDFs that are all one act —
    signing the lease. Before this, each file had to become its own event,
    which turned one signing into 25 timeline rows and made the user pick a
    date 25 times. VaultEvent keeps its own source_document_ref for events
    written before this table existed, so old download links still resolve;
    see app/routers/documents.py:build_document_response.

    Safe to add mid-flight, unlike a new column: SQLModel.metadata.create_all
    does create tables that don't exist yet — it only refuses to alter
    existing ones (see the migration note in CLAUDE.md).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    vault_id: str = Field(foreign_key="vault.id", index=True)
    event_id: int = Field(foreign_key="vaultevent.id", index=True)
    storage_ref: str
    original_filename: Optional[str] = None
    # Why this file was or wasn't sent to the extractor — see app/triage.py.
    triage_category: str = "priority"
    extraction_status: str = "skipped"
    extraction_note: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


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
