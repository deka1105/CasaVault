"""The counterparty's read-only surface, addressed by share token.

PLAN.md promises a "counterparty read-only share link". Before this module
existed, the share flow worked by handing the counterparty the vault's own
`id` (GET /api/vaults/by-share-token/{token} returned it) and letting the
browser hide the write controls — client-side only. Anyone holding a share
link could read the id straight out of that JSON response and then POST
events or upload documents to the vault, because the vault id is the only
credential those routes check. "Read-only" was a UI convention, not a
property of the system.

Every route here is a GET except the acknowledgement POST that PLAN.md
explicitly calls for, and none of them return the vault id or share token in
a response body. That is what makes the link actually read-only.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session, select

from app.database import get_session
from app.documents import events_with_documents
from app.evidence import render_evidence_packet
from app.models import Deadline, Flag, Vault, VaultDocument, VaultEvent
from app.routers.documents import build_document_response
from app.rules_engine import build_adjudication_report, describe_deadline
from app.rtc import handoff_for_zip
from app.schemas import DeadlineRead, EventRead, FlagRead, Party, VaultShareRead

router = APIRouter(prefix="/api/vaults/by-share-token/{share_token}", tags=["share"])


def _require_vault(share_token: str, session: Session) -> Vault:
    vault = session.exec(select(Vault).where(Vault.share_token == share_token)).first()
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault


@router.get("", response_model=VaultShareRead)
def get_shared_vault(share_token: str, session: Session = Depends(get_session)):
    return _require_vault(share_token, session)


@router.post("/acknowledge", response_model=VaultShareRead)
def acknowledge_vault(share_token: str, session: Session = Depends(get_session)):
    """Counterparty read-only acknowledgement (PLAN.md: 'one-click timestamped
    acknowledgement'). First click wins — the evidentiary value is the
    earliest moment the counterparty is shown to have viewed the vault, so a
    repeat click must not overwrite it."""
    vault = _require_vault(share_token, session)
    if vault.acknowledged_at is None:
        vault.acknowledged_at = datetime.now(timezone.utc)
        session.add(vault)
        session.commit()
        session.refresh(vault)
    return vault


@router.get("/events", response_model=list[EventRead])
def list_events(share_token: str, session: Session = Depends(get_session)):
    vault = _require_vault(share_token, session)
    return events_with_documents(vault.id, session)


@router.get("/flags", response_model=list[FlagRead])
def list_flags(share_token: str, session: Session = Depends(get_session)):
    vault = _require_vault(share_token, session)
    return session.exec(select(Flag).where(Flag.vault_id == vault.id)).all()


@router.get("/deadlines", response_model=list[DeadlineRead])
def list_deadlines(
    share_token: str,
    request: Request,
    party: Party = Query("landlord"),
    session: Session = Depends(get_session),
):
    vault = _require_vault(share_token, session)
    table = request.app.state.statutes
    deadlines = session.exec(select(Deadline).where(Deadline.vault_id == vault.id)).all()
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
    share_token: str,
    request: Request,
    party: Party = Query("landlord"),
    session: Session = Depends(get_session),
):
    vault = _require_vault(share_token, session)
    return build_adjudication_report(vault.id, session, request.app.state.statutes, party)


@router.get("/rtc-check")
def rtc_check(share_token: str, request: Request, session: Session = Depends(get_session)):
    vault = _require_vault(share_token, session)
    return handoff_for_zip(request.app.state.statutes.right_to_counsel, vault.zip_code)


@router.get("/evidence", response_class=HTMLResponse)
def evidence_packet(
    share_token: str,
    request: Request,
    party: Party = Query("landlord"),
    session: Session = Depends(get_session),
):
    """Defaults to the landlord framing: the counterparty opening a tenant's
    share link is the other side of the same rules. Overridable, since a
    landlord-held vault shares to a tenant."""
    vault = _require_vault(share_token, session)
    events = session.exec(select(VaultEvent).where(VaultEvent.vault_id == vault.id)).all()
    documents = session.exec(select(VaultDocument).where(VaultDocument.vault_id == vault.id)).all()
    flags = session.exec(select(Flag).where(Flag.vault_id == vault.id)).all()
    deadlines = session.exec(select(Deadline).where(Deadline.vault_id == vault.id)).all()

    return render_evidence_packet(
        vault,
        events,
        flags,
        deadlines,
        party=party,
        # Document links must stay on the token-addressed path — linking to
        # /api/vaults/{vault.id}/documents/... would leak the owner
        # credential straight into the shared packet's HTML.
        document_base=f"/api/vaults/by-share-token/{share_token}/documents",
        documents_by_event=_group_documents(documents),
        deadline_descriptions={
            d.id: describe_deadline(d, request.app.state.statutes, party) for d in deadlines
        },
    )


@router.get("/documents/{event_id}")
def download_document(share_token: str, event_id: int, session: Session = Depends(get_session)) -> Response:
    vault = _require_vault(share_token, session)
    return build_document_response(vault.id, event_id, session)


def _group_documents(documents) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for doc in documents:
        grouped.setdefault(doc.event_id, []).append(doc)
    return grouped
