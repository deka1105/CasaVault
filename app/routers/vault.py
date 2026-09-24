from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Vault
from app.schemas import VaultCreate, VaultRead

router = APIRouter(prefix="/api/vaults", tags=["vaults"])


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


@router.get("/by-share-token/{share_token}", response_model=VaultRead)
def get_vault_by_share_token(share_token: str, session: Session = Depends(get_session)):
    vault = session.exec(select(Vault).where(Vault.share_token == share_token)).first()
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault
