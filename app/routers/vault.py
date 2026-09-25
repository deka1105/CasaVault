from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.auth import get_optional_user_id, require_user_id
from app.database import get_session
from app.models import Vault
from app.rtc import handoff_for_zip
from app.schemas import VaultCreate, VaultRead

router = APIRouter(prefix="/api/vaults", tags=["vaults"])


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


# The by-share-token routes live in app/routers/share.py — the counterparty's
# read-only surface is kept in one module so the property "a share link never
# yields the vault id" is auditable in one place rather than spread across
# the owner routes above.
