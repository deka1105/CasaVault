from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.auth import require_user_id
from app.database import get_session
from app.documents import events_with_documents
from app.models import Deadline, Flag, Vault, VaultDocument, VaultEvent
from app.rules_engine import (
    adjudicate_vault,
    build_adjudication_report,
    compute_deadlines_for_event,
    describe_deadline,
)
from app.schemas import DeadlineRead, EventCreate, EventRead, FlagRead, Party
from app import storage

router = APIRouter(prefix="/api/vaults/{vault_id}", tags=["events"])

DELETE_WINDOW_SECONDS = 600


def _require_vault(vault_id: str, session: Session) -> Vault:
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault


@router.post("/events", response_model=EventRead)
async def create_event(
    vault_id: str, payload: EventCreate, request: Request,
    session: Session = Depends(get_session),
    _user: str = Depends(require_user_id),
):
    _require_vault(vault_id, session)
    event = VaultEvent(vault_id=vault_id, **payload.model_dump())
    session.add(event)
    session.commit()
    session.refresh(event)

    table = request.app.state.statutes
    adjudicate_vault(vault_id, session, table)
    compute_deadlines_for_event(event, session, table)

    return event


@router.get("/events", response_model=list[EventRead])
async def list_events(
    vault_id: str, session: Session = Depends(get_session),
    _user: str = Depends(require_user_id),
):
    _require_vault(vault_id, session)
    return events_with_documents(vault_id, session)


@router.get("/flags", response_model=list[FlagRead])
def list_flags(vault_id: str, session: Session = Depends(get_session)):
    """Current adjudication result for the vault's aggregated facts —
    recomputed from scratch on every event write, so this always reflects
    every event recorded so far, not just the most recent one."""
    _require_vault(vault_id, session)
    return session.exec(select(Flag).where(Flag.vault_id == vault_id)).all()


@router.get("/deadlines", response_model=list[DeadlineRead])
def list_deadlines(
    vault_id: str,
    request: Request,
    party: Party = Query("tenant"),
    session: Session = Depends(get_session),
):
    """One rule, two framings — for clocks as well as flags."""
    _require_vault(vault_id, session)
    table = request.app.state.statutes
    deadlines = session.exec(select(Deadline).where(Deadline.vault_id == vault_id)).all()
    return [
        DeadlineRead(
            id=d.id,
            statute_id=d.statute_id,
            due_date=d.due_date,
            description=describe_deadline(d, table, party),
            resolved=d.resolved,
            created_at=d.created_at,
        )
        for d in deadlines
    ]


@router.get("/adjudication")
def get_adjudication(
    vault_id: str,
    request: Request,
    party: Party = Query("tenant"),
    session: Session = Depends(get_session),
):
    """The full picture: what fired, what is affirmatively satisfied, and what
    can't be judged yet for lack of facts. `/flags` stays as-is — it is what
    the evidence packet and the agent read — but a user needs all three
    states, not only the failures. See rules_engine.build_adjudication_report."""
    _require_vault(vault_id, session)
    return build_adjudication_report(vault_id, session, request.app.state.statutes, party)


@router.delete("/events/{event_id}")
async def delete_event(
    vault_id: str, event_id: int, request: Request,
    session: Session = Depends(get_session),
    _user: str = Depends(require_user_id),
):
    """Delete an event within 10 minutes of creation. After that it is
    permanent — the point of a record is that it can't be quietly erased."""
    vault = _require_vault(vault_id, session)
    event = session.get(VaultEvent, event_id)
    if event is None or event.vault_id != vault_id:
        raise HTTPException(status_code=404, detail="event not found")

    age = (datetime.now(timezone.utc) - event.recorded_at).total_seconds()
    if age > DELETE_WINDOW_SECONDS:
        raise HTTPException(
            status_code=403,
            detail="This entry is older than 10 minutes and can no longer be deleted. Contact support if you need it removed.",
        )

    docs = session.exec(
        select(VaultDocument).where(VaultDocument.event_id == event_id)
    ).all()
    for doc in docs:
        storage.delete(doc.storage_ref)
        session.delete(doc)

    if event.source_document_ref:
        storage.delete(event.source_document_ref)

    flags = session.exec(select(Flag).where(Flag.event_id == event_id)).all()
    for flag in flags:
        session.delete(flag)
    deadlines = session.exec(select(Deadline).where(Deadline.event_id == event_id)).all()
    for dl in deadlines:
        session.delete(dl)

    session.delete(event)
    session.commit()

    adjudicate_vault(vault_id, session, request.app.state.statutes)

    return {"deleted": True, "event_id": event_id}
