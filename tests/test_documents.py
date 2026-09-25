import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import UPLOADS_DIR
from app.documents import UploadRejected, stored_filename
from app.main import app


@pytest.fixture(autouse=True)
def _clean_uploads():
    yield
    shutil.rmtree(UPLOADS_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_live_extraction(monkeypatch):
    # This file tests upload/download storage mechanics, not extraction —
    # force the no-key path so these never make a real Gemini call even if
    # a real GEMINI_API_KEY is configured in this environment's .env.
    monkeypatch.setattr("app.extractor.GEMINI_API_KEY", None)


def _make_vault(client: TestClient) -> str:
    res = client.post("/api/vaults", json={})
    assert res.status_code == 200
    return res.json()["id"]


def test_stored_filename_rejects_disallowed_extension():
    with pytest.raises(UploadRejected):
        stored_filename("malware.exe")


def test_stored_filename_strips_path_and_randomizes_name():
    name = stored_filename("../../etc/passwd.pdf")
    assert "/" not in name
    assert ".." not in name
    assert name.endswith(".pdf")


def test_upload_document_creates_event_with_document_ref():
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        res = client.post(
            f"/api/vaults/{vault_id}/documents",
            data={"occurred_at": "2026-03-01", "notes": "lease pdf"},
            files={"file": ("lease.pdf", b"%PDF-1.4 fake lease content", "application/pdf")},
        )
        assert res.status_code == 200
        event = res.json()
        assert event["event_type"] == "document_upload"
        assert event["source_document_ref"]

        download = client.get(f"/api/vaults/{vault_id}/documents/{event['id']}")
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 fake lease content"
    assert "attachment" in download.headers["content-disposition"]
    assert 'filename="lease.pdf"' in download.headers["content-disposition"]


def test_upload_rejects_disallowed_extension():
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        res = client.post(
            f"/api/vaults/{vault_id}/documents",
            data={"occurred_at": "2026-03-01"},
            files={"file": ("script.exe", b"not a real binary", "application/octet-stream")},
        )
    assert res.status_code == 400


def test_download_404_for_event_without_document():
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        event = client.post(
            f"/api/vaults/{vault_id}/events",
            json={"event_type": "repair_requested", "occurred_at": "2026-01-01", "facts": {}},
        ).json()
        res = client.get(f"/api/vaults/{vault_id}/documents/{event['id']}")
    assert res.status_code == 404


def test_download_404_for_document_in_a_different_vault():
    with TestClient(app) as client:
        vault_a = _make_vault(client)
        vault_b = _make_vault(client)
        event = client.post(
            f"/api/vaults/{vault_a}/documents",
            data={"occurred_at": "2026-03-01"},
            files={"file": ("lease.pdf", b"content", "application/pdf")},
        ).json()

        res = client.get(f"/api/vaults/{vault_b}/documents/{event['id']}")
    assert res.status_code == 404
