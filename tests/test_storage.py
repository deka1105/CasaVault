import shutil

import pytest

import app.storage as storage
from app.config import UPLOADS_DIR


@pytest.fixture(autouse=True)
def _clean_uploads():
    yield
    shutil.rmtree(UPLOADS_DIR, ignore_errors=True)


def test_local_backend_round_trip():
    temp_path = storage.save_temp("vault1", "lease.pdf", b"hello world")
    assert temp_path.exists()

    ref = storage.persist(temp_path, "vault1")
    assert not ref.startswith("blob:")

    assert storage.read(ref) == b"hello world"

    storage.delete(ref)
    assert storage.read(ref) is None


def test_read_missing_local_ref_returns_none():
    assert storage.read("uploads/does-not-exist/nope.pdf") is None


def test_blob_backend_persist_uses_private_access_and_no_extra_suffix(monkeypatch):
    monkeypatch.setattr("app.storage.BLOB_READ_WRITE_TOKEN", "test-token")

    class FakePutResult:
        pathname = "vaults/vault1/lease.pdf"

    calls = []

    def fake_put(pathname, data, **kwargs):
        calls.append((pathname, data, kwargs))
        return FakePutResult()

    import vercel.blob as blob

    monkeypatch.setattr(blob, "put", fake_put)

    temp_path = storage.save_temp("vault1", "lease.pdf", b"hello world")
    ref = storage.persist(temp_path, "vault1")

    assert ref == "blob:vaults/vault1/lease.pdf"
    pathname, data, kwargs = calls[0]
    assert pathname == "vaults/vault1/lease.pdf"
    assert data == b"hello world"
    assert kwargs["access"] == "private"
    assert kwargs["add_random_suffix"] is False


def test_blob_backend_read_returns_content(monkeypatch):
    monkeypatch.setattr("app.storage.BLOB_READ_WRITE_TOKEN", "test-token")

    class FakeGetResult:
        content = b"hello from blob"

    import vercel.blob as blob

    monkeypatch.setattr(blob, "get", lambda pathname, **kwargs: FakeGetResult())

    assert storage.read("blob:vaults/vault1/lease.pdf") == b"hello from blob"


def test_blob_backend_read_not_found_returns_none(monkeypatch):
    monkeypatch.setattr("app.storage.BLOB_READ_WRITE_TOKEN", "test-token")

    import vercel.blob as blob
    from vercel.blob import BlobNotFoundError

    def fake_get(pathname, **kwargs):
        raise BlobNotFoundError()

    monkeypatch.setattr(blob, "get", fake_get)

    assert storage.read("blob:vaults/vault1/missing.pdf") is None


def test_blob_backend_delete_calls_blob_delete(monkeypatch):
    monkeypatch.setattr("app.storage.BLOB_READ_WRITE_TOKEN", "test-token")

    import vercel.blob as blob

    calls = []
    monkeypatch.setattr(blob, "delete", lambda pathname, **kwargs: calls.append(pathname))

    storage.delete("blob:vaults/vault1/lease.pdf")
    assert calls == ["vaults/vault1/lease.pdf"]
