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


def test_share_token_lookup_matches_vault():
    with TestClient(app) as client:
        vault = _make_vault(client, label="test tenancy")
        res = client.get(f"/api/vaults/by-share-token/{vault['share_token']}")
    assert res.status_code == 200
    assert res.json()["id"] == vault["id"]


def test_acknowledge_sets_timestamp_once_and_first_click_wins():
    with TestClient(app) as client:
        vault = _make_vault(client)
        assert vault["acknowledged_at"] is None

        first = client.post(f"/api/vaults/by-share-token/{vault['share_token']}/acknowledge")
        assert first.status_code == 200
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
