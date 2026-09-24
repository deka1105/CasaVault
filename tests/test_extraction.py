import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import UPLOADS_DIR
from app.extraction_schema import ExtractedFacts
from app.extractor import ExtractionUnsupported, _content_block_for_file
from app.main import app


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


def test_upload_without_gemini_key_leaves_facts_empty():
    # No GEMINI_API_KEY is set in this test environment — extraction should
    # no-op rather than fail the upload.
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
