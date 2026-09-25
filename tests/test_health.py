from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_statutes_excludes_drafts():
    with TestClient(app) as client:
        res = client.get("/api/statutes")
    assert res.status_code == 200
    rules = res.json()
    assert all(r["status"] == "verified" for r in rules)
    assert any(r["id"] == "no_rental_license" for r in rules)
    assert not any(r["id"] == "habitability_waiver" for r in rules)


def test_vault_create_and_event_flow():
    with TestClient(app) as client:
        created = client.post("/api/vaults", json={"label": "test tenancy", "zip_code": "19121"})
        assert created.status_code == 200
        vault_id = created.json()["id"]

        event = client.post(
            f"/api/vaults/{vault_id}/events",
            json={"event_type": "repair_requested", "occurred_at": "2026-03-14", "facts": {"issue": "leak"}},
        )
        assert event.status_code == 200

        events = client.get(f"/api/vaults/{vault_id}/events")
        assert events.status_code == 200
        assert len(events.json()) == 1
