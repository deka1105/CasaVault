import os
import uuid
from pathlib import Path

# Lease PDFs, notices, receipts, inspection photos — matches the artifact
# types PLAN.md describes. Deliberately not arbitrary: this app is deployed
# to a public URL, and an upload endpoint that stores anything is a real
# attack surface (stored content served back to a browser under this origin).
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".txt", ".docx"}

# Vercel Functions cap the REQUEST BODY at 4.5MB, and that limit is enforced
# at the platform edge — a larger upload never reaches this app, so it can't
# produce our own clean 413. The previous 15MB cap was therefore a promise
# the deployment could not keep: every upload between 4.5MB and 15MB failed
# with an opaque platform error instead of a readable message. Cap below the
# platform's limit so the rejection comes from here, with a usable reason.
# Overridable for a self-hosted run where no such edge limit applies.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 4 * 1024 * 1024))


class UploadRejected(ValueError):
    pass


def events_with_documents(vault_id: str, session) -> list["EventRead"]:
    """Timeline events, each carrying its stored files.

    Done in one extra query and grouped in memory rather than through a
    SQLModel relationship: the relationship would lazy-load per event, which
    is a query per row against Neon on a serverless invocation.
    """
    from sqlmodel import select

    from app.models import VaultDocument, VaultEvent
    from app.schemas import DocumentRead, EventRead

    events = session.exec(
        select(VaultEvent).where(VaultEvent.vault_id == vault_id).order_by(VaultEvent.occurred_at)
    ).all()
    documents = session.exec(
        select(VaultDocument).where(VaultDocument.vault_id == vault_id).order_by(VaultDocument.id)
    ).all()

    by_event: dict[int, list[DocumentRead]] = {}
    for doc in documents:
        by_event.setdefault(doc.event_id, []).append(DocumentRead.model_validate(doc, from_attributes=True))

    out = []
    for event in events:
        view = EventRead.model_validate(event, from_attributes=True)
        view.documents = by_event.get(event.id, [])
        out.append(view)
    return out


def stored_filename(original_name: str) -> str:
    """Never trust the client's filename or path — take only the extension
    and generate a fresh name, so path traversal and collisions are both
    impossible by construction."""
    ext = Path(original_name or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadRejected(f"unsupported file type: {ext or '(none)'}")
    return f"{uuid.uuid4().hex}{ext}"
