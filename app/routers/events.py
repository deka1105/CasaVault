from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Vault, VaultEvent
from app.schemas import EventCreate, EventRead

router = APIRouter(prefix="/api/vaults/{vault_id}/events", tags=["events"])


def _require_vault(vault_id: str, session: Session) -> Vault:
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault


@router.post("", response_model=EventRead)
def create_event(vault_id: str, payload: EventCreate, session: Session = Depends(get_session)):
    _require_vault(vault_id, session)
    event = VaultEvent(vault_id=vault_id, **payload.model_dump())
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("", response_model=list[EventRead])
def list_events(vault_id: str, session: Session = Depends(get_session)):
    _require_vault(vault_id, session)
    return session.exec(
        select(VaultEvent).where(VaultEvent.vault_id == vault_id).order_by(VaultEvent.occurred_at)
    ).all()
