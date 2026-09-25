"""The address surface and incident reporting.

The privacy assertions here are the important ones. The public address page
is readable by anyone who types a street address, so what it may expose is
decided by where a fact came from — City records and de-identified event
shapes only, never anything out of a vault.
"""

from datetime import date

from fastapi.testclient import TestClient

from app import city_data
from app.main import app
from app.routers import properties as properties_router


def _no_city(monkeypatch):
    """Keep the suite offline. The City half is covered in test_city_data.py."""
    monkeypatch.setattr(
        city_data,
        "fetch_city_record",
        lambda addr, **kw: city_data.CityRecord(
            query_address=city_data.normalize_address(addr), address_found=False
        ),
    )


# --- the record attaches to the address ------------------------------------

def test_a_record_created_from_an_address_is_linked_to_that_property(monkeypatch):
    _no_city(monkeypatch)
    with TestClient(app) as client:
        vault = client.post(
            "/api/vaults",
            json={"address": "4047 Spring Garden Street, Philadelphia", "unit": "#2", "zip_code": "19104"},
        ).json()

    assert vault["address_normalized"] == "4047 SPRING GARDEN ST"
    assert vault["address"] == "4047 Spring Garden Street #2"


def test_two_records_at_one_address_share_a_property(monkeypatch):
    """One address, many tenancies over time — that is the whole point of a
    record that outlives its occupants."""
    _no_city(monkeypatch)
    with TestClient(app) as client:
        a = client.post("/api/vaults", json={"address": "1519 Spring Garden St"}).json()
        b = client.post("/api/vaults", json={"address": "1519 SPRING GARDEN STREET, Philadelphia"}).json()

    assert a["address_normalized"] == b["address_normalized"]
    assert a["id"] != b["id"]


def test_an_address_unknown_to_us_still_returns_a_page(monkeypatch):
    """The City half never depends on this app having been used before, so a
    prospective resident can look up anywhere."""
    _no_city(monkeypatch)
    with TestClient(app) as client:
        res = client.get("/api/properties/lookup", params={"address": "9999 Nowhere St"})

    body = res.json()
    assert res.status_code == 200
    assert body["address"]["known_to_us"] is False
    assert body["history"] == []


# --- privacy: what may cross onto a public page ----------------------------

def test_the_public_address_page_never_leaks_a_vault(monkeypatch):
    """The vault id is the write credential and the documents are private.
    Neither may appear on a page anyone can load by typing a street name."""
    _no_city(monkeypatch)
    with TestClient(app) as client:
        vault = client.post(
            "/api/vaults", json={"address": "1234 Test Ave", "label": "Sensitive label"}
        ).json()
        client.post(
            f"/api/vaults/{vault['id']}/events",
            json={
                "event_type": "lease_signed",
                "occurred_at": "2026-01-15",
                "notes": "rent is $2,432",
                "facts": {"deposit_amount": 500.0},
            },
        )
        res = client.get("/api/properties/lookup", params={"address": "1234 Test Ave"})

    text = res.text
    assert vault["id"] not in text
    assert vault["share_token"] not in text
    assert "2,432" not in text and "deposit_amount" not in text
    assert "Sensitive label" not in text


def test_incident_history_is_withheld_until_more_than_one_tenancy(monkeypatch):
    """In a duplex, "a repair was reported here in March" identifies a person
    as surely as naming them."""
    _no_city(monkeypatch)
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"address": "77 Lonely Ln"}).json()
        client.post(
            f"/api/vaults/{vault['id']}/incidents",
            json={"category": "heat", "urgency": "urgent", "summary": "No heat"},
        )
        res = client.get("/api/properties/lookup", params={"address": "77 Lonely Ln"}).json()

    assert res["history_withheld"] is True
    assert res["history"] == []


def test_history_appears_once_the_threshold_is_met_but_stays_de_identified(monkeypatch):
    _no_city(monkeypatch)
    with TestClient(app) as client:
        for _ in range(properties_router.MIN_TENANCIES_FOR_HISTORY):
            vault = client.post("/api/vaults", json={"address": "88 Busy Blvd"}).json()
            client.post(
                f"/api/vaults/{vault['id']}/incidents",
                json={
                    "category": "water_leak",
                    "urgency": "urgent",
                    "summary": "Leak above the kitchen sink",
                    "detail": "My name is A. Resident and I live in unit 4",
                    "reported_at": "2026-03-14",
                },
            )
        res = client.get("/api/properties/lookup", params={"address": "88 Busy Blvd"}).json()

    assert res["history_withheld"] is False
    assert len(res["history"]) == properties_router.MIN_TENANCIES_FOR_HISTORY

    entry = res["history"][0]
    assert entry["category"] == "water_leak"
    assert entry["reported"] == "2026-03-14"
    # Shape of what happened, with the person removed.
    assert "A. Resident" not in res["history_note"] if res["history_note"] else True
    assert "detail" not in entry and "summary" not in entry
    assert "unit 4" not in str(res["history"])


# --- incidents and the drafted notice --------------------------------------

def _report(client, vault_id, **overrides):
    payload = {
        "category": "heat",
        "urgency": "emergency",
        "summary": "No heat since Tuesday",
        "affects_essential_service": True,
        "previously_reported": True,
        "reported_at": "2026-09-25",
        "management_email": "office@example.com",
        "reporter_name": "A. Resident",
    }
    payload.update(overrides)
    return client.post(f"/api/vaults/{vault_id}/incidents", json=payload)


def test_reporting_an_incident_drafts_a_notice_and_does_not_send_it(monkeypatch):
    _no_city(monkeypatch)
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"address": "4047 Spring Garden St"}).json()
        body = _report(client, vault["id"]).json()

    draft = body["draft"]
    assert draft["to"] == "office@example.com"
    # issue | urgency | address | name | #ref
    assert draft["subject"] == (
        f"No heat | EMERGENCY | 4047 Spring Garden St | A. Resident | #{body['reference_code']}"
    )
    assert draft["mailto"].startswith("mailto:office%40example.com?")
    # The user sends it. Nothing here transmits anything.
    assert "No heat since Tuesday" in draft["body"]
    assert body["reported_at"] == "2026-09-25"


def test_the_draft_states_facts_and_makes_no_legal_claim(monkeypatch):
    """statutes.yaml has no *verified* rule about repair obligations — the
    habitability rules are still draft pending a pin cite. Citing law in a
    letter to a third party would assert something this project has not
    confirmed."""
    _no_city(monkeypatch)
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"address": "4047 Spring Garden St"}).json()
        draft = _report(client, vault["id"]).json()["draft"]

    for legalese in ("P.S. §", "Phila. Code", "violation", "unlawful", "must repair", "legally required"):
        assert legalese.lower() not in draft["body"].lower(), f"draft should not assert {legalese!r}"


def test_essential_service_and_repeat_report_appear_in_the_notice(monkeypatch):
    """A repeat report is a far stronger record than a first one, so it has
    to be in the letter rather than only in our database."""
    _no_city(monkeypatch)
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"address": "4047 Spring Garden St"}).json()
        draft = _report(client, vault["id"]).json()["draft"]

    assert "essential service" in draft["body"]
    assert "reported this before" in draft["body"]


def test_an_incident_lands_on_the_vault_timeline(monkeypatch):
    _no_city(monkeypatch)
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"address": "4047 Spring Garden St"}).json()
        ref = _report(client, vault["id"]).json()["reference_code"]
        events = client.get(f"/api/vaults/{vault['id']}/events").json()

    assert [e["event_type"] for e in events] == ["incident_reported"]
    assert ref in events[0]["notes"]


def test_urgency_and_category_are_a_fixed_vocabulary(monkeypatch):
    _no_city(monkeypatch)
    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"address": "4047 Spring Garden St"}).json()
        bad_urgency = _report(client, vault["id"], urgency="VERY BAD")
        bad_category = _report(client, vault["id"], category="vibes")

    assert bad_urgency.status_code == 422
    assert bad_category.status_code == 422


def test_city_record_pull_moves_two_rules_out_of_needs_facts(monkeypatch):
    """The claim the whole design rests on: City facts use names the schema
    and statute table already know, so the existing engine absorbs them with
    no changes at all."""
    monkeypatch.setattr(
        city_data,
        "fetch_city_record",
        lambda addr, **kw: type(
            "R", (), {
                "query_address": "4047 SPRING GARDEN ST", "address_found": True,
                "unavailable": False, "note": None,
                "rental_licenses": [{"licensestatus": "Active"}], "open_violations": [],
            }
        )(),
    )
    monkeypatch.setattr(
        city_data, "derive_facts",
        lambda rec, **kw: {"landlord_rental_license_valid": True, "li_violations_open_days": 0},
    )

    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"address": "4047 Spring Garden St"}).json()
        before = client.get(f"/api/vaults/{vault['id']}/adjudication").json()
        client.post(f"/api/vaults/{vault['id']}/city-record")
        after = client.get(f"/api/vaults/{vault['id']}/adjudication").json()

    moved = {e["statute_id"] for e in before["unknown"]} - {e["statute_id"] for e in after["unknown"]}
    assert moved == {"no_rental_license", "open_violations_over_30_days"}
    assert {e["statute_id"] for e in after["passed"]} >= moved
