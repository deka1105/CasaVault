import pytest
from fastapi.testclient import TestClient

from app import agent
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
        lambda question, party, context, key_index=0: GroundedAnswer(
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


# --- upstream failures must not masquerade as principled refusals --------

def test_transient_upstream_failure_is_retried_then_reported_as_unavailable(monkeypatch):
    """A 503 from the provider used to surface as "the agent isn't configured
    yet" — a refusal the user reads as the agent's own judgement. It is a
    fault, and must say so, while still never guessing."""
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("Error code: 503 - gemini is currently experiencing high demand")

    monkeypatch.setattr(agent, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(agent, "_call_model", boom)
    monkeypatch.setattr(agent.time, "sleep", lambda _s: None)

    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"zip_code": "19121"}).json()
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "anything"})

    assert res.status_code == 200
    body = res.json()
    assert len(calls) == 3, "transient provider errors should be retried"
    assert body["answer"] is None
    assert body["unavailable"] is True
    assert "couldn't reach" in body["refusal"]
    assert body["handoff"]["route"] == "hotline"


def test_a_grounded_refusal_is_not_marked_unavailable(monkeypatch):
    """The designed refusal must stay visibly distinct from a fault."""
    monkeypatch.setattr(agent, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        agent,
        "_call_model",
        lambda *a, **k: agent.GroundedAnswer(grounded=False, answer=None, citation_type=None, citation_value=None),
    )

    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"zip_code": "19107"}).json()
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "will I win in court"})

    body = res.json()
    assert body["unavailable"] is False
    assert body["answer"] is None
    assert body["refusal"]
    assert body["handoff"]["route"] == "phillytenant_org"


def test_non_transient_error_is_not_retried(monkeypatch):
    """Retrying a schema/validation failure just burns quota for the same
    result, and quota is the scarce resource here."""
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise ValueError("response failed schema validation")

    monkeypatch.setattr(agent, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(agent, "_call_model", boom)

    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={}).json()
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "anything"})

    assert len(calls) == 1
    assert res.json()["unavailable"] is True
    assert res.json()["answer"] is None


def test_daily_quota_is_not_retried(monkeypatch):
    """A 429 here is a DAILY cap (20/day on the free tier), so retrying can't
    clear it — and each attempt costs ~2 minutes, because the SDK backs off
    internally before surfacing the error. Fail fast, and say it's a limit
    rather than implying the record couldn't support an answer."""
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("Error code: 429 - Rate limit exceeded (limit: 20 requests per day on Free Tier)")

    monkeypatch.setattr(agent, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(agent, "_call_model", boom)
    monkeypatch.setattr(agent.time, "sleep", lambda _s: pytest.fail("quota must not be retried"))

    with TestClient(app) as client:
        vault = client.post("/api/vaults", json={"zip_code": "19121"}).json()
        res = client.post(f"/api/vaults/{vault['id']}/ask", json={"question": "anything"})

    assert len(calls) == 1
    body = res.json()
    assert body["unavailable"] is True
    assert "daily limit" in body["refusal"]
    assert body["answer"] is None
    assert body["handoff"]["route"] == "hotline"
