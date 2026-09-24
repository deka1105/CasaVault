from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.database import get_session
from app.models import Vault
from app.rtc import handoff_for_zip
from app.schemas import AskRequest, AskResponse

router = APIRouter(prefix="/api/vaults/{vault_id}/ask", tags=["agent"])


@router.post("", response_model=AskResponse)
def ask(vault_id: str, payload: AskRequest, request: Request, session: Session = Depends(get_session)):
    """Stub grounded-agent endpoint.

    The real agent (retrieval limited to this vault's events + verified
    statute rows, mandatory citation, structural refusal — see PLAN.md /
    CLAUDE.md) is not implemented yet. Until it is, this endpoint must not
    fabricate an answer: it always refuses and hands off, which is the
    correct behavior with no grounding available, not a placeholder shortcut.
    """
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")

    return AskResponse(
        answer=None,
        citation=None,
        refusal="The grounded agent isn't wired up yet, so I can't answer from your vault or the statute table. I won't guess.",
        handoff=handoff_for_zip(request.app.state.statutes.right_to_counsel, vault.zip_code),
    )
