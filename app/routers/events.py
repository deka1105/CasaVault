from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import Deadline, Flag, Vault, VaultEvent
from app.rules_engine import adjudicate_vault, compute_deadlines_for_event, describe_deadline
from app.schemas import DeadlineRead, EventCreate, EventRead, FlagRead, Party

router = APIRouter(prefix="/api/vaults/{vault_id}", tags=["events"])


def _require_vault(vault_id: str, session: Session) -> Vault:
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault


@router.post("/events", response_model=EventRead)
def create_event(
    vault_id: str, payload: EventCreate, request: Request, session: Session = Depends(get_session)
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
def list_events(vault_id: str, session: Session = Depends(get_session)):
    _require_vault(vault_id, session)
    return session.exec(
        select(VaultEvent).where(VaultEvent.vault_id == vault_id).order_by(VaultEvent.occurred_at)
    ).all()


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
