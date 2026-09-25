import logging
import re
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlmodel import Session

from app import storage
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


def _content_disposition(filename: str) -> str:
    # Strip CR/LF/quotes so an attacker-controlled original_filename can't
    # break out of the quoted-string or inject a header/CRLF.
    safe = re.sub(r'[\r\n"]', "", filename)
    return f'attachment; filename="{safe}"'


@router.post("", response_model=EventRead)
async def upload_document(
    vault_id: str,
    request: Request,
    file: UploadFile = File(...),
    occurred_at: date = Form(...),
    notes: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Stores the file (locally, or on Vercel Blob if BLOB_READ_WRITE_TOKEN
    is set — see app/storage.py), then runs it through the schema-bound
    extractor and adjudicates the vault if that produced any facts.
    Extraction is best-effort: no configured key, an unsupported file type,
    or an API error all fall back to an empty facts dict rather than
    failing the upload — the document is safely stored either way."""
    _require_vault(vault_id, session)

    try:
        name = stored_filename(file.filename or "")
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    size = 0
    chunks = []
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="file too large")
        chunks.append(chunk)
    content = b"".join(chunks)

    temp_path = storage.save_temp(vault_id, name, content)

    try:
        facts = extract_facts_from_file(temp_path)
    except ExtractionUnavailable:
        facts = None  # no key configured — expected in dev, not an error
    except ExtractionUnsupported as exc:
        logger.info("skipping extraction for event in vault %s: %s", vault_id, exc)
        facts = None
    except Exception:
        logger.exception("extraction failed for an upload in vault %s", vault_id)
        facts = None

    storage_ref = storage.persist(temp_path, vault_id)

    event = VaultEvent(
        vault_id=vault_id,
        event_type="document_upload",
        occurred_at=occurred_at,
        facts=facts or {},
        source_document_ref=storage_ref,
        original_filename=Path(file.filename).name if file.filename else None,
        notes=notes,
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    if facts:
        adjudicate_vault(vault_id, session, request.app.state.statutes)

    return event


@router.get("/{event_id}")
def download_document(vault_id: str, event_id: int, session: Session = Depends(get_session)):
    _require_vault(vault_id, session)
    event = session.get(VaultEvent, event_id)
    if event is None or event.vault_id != vault_id or not event.source_document_ref:
        raise HTTPException(status_code=404, detail="document not found")

    content = storage.read(event.source_document_ref)
    if content is None:
        raise HTTPException(status_code=404, detail="document not found")

    # Always served as an attachment, from bytes read through app/storage.py
    # regardless of backend: an uploaded .txt/.pdf served inline under this
    # origin would otherwise be a stored-content risk in the browser.
    download_name = event.original_filename or Path(event.source_document_ref).name
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": _content_disposition(download_name)},
    )
