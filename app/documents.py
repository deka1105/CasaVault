import uuid
from pathlib import Path

# Lease PDFs, notices, receipts, inspection photos — matches the artifact
# types PLAN.md describes. Deliberately not arbitrary: this app is deployed
# to a public URL, and an upload endpoint that stores anything is a real
# attack surface (stored content served back to a browser under this origin).
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".txt", ".docx"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


class UploadRejected(ValueError):
    pass


def stored_filename(original_name: str) -> str:
    """Never trust the client's filename or path — take only the extension
    and generate a fresh name, so path traversal and collisions are both
    impossible by construction."""
    ext = Path(original_name or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadRejected(f"unsupported file type: {ext or '(none)'}")
    return f"{uuid.uuid4().hex}{ext}"
