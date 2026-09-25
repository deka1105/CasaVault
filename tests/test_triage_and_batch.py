"""Multi-document uploads and the triage that makes them affordable.

Built against a real Philadelphia lease: 25 PDFs, 102 pages, 8.8MB, from a
professionally-managed building. The filenames below are that bundle's.
"""

from fastapi.testclient import TestClient

from app import triage
from app.main import app
from app.routers import documents as documents_router

REAL_LEASE_BUNDLE = [
    "Form__ADDENDUM_FOR_RENT_CONCESSION_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__ADDENDUM_REGARDING_MARIJUANA_USE_AND_LANDLORDS_COMMITMENT_TO_ENFORCEMENT.pdf",
    "Form__ALL-IN-ONE_UTILITY_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__APARTMENT_LEASE_FORM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__BED_BUG_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__CITY_OF_PHILADELPHIA_BED_BUG_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__CITY_OF_PHILADELPHIA_BED_BUG_BROCHURE__A_GUIDE_TO_BED_BUG_SAFETY.pdf",
    "Form__CLASS_ACTION_WAIVER_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__CRIME_DRUG_FREE_HOUSING_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__INVENTORY_AND_CONDITION_FORM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__LEASE_CONTRACT_BUY-OUT_AGREEMENT_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__MASTER_ADDENDUM_AND_COMMUNITY_POLICIES_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__MOLD_INFORMATION_AND_PREVENTION_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__NO-SMOKING_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__PHILADELPHIA_ACKNOWLEDGMENT_OF_RECEIPT_OF_REQUIRED_DOCUMENTS.pdf",
    "Form__PHILADELPHIA_LEAD_DISCLOSURE_AND_CERTIFICATION_ADDENDUM.pdf",
    "Form__PHILADELPHIA_PARTNERS_FOR_GOOD_HOUSING_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__REMOTE_CONTROL_CARD_OR_CODE_ACCESS_GATE_ADDENDUM.pdf",
    "Form__RESIDENT_FEES_DISCLOSURE_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__Resident_Insurance_-_Leasing_Desk_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__SATELLITE_DISH_OR_ANTENNA_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Form__SERVICEMEMBERS_CIVIL_RELIEF_ACT_ADDENDUM.pdf",
    "Form__SHORT-TERM_SUBLETTING_OR_RENTAL_PROHIBITED.pdf",
    "Form__SUSTAINABLE_LIVING_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf",
    "Summary.pdf",
]


# --- triage ---------------------------------------------------------------

def test_a_real_lease_bundle_costs_far_fewer_requests_than_it_has_files():
    """The free tier allows 20 model requests per DAY. Reading all 25 files
    would spend more than a day's quota on one lease."""
    decisions = triage.plan(REAL_LEASE_BUNDLE)
    read = sum(1 for d in decisions if d.extract)
    assert len(decisions) == 25
    assert read < 20, "a single lease must not exhaust the daily quota"
    assert read >= 6, "but the documents that carry the terms must still be read"


def test_the_documents_carrying_the_terms_are_always_read():
    decisions = dict(zip(REAL_LEASE_BUNDLE, triage.plan(REAL_LEASE_BUNDLE)))
    for name in (
        "Form__APARTMENT_LEASE_FORM_-_Lease_5_12_2026_to_8_11_2027.pdf",
        "Form__PHILADELPHIA_ACKNOWLEDGMENT_OF_RECEIPT_OF_REQUIRED_DOCUMENTS.pdf",
        "Form__INVENTORY_AND_CONDITION_FORM_-_Lease_5_12_2026_to_8_11_2027.pdf",
        "Form__RESIDENT_FEES_DISCLOSURE_-_Lease_5_12_2026_to_8_11_2027.pdf",
    ):
        assert decisions[name].extract, f"{name} carries the terms and must be read"


def test_waiver_documents_are_read_even_though_they_are_addenda():
    """statutes.yaml calls deposit_waiver_void the high-value flag — "void on
    its face, detectable by extraction alone". The real lease buries
    "Resident Waives Right to Withhold Rent" in the master addendum, so
    ranking the secondary budget alphabetically skipped exactly the file that
    mattered."""
    decisions = dict(zip(REAL_LEASE_BUNDLE, triage.plan(REAL_LEASE_BUNDLE)))
    assert decisions["Form__MASTER_ADDENDUM_AND_COMMUNITY_POLICIES_-_Lease_5_12_2026_to_8_11_2027.pdf"].extract
    assert decisions["Form__CLASS_ACTION_WAIVER_ADDENDUM_-_Lease_5_12_2026_to_8_11_2027.pdf"].extract


def test_city_literature_and_the_signing_audit_trail_are_never_read():
    """These are identical for every tenant in Philadelphia (or, for the
    DocuSign certificate, contain only names, emails and signer IPs) — no
    facts about this tenancy, so no request should be spent on them."""
    decisions = dict(zip(REAL_LEASE_BUNDLE, triage.plan(REAL_LEASE_BUNDLE)))
    for name in (
        "Form__PHILADELPHIA_PARTNERS_FOR_GOOD_HOUSING_-_Lease_5_12_2026_to_8_11_2027.pdf",
        "Form__CITY_OF_PHILADELPHIA_BED_BUG_BROCHURE__A_GUIDE_TO_BED_BUG_SAFETY.pdf",
        "Summary.pdf",
    ):
        assert decisions[name].category == triage.SKIP
        assert not decisions[name].extract


def test_a_single_file_uploaded_alone_is_always_read():
    """Triage is a budget for bundles. One deliberately chosen file is not a
    bundle, and silently declining to read it would be a bug."""
    assert triage.plan(["Summary.pdf"], secondary_budget=0)[0].extract is False
    # ...but with no manifest at all, the upload path reads it unconditionally:
    assert documents_router._decide_triage("anything.pdf", None, None).extract


# --- batch upload ---------------------------------------------------------

def _upload(client, vault_id, name, *, manifest=None, index=None, event_id=None):
    data = {"occurred_at": "2026-05-11", "event_type": "lease_signed"}
    if manifest is not None:
        data["manifest"] = manifest
        data["index"] = str(index)
    if event_id is not None:
        data["event_id"] = str(event_id)
    return client.post(
        f"/api/vaults/{vault_id}/documents",
        files={"file": (name, b"%PDF-1.4 fake", "application/pdf")},
        data=data,
    )


def test_a_lease_bundle_becomes_one_timeline_event(monkeypatch):
    """25 files used to mean 25 timeline rows and 25 date pickers."""
    monkeypatch.setattr(documents_router, "extract_facts_from_file", lambda _p: {})
    import json

    manifest = json.dumps(REAL_LEASE_BUNDLE)
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"label": "bundle"}).json()
        event_id = None
        for i, name in enumerate(REAL_LEASE_BUNDLE):
            res = _upload(client, vault["id"], name, manifest=manifest, index=i, event_id=event_id)
            assert res.status_code == 200, res.text
            event_id = res.json()["id"]

        events = client.get(f"/api/vaults/{vault['id']}/events").json()

    assert len(events) == 1, "one signing, one timeline entry"
    assert len(events[0]["documents"]) == 25, "every file is still attached and downloadable"
    not_read = [d for d in events[0]["documents"] if d["extraction_status"] == "not_read"]
    assert not_read, "the skipped files must say so rather than look examined"


def test_facts_from_later_files_in_a_bundle_merge_into_the_same_event(monkeypatch):
    """The deposit comes from the lease form, the certificate acknowledgement
    from a different PDF. Both have to land on one event or the rules engine
    sees a half-filled tenancy."""
    facts_by_call = iter([{"deposit_amount": 500.0}, {"certificate_of_rental_suitability_provided": True}])
    monkeypatch.setattr(documents_router, "extract_facts_from_file", lambda _p: next(facts_by_call, {}))

    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        first = _upload(client, vault["id"], "APARTMENT_LEASE_FORM.pdf")
        event_id = first.json()["id"]
        _upload(client, vault["id"], "ACKNOWLEDGMENT_OF_REQUIRED_DOCUMENTS.pdf", event_id=event_id)

        events = client.get(f"/api/vaults/{vault['id']}/events").json()

    assert len(events) == 1
    assert events[0]["facts"] == {
        "deposit_amount": 500.0,
        "certificate_of_rental_suitability_provided": True,
    }


def test_documents_are_downloadable_by_their_own_id(monkeypatch):
    monkeypatch.setattr(documents_router, "extract_facts_from_file", lambda _p: {})
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        first = _upload(client, vault["id"], "APARTMENT_LEASE_FORM.pdf")
        event_id = first.json()["id"]
        _upload(client, vault["id"], "SECOND.pdf", event_id=event_id)

        events = client.get(f"/api/vaults/{vault['id']}/events").json()
        docs = events[0]["documents"]
        assert len(docs) == 2
        for doc in docs:
            res = client.get(f"/api/vaults/{vault['id']}/documents/{doc['id']}")
            assert res.status_code == 200
            assert res.content == b"%PDF-1.4 fake"
            assert res.headers["content-disposition"].startswith("attachment")


def test_a_bundle_cannot_be_attached_to_another_vaults_event(monkeypatch):
    """event_id is client-supplied, so it must be scoped to the vault in the
    path or one vault's upload could be filed into another's timeline."""
    monkeypatch.setattr(documents_router, "extract_facts_from_file", lambda _p: {})
    with TestClient(app) as client:
        mine = client.post("/api/vaults", json={}).json()
        theirs = client.post("/api/vaults", json={}).json()
        their_event = _upload(client, theirs["id"], "THEIRS.pdf").json()["id"]

        res = _upload(client, mine["id"], "MINE.pdf", event_id=their_event)

    assert res.status_code == 404


def test_share_view_shows_every_document_in_a_bundle(monkeypatch):
    monkeypatch.setattr(documents_router, "extract_facts_from_file", lambda _p: {})
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        first = _upload(client, vault["id"], "APARTMENT_LEASE_FORM.pdf")
        _upload(client, vault["id"], "SECOND.pdf", event_id=first.json()["id"])

        token = vault["share_token"]
        events = client.get(f"/api/vaults/by-share-token/{token}/events").json()
        doc_id = events[0]["documents"][1]["id"]
        download = client.get(f"/api/vaults/by-share-token/{token}/documents/{doc_id}")
        packet = client.get(f"/api/vaults/by-share-token/{token}/evidence")

    assert len(events[0]["documents"]) == 2
    assert download.status_code == 200
    # The shared packet lists both files, on token-addressed links only.
    assert packet.text.count("/documents/") == 2
    assert vault["id"] not in packet.text
