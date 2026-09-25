import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import documents
from app.config import UPLOADS_DIR
from app.extraction_schema import ExtractedFacts
from app.extractor import ExtractionUnsupported, _content_block_for_file
from app.main import app
from app.routers import documents as documents_router


@pytest.fixture(autouse=True)
def _clean_uploads():
    yield
    shutil.rmtree(UPLOADS_DIR, ignore_errors=True)


def _make_vault(client: TestClient) -> str:
    return client.post("/api/vaults", json={}).json()["id"]


def test_content_block_maps_pdf_and_image_and_rejects_docx(tmp_path):
    pdf_block = _content_block_for_file(Path("lease.pdf"))
    assert pdf_block == {"type": "document", "data": Path("lease.pdf"), "mime_type": "application/pdf"}

    image_block = _content_block_for_file(Path("photo.jpg"))
    assert image_block["type"] == "image"
    assert image_block["mime_type"] == "image/jpeg"

    txt_path = tmp_path / "notes.txt"
    txt_path.write_text("tenant reported a leak")
    text_block = _content_block_for_file(txt_path)
    assert text_block == {"type": "text", "text": "tenant reported a leak"}

    with pytest.raises(ExtractionUnsupported):
        _content_block_for_file(Path("lease.docx"))


def test_extraction_schema_round_trips_partial_facts():
    facts = ExtractedFacts(deposit_amount=1200, landlord_rental_license_valid=False)
    dumped = facts.model_dump(exclude_none=True)
    assert dumped == {"deposit_amount": 1200, "landlord_rental_license_valid": False}


def test_upload_without_gemini_key_leaves_facts_empty(monkeypatch):
    # Force the no-key path explicitly — a real key may be configured in
    # this environment's .env, and this test must not make a live API call.
    monkeypatch.setattr("app.extractor.GEMINI_API_KEY", None)
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        res = client.post(
            f"/api/vaults/{vault_id}/documents",
            data={"occurred_at": "2026-03-01"},
            files={"file": ("lease.pdf", b"%PDF-1.4 fake lease", "application/pdf")},
        )
    assert res.status_code == 200
    assert res.json()["facts"] == {}


def test_upload_with_mocked_extraction_populates_facts_and_adjudicates(monkeypatch):
    def fake_extract(path):
        return {"landlord_rental_license_valid": False}

    monkeypatch.setattr("app.routers.documents.extract_facts_from_file", fake_extract)

    with TestClient(app) as client:
        vault_id = _make_vault(client)
        res = client.post(
            f"/api/vaults/{vault_id}/documents",
            data={"occurred_at": "2026-03-01"},
            files={"file": ("lease.pdf", b"%PDF-1.4 fake lease", "application/pdf")},
        )
        assert res.status_code == 200
        assert res.json()["facts"] == {"landlord_rental_license_valid": False}

        flags = client.get(f"/api/vaults/{vault_id}/flags").json()
    assert any(f["statute_id"] == "no_rental_license" for f in flags)


def test_upload_survives_extraction_raising(monkeypatch):
    def boom(path):
        raise RuntimeError("simulated API outage")

    monkeypatch.setattr("app.routers.documents.extract_facts_from_file", boom)

    with TestClient(app) as client:
        vault_id = _make_vault(client)
        res = client.post(
            f"/api/vaults/{vault_id}/documents",
            data={"occurred_at": "2026-03-01"},
            files={"file": ("lease.pdf", b"%PDF-1.4 fake lease", "application/pdf")},
        )
    assert res.status_code == 200
    assert res.json()["facts"] == {}


# --- an upload must say WHY it extracted nothing --------------------------

def _upload(client, vault_id, body=b"a notice"):
    return client.post(
        f"/api/vaults/{vault_id}/documents",
        files={"file": ("notice.txt", body, "text/plain")},
        data={"occurred_at": "2026-02-01"},
    )


def test_upload_reports_rate_limiting_rather_than_silently_empty_facts(monkeypatch):
    """The free tier's daily cap is 20 requests. Hitting it used to look
    identical to a document that genuinely stated nothing — during a demo
    that reads as a broken product, not a quota."""
    def boom(_path):
        raise RuntimeError(
            "Error code: 429 - Rate limit exceeded for model gemini-3.8-flash "
            "(limit: 20 requests per day on Free Tier)"
        )

    monkeypatch.setattr(documents_router, "extract_facts_from_file", boom)

    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        res = _upload(client, vault["id"])

    assert res.status_code == 200, "the upload itself must still succeed"
    body = res.json()
    assert body["facts"] == {}
    assert body["source_document_ref"], "the document is stored regardless"
    assert body["extraction"]["status"] == "rate_limited"
    assert "daily limit" in body["extraction"]["message"]


def test_upload_distinguishes_a_transient_outage_from_a_quota_limit(monkeypatch):
    monkeypatch.setattr(
        documents_router,
        "extract_facts_from_file",
        lambda _p: (_ for _ in ()).throw(RuntimeError("Error code: 503 - service_unavailable, high demand")),
    )
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        res = _upload(client, vault["id"])
    assert res.json()["extraction"]["status"] == "upstream_error"


def test_upload_of_a_document_stating_nothing_is_reported_as_no_facts(monkeypatch):
    monkeypatch.setattr(documents_router, "extract_facts_from_file", lambda _p: {})
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        res = _upload(client, vault["id"])
    info = res.json()["extraction"]
    assert info["status"] == "no_facts"
    assert "stated none" in info["message"]


def test_successful_extraction_is_reported_as_ok(monkeypatch):
    monkeypatch.setattr(
        documents_router,
        "extract_facts_from_file",
        lambda _p: {"landlord_rental_license_valid": False},
    )
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        res = _upload(client, vault["id"])
        flags = client.get(f"/api/vaults/{vault['id']}/flags").json()

    assert res.json()["extraction"]["status"] == "ok"
    assert any(f["statute_id"] == "no_rental_license" for f in flags)


def test_oversized_upload_is_rejected_with_a_readable_limit():
    """Capped below Vercel's 4.5MB request-body limit so the rejection comes
    from here, with a reason, instead of an opaque platform error."""
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        res = _upload(client, vault["id"], body=b"x" * (documents.MAX_UPLOAD_BYTES + 1))
    assert res.status_code == 413
    assert "limit" in res.json()["detail"]
