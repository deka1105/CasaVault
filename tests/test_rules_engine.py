import pytest
from fastapi.testclient import TestClient

from app.condition_eval import UnsafeConditionError, evaluate_condition
from app.main import app


# --- condition_eval unit tests -----------------------------------------

def test_evaluate_condition_and():
    assert evaluate_condition("deposit_months > 2 AND tenancy_year == 1", {"deposit_months": 3, "tenancy_year": 1})
    assert not evaluate_condition(
        "deposit_months > 2 AND tenancy_year == 1", {"deposit_months": 2, "tenancy_year": 1}
    )


def test_evaluate_condition_missing_fact_is_false_not_error():
    assert evaluate_condition("deposit_amount > 100", {}) is False


def test_evaluate_condition_rejects_unsafe_expressions():
    with pytest.raises(UnsafeConditionError):
        evaluate_condition("__import__('os').system('echo hi') == None", {})


def test_evaluate_condition_boolean_literal():
    assert evaluate_condition("clause_waives_deposit_rights == true", {"clause_waives_deposit_rights": True})


# --- end-to-end adjudication tests --------------------------------------

def _make_vault(client: TestClient, **kwargs) -> str:
    res = client.post("/api/vaults", json=kwargs)
    assert res.status_code == 200
    return res.json()["id"]


def test_deposit_cap_flag_fires_on_matching_facts():
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        res = client.post(
            f"/api/vaults/{vault_id}/events",
            json={
                "event_type": "document_upload",
                "occurred_at": "2026-01-01",
                "facts": {"deposit_months": 3, "tenancy_year": 1},
            },
        )
        assert res.status_code == 200

        flags = client.get(f"/api/vaults/{vault_id}/flags").json()
    statute_ids = {f["statute_id"] for f in flags}
    assert "deposit_cap_year_one" in statute_ids


def test_draft_rules_never_flag_even_if_condition_is_true():
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        client.post(
            f"/api/vaults/{vault_id}/events",
            json={
                "event_type": "document_upload",
                "occurred_at": "2026-01-01",
                "facts": {"waives_implied_warranty_of_habitability": True, "lockout_or_utility_shutoff": True},
            },
        )
        flags = client.get(f"/api/vaults/{vault_id}/flags").json()
    statute_ids = {f["statute_id"] for f in flags}
    assert "habitability_waiver" not in statute_ids
    assert "self_help_eviction" not in statute_ids


def test_flags_recompute_across_events_not_just_the_latest_one():
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        client.post(
            f"/api/vaults/{vault_id}/events",
            json={"event_type": "document_upload", "occurred_at": "2026-01-01", "facts": {"deposit_amount": 500}},
        )
        client.post(
            f"/api/vaults/{vault_id}/events",
            json={
                "event_type": "notice_received",
                "occurred_at": "2026-02-01",
                "facts": {"landlord_rental_license_valid": False},
            },
        )
        flags = client.get(f"/api/vaults/{vault_id}/flags").json()
    statute_ids = {f["statute_id"] for f in flags}
    assert "deposit_escrow_required" in statute_ids  # from event 1's facts
    assert "no_rental_license" in statute_ids  # from event 2's facts


def test_move_out_with_forwarding_address_starts_deposit_clock():
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        res = client.post(
            f"/api/vaults/{vault_id}/events",
            json={
                "event_type": "move_out",
                "occurred_at": "2026-08-01",
                "facts": {"forwarding_address_provided": True},
            },
        )
        assert res.status_code == 200

        deadlines = client.get(f"/api/vaults/{vault_id}/deadlines").json()
    assert len(deadlines) == 1
    assert deadlines[0]["statute_id"] == "deposit_return_clock"
    assert deadlines[0]["due_date"] == "2026-08-31"


def test_move_out_without_forwarding_address_does_not_start_clock():
    with TestClient(app) as client:
        vault_id = _make_vault(client)
        client.post(
            f"/api/vaults/{vault_id}/events",
            json={"event_type": "move_out", "occurred_at": "2026-08-01", "facts": {}},
        )
        deadlines = client.get(f"/api/vaults/{vault_id}/deadlines").json()
    assert deadlines == []
