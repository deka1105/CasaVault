import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.agent import AgentRateLimited, AgentUnavailable, AgentUpstreamError, ask_agent
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
    handoff = handoff_for_zip(table.right_to_counsel, vault.zip_code)

    # Three distinct safe outcomes. None of them ever guesses; saying which
    # one happened is the difference between a user trusting the refusal and
    # a user filing a bug report about it.
    try:
        result = ask_agent(payload.question, payload.party, vault_id, session, table)
    except AgentUnavailable:
        return AskResponse(
            refusal=(
                "The grounded agent isn't configured on this deployment, so I can't "
                "answer from your vault or the statute table. I won't guess."
            ),
            handoff=handoff,
            unavailable=True,
        )
    except AgentRateLimited:
        logger.warning("agent quota exhausted for vault %s", vault_id)
        return AskResponse(
            refusal=(
                "The daily limit for asking questions has been reached on this "
                "deployment, so I have no grounded answer to give you right now. "
                "Your record and its findings are unaffected."
            ),
            handoff=handoff,
            unavailable=True,
        )
    except AgentUpstreamError:
        logger.warning("agent upstream unavailable for vault %s", vault_id)
        return AskResponse(
            refusal=(
                "I couldn't reach the language model just now, so I have no grounded "
                "answer to give you. This is a temporary service problem on our side, "
                "not a limit on what your record says — try again in a moment."
            ),
            handoff=handoff,
            unavailable=True,
        )
    except Exception:
        logger.exception("agent call failed for vault %s", vault_id)
        return AskResponse(
            refusal=(
                "Something went wrong answering that, so I won't offer a guess. "
                "Your record is unaffected."
            ),
            handoff=handoff,
            unavailable=True,
        )

    if not result.grounded:
        # The designed behaviour: the question can't be grounded in the vault
        # or the statute table, so the agent declines and routes to a human.
        return AskResponse(refusal=result.refusal_reason, handoff=handoff)

    return AskResponse(answer=result.answer, citation=result.citation_display)
