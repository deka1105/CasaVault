from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.auth import get_optional_user_id, require_user_id
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
def create_vault(
    payload: VaultCreate,
    session: Session = Depends(get_session),
    owner_user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Anonymous by default (PLAN.md: 'no signup'). If the caller is signed
    in (Clerk), the vault is additionally tagged with owner_user_id so they
    can find it later via GET /mine — this never restricts anonymous access
    to the vault's own id/share_token, it's purely additive."""
    vault = Vault(label=payload.label, zip_code=payload.zip_code, owner_user_id=owner_user_id)
    session.add(vault)
    session.commit()
    session.refresh(vault)
    return vault


@router.get("/mine", response_model=list[VaultRead])
def list_my_vaults(session: Session = Depends(get_session), user_id: str = Depends(require_user_id)):
    """Requires sign-in (401 otherwise) — lists vaults created while signed
    in as this user. Registered before /{vault_id} so 'mine' is never
    mistaken for a vault id."""
    return session.exec(
        select(Vault).where(Vault.owner_user_id == user_id).order_by(Vault.created_at.desc())
    ).all()


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
