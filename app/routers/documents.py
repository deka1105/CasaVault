import logging
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.config import BASE_DIR, UPLOADS_DIR
from app.database import get_session
from app.documents import MAX_UPLOAD_BYTES, UploadRejected, stored_filename
from app.extractor import ExtractionUnavailable, ExtractionUnsupported, extract_facts_from_file
from app.models import Vault, VaultEvent
from app.rules_engine import adjudicate_vault
from app.schemas import EventRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vaults/{vault_id}/documents", tags=["documents"])


def _require_vault(vault_id: str, session: Session) -> Vault:
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault


@router.post("", response_model=EventRead)
async def upload_document(
    vault_id: str,
    request: Request,
    file: UploadFile = File(...),
    occurred_at: date = Form(...),
    notes: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Stores the file, then runs it through the schema-bound extractor
    (app/extractor.py) and adjudicates the vault if that produced any
    facts. Extraction is best-effort: no configured key, an unsupported
    file type, or an API error all fall back to an empty facts dict rather
    than failing the upload — the document is safely stored either way."""
    _require_vault(vault_id, session)

    try:
        name = stored_filename(file.filename or "")
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    vault_dir = UPLOADS_DIR / vault_id
    vault_dir.mkdir(parents=True, exist_ok=True)
    dest = vault_dir / name

    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="file too large")
            out.write(chunk)

    event = VaultEvent(
        vault_id=vault_id,
        event_type="document_upload",
        occurred_at=occurred_at,
        facts={},
        source_document_ref=str(dest.relative_to(BASE_DIR)),
        original_filename=Path(file.filename).name if file.filename else None,
        notes=notes,
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    try:
        facts = extract_facts_from_file(dest)
    except ExtractionUnavailable:
        facts = None  # no key configured — expected in dev, not an error
    except ExtractionUnsupported as exc:
        logger.info("skipping extraction for event %s: %s", event.id, exc)
        facts = None
    except Exception:
        logger.exception("extraction failed for event %s", event.id)
        facts = None

    if facts:
        event.facts = facts
        session.add(event)
        session.commit()
        session.refresh(event)
        adjudicate_vault(vault_id, session, request.app.state.statutes)

    return event


@router.get("/{event_id}")
def download_document(vault_id: str, event_id: int, session: Session = Depends(get_session)):
    _require_vault(vault_id, session)
    event = session.get(VaultEvent, event_id)
    if event is None or event.vault_id != vault_id or not event.source_document_ref:
        raise HTTPException(status_code=404, detail="document not found")

    path = BASE_DIR / event.source_document_ref
    if not path.is_file():
        raise HTTPException(status_code=404, detail="document not found")

    # content_disposition_type="attachment" (the default) matters here: an
    # uploaded .txt/.pdf served inline under this origin would otherwise be
    # a stored-content risk in the browser. filename is the original name
    # for the download prompt — the on-disk name stays the random one.
    download_name = event.original_filename or Path(event.source_document_ref).name
    return FileResponse(path, filename=download_name)
