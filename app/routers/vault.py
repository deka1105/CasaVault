from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.database import get_session
from app.models import Vault
from app.rtc import handoff_for_zip
from app.schemas import VaultCreate, VaultRead

router = APIRouter(prefix="/api/vaults", tags=["vaults"])


def _get_by_share_token(share_token: str, session: Session) -> Vault:
    vault = session.exec(select(Vault).where(Vault.share_token == share_token)).first()
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault


@router.post("", response_model=VaultRead)
def create_vault(payload: VaultCreate, session: Session = Depends(get_session)):
    vault = Vault(label=payload.label, zip_code=payload.zip_code)
    session.add(vault)
    session.commit()
    session.refresh(vault)
    return vault


@router.get("/{vault_id}", response_model=VaultRead)
def get_vault(vault_id: str, session: Session = Depends(get_session)):
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault


@router.get("/{vault_id}/rtc-check")
def rtc_check(vault_id: str, request: Request, session: Session = Depends(get_session)):
    vault = get_vault(vault_id, session)
    return handoff_for_zip(request.app.state.statutes.right_to_counsel, vault.zip_code)


@router.get("/by-share-token/{share_token}", response_model=VaultRead)
def get_vault_by_share_token(share_token: str, session: Session = Depends(get_session)):
    return _get_by_share_token(share_token, session)


@router.post("/by-share-token/{share_token}/acknowledge", response_model=VaultRead)
def acknowledge_vault(share_token: str, session: Session = Depends(get_session)):
    """Counterparty read-only acknowledgement (PLAN.md: 'one-click timestamped
    acknowledgement'). First click wins — the evidentiary value is the
    earliest moment the counterparty is shown to have viewed the vault, so a
    repeat click must not overwrite it."""
    vault = _get_by_share_token(share_token, session)
    if vault.acknowledged_at is None:
        vault.acknowledged_at = datetime.now(timezone.utc)
        session.add(vault)
        session.commit()
        session.refresh(vault)
    return vault
