from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.database import get_session
from app.evidence import render_evidence_packet
from app.models import Deadline, Flag, Vault, VaultDocument, VaultEvent
from app.rules_engine import describe_deadline
from app.schemas import Party

router = APIRouter(prefix="/api/vaults/{vault_id}/evidence", tags=["evidence"])


@router.get("", response_class=HTMLResponse)
def get_evidence_packet(
    vault_id: str,
    request: Request,
    party: Party = Query("tenant"),
    session: Session = Depends(get_session),
):
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")

    events = session.exec(select(VaultEvent).where(VaultEvent.vault_id == vault_id)).all()
    documents = session.exec(select(VaultDocument).where(VaultDocument.vault_id == vault_id)).all()
    flags = session.exec(select(Flag).where(Flag.vault_id == vault_id)).all()
    deadlines = session.exec(select(Deadline).where(Deadline.vault_id == vault_id)).all()

    return render_evidence_packet(
        vault,
        events,
        flags,
        deadlines,
        party=party,
        vault_name=vault.label or vault.id,
        documents_by_event=_group_documents(documents),
        deadline_descriptions={
            d.id: describe_deadline(d, request.app.state.statutes, party) for d in deadlines
        },
    )


def _group_documents(documents) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for doc in documents:
        grouped.setdefault(doc.event_id, []).append(doc)
    return grouped
