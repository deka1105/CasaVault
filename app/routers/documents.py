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
from app.extractor import (
    ExtractionRateLimited,
    ExtractionUnavailable,
    ExtractionUnsupported,
    ExtractionUpstreamError,
    classify_extraction_error,
    extract_facts_from_file,
)
from app.models import Vault, VaultEvent
from app.rules_engine import adjudicate_vault
from app.schemas import DocumentUploadRead, EventRead, ExtractionInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vaults/{vault_id}/documents", tags=["documents"])


def _info(log, vault_id, exc):
    log.info("extraction skipped for vault %s: %s", vault_id, exc)


def _warn(log, vault_id, exc):
    log.warning("extraction unavailable for vault %s: %s", vault_id, exc)


def _exception(log, vault_id, exc):
    log.exception("extraction failed for an upload in vault %s: %s", vault_id, exc)


def _silent(log, vault_id, exc):
    pass  # no key configured: the expected state in dev, not worth a log line


# exception type -> (status, user-facing message, how to log it)
_EXTRACTION_OUTCOMES = {
    ExtractionUnavailable: (
        "not_configured",
        "Automatic reading is not configured on this deployment. The document is stored; enter any known facts by hand.",
        _silent,
    ),
    ExtractionUnsupported: (
        "unsupported_type",
        "This file type can't be read automatically. It is stored, and you can log its facts by hand.",
        _info,
    ),
    ExtractionRateLimited: (
        "rate_limited",
        "The daily limit for automatic document reading has been reached. Your document is stored — add its facts by hand, or try again tomorrow.",
        _warn,
    ),
    ExtractionUpstreamError: (
        "upstream_error",
        "The document reader was temporarily unreachable. Your document is stored — try re-uploading shortly, or add its facts by hand.",
        _warn,
    ),
    None: (
        "failed",
        "The document couldn't be read automatically. It is stored — add its facts by hand.",
        _exception,
    ),
}


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


@router.post("", response_model=DocumentUploadRead)
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
            raise HTTPException(
                status_code=413,
                detail=f"file too large (limit {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    temp_path = storage.save_temp(vault_id, name, content)

    # One dispatch point for every way reading a document can fail. Each
    # outcome stores the document and leaves facts empty — extraction is
    # strictly best-effort — but each says something different to the user,
    # because "this document stated nothing we track" and "the daily model
    # quota ran out" look identical from an empty facts dict, and the second
    # one reads as a broken product during a demo.
    facts = None
    try:
        facts = extract_facts_from_file(temp_path)
        extraction = ExtractionInfo(
            status="ok" if facts else "no_facts",
            message=None if facts else "The document was read, but it stated none of the facts this vault tracks.",
        )
    except Exception as raw:
        # classify() is applied here as well as inside the extractor so a
        # provider error raised from any path lands in the right bucket,
        # rather than only the ones the extractor itself wrapped.
        exc = classify_extraction_error(raw)
        status, message, log = _EXTRACTION_OUTCOMES.get(type(exc), _EXTRACTION_OUTCOMES[None])
        log(logger, vault_id, exc)
        extraction = ExtractionInfo(status=status, message=message)

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

    # model_validate(..., from_attributes=True) rather than
    # event.model_dump(): on a refreshed SQLModel row, model_dump() omits
    # attributes SQLAlchemy has expired and never had explicitly set, so
    # fields like `notes` went missing and failed validation. Going through
    # attribute access triggers the load.
    return DocumentUploadRead(
        **EventRead.model_validate(event, from_attributes=True).model_dump(),
        extraction=extraction,
    )


def build_document_response(vault_id: str, event_id: int, session: Session) -> Response:
    """Shared by the owner route below and the token-addressed read-only
    route in app/routers/share.py, so both download paths enforce the same
    vault-scoping check and the same attachment-only serving rules."""
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
        headers={
            "Content-Disposition": _content_disposition(download_name),
            # Belt-and-braces against content sniffing overriding the
            # octet-stream type on an uploaded .html/.svg masquerading as an
            # allowed extension.
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{event_id}")
def download_document(vault_id: str, event_id: int, session: Session = Depends(get_session)) -> Response:
    _require_vault(vault_id, session)
    return build_document_response(vault_id, event_id, session)
