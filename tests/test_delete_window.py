from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.models import VaultEvent


def test_delete_event_within_window(monkeypatch):
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        vid = vault["id"]
        event = client.post(
            f"/api/vaults/{vid}/events",
            json={"event_type": "repair_requested", "occurred_at": "2026-03-14", "facts": {}},
        ).json()

        res = client.delete(f"/api/vaults/{vid}/events/{event['id']}")
        assert res.status_code == 200
        assert res.json()["deleted"] is True

        events = client.get(f"/api/vaults/{vid}/events").json()
        assert not any(e["id"] == event["id"] for e in events)


def test_delete_event_after_window_is_rejected(monkeypatch):
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        vid = vault["id"]
        event = client.post(
            f"/api/vaults/{vid}/events",
            json={"event_type": "repair_requested", "occurred_at": "2026-03-14", "facts": {}},
        ).json()

        from app.database import get_session

        session = next(get_session())
        db_event = session.get(VaultEvent, event["id"])
        db_event.recorded_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        session.add(db_event)
        session.commit()

        res = client.delete(f"/api/vaults/{vid}/events/{event['id']}")
        assert res.status_code == 403
        assert "10 minutes" in res.json()["detail"]
