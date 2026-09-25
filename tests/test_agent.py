from fastapi.testclient import TestClient

from app.agent import GroundedAnswer
from app.main import app


def _make_vault(client: TestClient, **kwargs) -> dict:
    return client.post("/api/vaults", json=kwargs).json()


def test_ask_without_gemini_key_refuses_with_handoff(monkeypatch):
    # Force the no-key path explicitly — a real key may be configured in
    # this environment's .env, and this test must not make a live API call.
    monkeypatch.setattr("app.agent.GEMINI_API_KEY", None)
    with TestClient(app) as client:
        vault = _make_vault(client, zip_code="19121")
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "Will I win in court?"})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] is None
    assert body["refusal"]
    assert body["handoff"]["route"] == "hotline"


def test_ask_with_verified_statute_citation_succeeds(monkeypatch):
    monkeypatch.setattr("app.agent.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.agent._call_model",
        lambda question, party, context: GroundedAnswer(
            grounded=True,
            answer="30 days from move-out, if you gave a forwarding address.",
            citation_type="statute",
            citation_value="68 P.S. § 250.512",
        ),
    )
    with TestClient(app) as client:
        vault = _make_vault(client)
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "When is my deposit due back?"})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "30 days from move-out, if you gave a forwarding address."
    assert body["citation"] == "68 P.S. § 250.512"
    assert body["refusal"] is None


def test_ask_with_fabricated_citation_is_refused_despite_model_claiming_grounded(monkeypatch):
    """The core structural-grounding guarantee: even if the model asserts
    grounded=True, an unverifiable citation must still be refused. This is
    what makes grounding enforced in code, not just requested in the prompt."""
    monkeypatch.setattr("app.agent.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.agent._call_model",
        lambda question, party, context: GroundedAnswer(
            grounded=True,
            answer="You will definitely win your case.",
            citation_type="statute",
            citation_value="a citation that does not exist anywhere",
        ),
    )
    with TestClient(app) as client:
        vault = _make_vault(client)
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "Will I win in court?"})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] is None
    assert body["refusal"]


def test_ask_with_verified_vault_event_citation_succeeds(monkeypatch):
    monkeypatch.setattr("app.agent.GEMINI_API_KEY", "test-key")

    with TestClient(app) as client:
        vault = _make_vault(client)
        event = client.post(
            f"/api/vaults/{vault['id']}/events",
            json={"event_type": "repair_requested", "occurred_at": "2026-03-14", "facts": {}},
        ).json()

        monkeypatch.setattr(
            "app.agent._call_model",
            lambda question, party, context: GroundedAnswer(
                grounded=True,
                answer="You first reported it on 2026-03-14.",
                citation_type="vault_event",
                citation_value=str(event["id"]),
            ),
        )
        res = client.post(
            f"/api/vaults/{vault['id']}/ask", json={"question": "When did I first report the leak?"}
        )
    body = res.json()
    assert body["citation"] == f"event #{event['id']}, repair_requested, 2026-03-14"


def test_ask_with_nonexistent_event_id_is_refused(monkeypatch):
    monkeypatch.setattr("app.agent.GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.agent._call_model",
        lambda question, party, context: GroundedAnswer(
            grounded=True, answer="...", citation_type="vault_event", citation_value="999999"
        ),
    )
    with TestClient(app) as client:
        vault = _make_vault(client)
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "..."})
    body = res.json()
    assert body["answer"] is None
    assert body["refusal"]


def test_ask_survives_model_call_raising(monkeypatch):
    monkeypatch.setattr("app.agent.GEMINI_API_KEY", "test-key")

    def boom(question, party, context):
        raise RuntimeError("simulated API outage")

    monkeypatch.setattr("app.agent._call_model", boom)
    with TestClient(app) as client:
        vault = _make_vault(client)
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "..."})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] is None
    assert body["refusal"]
