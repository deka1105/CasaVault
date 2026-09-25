from pathlib import Path
from typing import Optional

from app.config import BASE_DIR, BLOB_READ_WRITE_TOKEN, UPLOADS_DIR

# Storage refs are prefixed so read()/delete() never have to guess which
# backend wrote them, regardless of the current environment's config.
_BLOB_PREFIX = "blob:"


def _blob_enabled() -> bool:
    return bool(BLOB_READ_WRITE_TOKEN)


def save_temp(vault_id: str, filename: str, content: bytes) -> Path:
    """Writes incoming upload bytes to a local path so app/extractor.py can
    keep reading a plain Path regardless of the durable backend. Locally
    this path IS the durable store (persist() below is a no-op copy of it);
    on Vercel, set UPLOADS_DIR to a /tmp path — persist() then uploads these
    bytes to Blob and the temp copy can be reclaimed by the platform."""
    vault_dir = UPLOADS_DIR / vault_id
    vault_dir.mkdir(parents=True, exist_ok=True)
    dest = vault_dir / filename
    dest.write_bytes(content)
    return dest


def persist(temp_path: Path, vault_id: str) -> str:
    """Returns the durable storage_ref to save on VaultEvent.source_document_ref."""
    if not _blob_enabled():
        # Prefer a project-relative ref so the database stays portable across
        # machines, but UPLOADS_DIR is explicitly allowed to point anywhere
        # (on Vercel it must — /tmp is the only writable path). relative_to()
        # raises ValueError for any path outside BASE_DIR, which used to make
        # every upload 500 under that configuration; fall back to an absolute
        # ref instead. read()/delete() below handle both, since
        # `BASE_DIR / "/abs/path"` already resolves to the absolute path.
        try:
            return str(temp_path.relative_to(BASE_DIR))
        except ValueError:
            return str(temp_path)

    import vercel.blob as blob

    pathname = f"vaults/{vault_id}/{temp_path.name}"
    # add_random_suffix=False: app/documents.py already generates a unique
    # random on-disk name, so a second random suffix from Blob is redundant.
    result = blob.put(pathname, temp_path.read_bytes(), access="private", add_random_suffix=False)
    return f"{_BLOB_PREFIX}{result.pathname}"


def read(storage_ref: str) -> Optional[bytes]:
    """Returns the file's bytes, or None if it doesn't exist under this ref."""
    if storage_ref.startswith(_BLOB_PREFIX):
        import vercel.blob as blob
        from vercel.blob import BlobNotFoundError

        pathname = storage_ref[len(_BLOB_PREFIX):]
        try:
            result = blob.get(pathname, access="private")
        except BlobNotFoundError:
            return None
        return result.content

    path = BASE_DIR / storage_ref
    if not path.is_file():
        return None
    return path.read_bytes()


def delete(storage_ref: str) -> None:
    if storage_ref.startswith(_BLOB_PREFIX):
        import vercel.blob as blob

        blob.delete(storage_ref[len(_BLOB_PREFIX):])
        return

    (BASE_DIR / storage_ref).unlink(missing_ok=True)
