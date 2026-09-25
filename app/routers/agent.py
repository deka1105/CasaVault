import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.agent import AgentUnavailable, ask_agent
from app.database import get_session
from app.models import Vault
from app.rtc import handoff_for_zip
from app.schemas import AskRequest, AskResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vaults/{vault_id}/ask", tags=["agent"])


@router.post("", response_model=AskResponse)
def ask(vault_id: str, payload: AskRequest, request: Request, session: Session = Depends(get_session)):
    """Runs the grounded agent (app/agent.py) and always falls back to a
    safe refusal + handoff — never a raw answer, never a 500 — whenever no
    key is configured or the model call fails for any reason. See CLAUDE.md
    for how citation verification actually enforces grounding here."""
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")

    table = request.app.state.statutes

    try:
        result = ask_agent(payload.question, payload.party, vault_id, session, table)
    except AgentUnavailable:
        result = None
    except Exception:
        logger.exception("agent call failed for vault %s", vault_id)
        result = None

    if result is None or not result.grounded:
        refusal = (
            result.refusal_reason
            if result is not None
            else "The grounded agent isn't configured yet, so I can't answer from your vault or the statute table. I won't guess."
        )
        return AskResponse(
            refusal=refusal,
            handoff=handoff_for_zip(table.right_to_counsel, vault.zip_code),
        )

    return AskResponse(answer=result.answer, citation=result.citation_display)
