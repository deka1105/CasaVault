from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app import city_data
from app.auth import get_optional_user_id, require_user_id
from app.database import get_session
from app.models import Property, PropertyLink, Vault, VaultEvent
from app.routers.properties import get_or_create_property
from app.rules_engine import adjudicate_vault
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
    vault = Vault(
        label=payload.label or (payload.address or "").strip() or None,
        zip_code=payload.zip_code,
        owner_user_id=owner_user_id,
    )
    session.add(vault)
    session.commit()
    session.refresh(vault)

    # Attach the record to the address. A join table rather than a column on
    # vault, so no ALTER TABLE is needed against the live database — and
    # because one address genuinely has many tenancies over time.
    if payload.address:
        prop = get_or_create_property(payload.address, session, payload.zip_code)
        if prop is not None:
            session.add(
                PropertyLink(vault_id=vault.id, property_id=prop.id, unit=payload.unit)
            )
            session.commit()

    return _with_address(vault, session)


@router.get("/mine", response_model=list[VaultRead])
def list_my_vaults(session: Session = Depends(get_session), user_id: str = Depends(require_user_id)):
    """Requires sign-in (401 otherwise) — lists vaults created while signed
    in as this user. Registered before /{vault_id} so 'mine' is never
    mistaken for a vault id."""
    vaults = session.exec(
        select(Vault).where(Vault.owner_user_id == user_id).order_by(Vault.created_at.desc())
    ).all()
    return [_with_address(v, session) for v in vaults]


@router.get("/{vault_id}", response_model=VaultRead)
def get_vault(vault_id: str, session: Session = Depends(get_session)):
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return _with_address(vault, session)


@router.get("/{vault_id}/rtc-check")
def rtc_check(vault_id: str, request: Request, session: Session = Depends(get_session)):
    vault = get_vault(vault_id, session)
    return handoff_for_zip(request.app.state.statutes.right_to_counsel, vault.zip_code)


# The by-share-token routes live in app/routers/share.py — the counterparty's
# read-only surface is kept in one module so the property "a share link never
# yields the vault id" is auditable in one place rather than spread across
# the owner routes above.


def _with_address(vault: Vault, session: Session) -> VaultRead:
    """VaultRead plus the linked address, resolved through PropertyLink."""
    view = VaultRead.model_validate(vault, from_attributes=True)
    link = session.exec(select(PropertyLink).where(PropertyLink.vault_id == vault.id)).first()
    if link:
        prop = session.get(Property, link.property_id)
        if prop:
            view.address = f"{prop.address_display}{f' {link.unit}' if link.unit else ''}".strip()
            view.address_normalized = prop.address_normalized
    return view


@router.post("/{vault_id}/city-record")
def pull_city_record(vault_id: str, request: Request, session: Session = Depends(get_session)):
    """Fetch this property's City records and file them as facts.

    The whole point of this endpoint is that it needs no changes anywhere
    else: `landlord_rental_license_valid` and `li_violations_open_days` are
    already in the extraction schema and already referenced by conditions in
    statutes.yaml, so writing them onto an event runs the existing rules
    engine and moves two rules out of "needs facts" on its own.
    """
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")

    link = session.exec(select(PropertyLink).where(PropertyLink.vault_id == vault_id)).first()
    prop = session.get(Property, link.property_id) if link else None
    address = prop.address_display if prop else vault.label
    if not address:
        raise HTTPException(status_code=400, detail="this record has no address to look up")

    record = city_data.fetch_city_record(address)
    facts = city_data.derive_facts(record)

    if facts:
        session.add(
            VaultEvent(
                vault_id=vault_id,
                event_type="city_record",
                occurred_at=date.today(),
                facts=facts,
                notes="Philadelphia L&I records for this address",
            )
        )
        session.commit()
        adjudicate_vault(vault_id, session, request.app.state.statutes)

    return {
        "checked": record.query_address,
        "found": record.address_found,
        "unavailable": record.unavailable,
        "note": record.note,
        "facts": facts,
        "rental_licences": len(record.rental_licenses),
        "open_violations": len(record.open_violations),
    }
