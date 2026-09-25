from fastapi.testclient import TestClient

from app.main import app


def _make_vault(client: TestClient, **kwargs) -> dict:
    res = client.post("/api/vaults", json=kwargs)
    assert res.status_code == 200
    return res.json()


def test_rtc_check_routes_covered_zip_to_hotline():
    with TestClient(app) as client:
        vault = _make_vault(client, zip_code="19121")
        res = client.get(f"/api/vaults/{vault['id']}/rtc-check")
    assert res.status_code == 200
    assert res.json()["route"] == "hotline"


def test_rtc_check_routes_uncovered_zip_to_fallback():
    with TestClient(app) as client:
        vault = _make_vault(client, zip_code="19107")
        res = client.get(f"/api/vaults/{vault['id']}/rtc-check")
    assert res.status_code == 200
    assert res.json()["route"] == "phillytenant_org"


def test_share_token_lookup_returns_vault_without_leaking_owner_credential():
    """The share link must not yield the vault id. The id is the only
    credential the write routes check, so returning it here would have made
    the 'read-only' counterparty link a full write credential — the browser
    hiding the controls was the only thing stopping a counterparty from
    posting events into someone else's vault."""
    with TestClient(app) as client:
        vault = _make_vault(client, label="test tenancy")
        res = client.get(f"/api/vaults/by-share-token/{vault['share_token']}")
    assert res.status_code == 200
    body = res.json()
    assert body["label"] == "test tenancy"
    assert "id" not in body
    assert "share_token" not in body
    assert vault["id"] not in res.text


def test_share_token_read_only_surface_serves_the_vault_record():
    with TestClient(app) as client:
        vault = _make_vault(client, label="123 Elm St", zip_code="19121")
        client.post(
            f"/api/vaults/{vault['id']}/events",
            json={
                "event_type": "repair_requested",
                "occurred_at": "2026-03-14",
                "facts": {"landlord_rental_license_valid": False},
                "notes": "kitchen leak",
            },
        )
        token = vault["share_token"]

        events = client.get(f"/api/vaults/by-share-token/{token}/events")
        flags = client.get(f"/api/vaults/by-share-token/{token}/flags")
        deadlines = client.get(f"/api/vaults/by-share-token/{token}/deadlines")
        rtc = client.get(f"/api/vaults/by-share-token/{token}/rtc-check")
        evidence = client.get(f"/api/vaults/by-share-token/{token}/evidence")

    assert [e["notes"] for e in events.json()] == ["kitchen leak"]
    assert any(f["statute_id"] == "no_rental_license" for f in flags.json())
    assert deadlines.json() == []
    assert rtc.json()["route"] == "hotline"
    assert evidence.status_code == 200
    # The shared packet must not embed the owner credential in its links.
    assert vault["id"] not in evidence.text


def test_share_token_surface_404s_for_an_unknown_token():
    with TestClient(app) as client:
        for path in ("", "/events", "/flags", "/deadlines", "/evidence", "/rtc-check"):
            res = client.get(f"/api/vaults/by-share-token/nope{path}")
            assert res.status_code == 404, path


def test_evidence_packet_respects_the_party_framing():
    with TestClient(app) as client:
        vault = _make_vault(client, label="Framing test")
        client.post(
            f"/api/vaults/{vault['id']}/events",
            json={
                "event_type": "lease_signed",
                "occurred_at": "2026-01-01",
                "facts": {"clause_waives_deposit_rights": True},
            },
        )
        tenant = client.get(f"/api/vaults/{vault['id']}/evidence?party=tenant").text
        landlord = client.get(f"/api/vaults/{vault['id']}/evidence?party=landlord").text

    # Same rule (deposit_waiver_void), two framings — not the tenant's
    # wording printed on the landlord's own evidence packet.
    assert "This lease tries to make you waive your deposit rights" in tenant
    assert "A lease term waiving this section is unenforceable" in landlord
    assert "This lease tries to make you waive your deposit rights" not in landlord


def test_evidence_packet_rejects_an_unknown_party():
    with TestClient(app) as client:
        vault = _make_vault(client)
        res = client.get(f"/api/vaults/{vault['id']}/evidence?party=judge")
    assert res.status_code == 422


def test_acknowledge_sets_timestamp_once_and_first_click_wins():
    with TestClient(app) as client:
        vault = _make_vault(client)
        assert vault["acknowledged_at"] is None

        first = client.post(f"/api/vaults/by-share-token/{vault['share_token']}/acknowledge")
        assert first.status_code == 200
        assert "id" not in first.json()  # read-only surface, never the credential
        first_ts = first.json()["acknowledged_at"]
        assert first_ts is not None

        second = client.post(f"/api/vaults/by-share-token/{vault['share_token']}/acknowledge")
        assert second.json()["acknowledged_at"] == first_ts


def test_evidence_packet_renders_events_and_flags():
    with TestClient(app) as client:
        vault = _make_vault(client, label="123 Elm St")
        client.post(
            f"/api/vaults/{vault['id']}/events",
            json={
                "event_type": "repair_requested",
                "occurred_at": "2026-03-14",
                "facts": {"landlord_rental_license_valid": False},
                "notes": "kitchen leak",
            },
        )
        res = client.get(f"/api/vaults/{vault['id']}/evidence")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    body = res.text
    assert "123 Elm St" in body
    assert "kitchen leak" in body
    assert "Phila. Code" in body  # citation for no_rental_license
    assert "Not yet acknowledged" in body


def test_evidence_packet_404_for_unknown_vault():
    with TestClient(app) as client:
        res = client.get("/api/vaults/does-not-exist/evidence")
    assert res.status_code == 404
