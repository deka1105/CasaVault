import asyncio
from types import SimpleNamespace

from fastapi import Request
from fastapi.testclient import TestClient

from app.auth import get_optional_user_id
from app.main import app


def _fake_state(signed_in: bool, sub: str = "user_abc123"):
    from clerk_backend_api.security.types import AuthStatus

    return SimpleNamespace(
        status=AuthStatus.SIGNED_IN if signed_in else AuthStatus.SIGNED_OUT,
        payload={"sub": sub} if signed_in else None,
    )


def _request_with_headers(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request({"type": "http", "headers": headers})


def test_get_optional_user_id_returns_none_without_clerk_key(monkeypatch):
    monkeypatch.setattr("app.auth.CLERK_SECRET_KEY", None)
    request = _request_with_headers([(b"authorization", b"Bearer whatever")])
    assert asyncio.run(get_optional_user_id(request)) is None


def test_get_optional_user_id_returns_none_without_auth_header(monkeypatch):
    monkeypatch.setattr("app.auth.CLERK_SECRET_KEY", "sk_test_fake")
    request = _request_with_headers([])
    assert asyncio.run(get_optional_user_id(request)) is None


def test_get_optional_user_id_returns_sub_on_valid_session(monkeypatch):
    monkeypatch.setattr("app.auth.CLERK_SECRET_KEY", "sk_test_fake")

    class FakeClerk:
        def __init__(self, **kwargs):
            pass

        async def authenticate_request_async(self, request, options):
            return _fake_state(signed_in=True, sub="user_live")

    monkeypatch.setattr("app.auth.Clerk", FakeClerk)
    request = _request_with_headers([(b"authorization", b"Bearer real-looking-token")])
    assert asyncio.run(get_optional_user_id(request)) == "user_live"


def test_get_optional_user_id_returns_none_on_verification_failure(monkeypatch):
    monkeypatch.setattr("app.auth.CLERK_SECRET_KEY", "sk_test_fake")

    class FakeClerk:
        def __init__(self, **kwargs):
            pass

        async def authenticate_request_async(self, request, options):
            raise RuntimeError("simulated Clerk outage")

    monkeypatch.setattr("app.auth.Clerk", FakeClerk)
    request = _request_with_headers([(b"authorization", b"Bearer whatever")])
    assert asyncio.run(get_optional_user_id(request)) is None


def test_create_vault_without_auth_leaves_owner_unset():
    with TestClient(app) as client:
        res = client.post("/api/vaults", json={"label": "anonymous vault"})
    assert res.status_code == 200
    assert res.json()["owner_user_id"] is None


def test_mine_requires_signin():
    with TestClient(app) as client:
        res = client.get("/api/vaults/mine")
    assert res.status_code == 401


def test_create_vault_with_auth_sets_owner_and_mine_lists_it(monkeypatch):
    class FakeClerk:
        def __init__(self, **kwargs):
            pass

        async def authenticate_request_async(self, request, options):
            return _fake_state(signed_in=True, sub="user_owner_1")

    monkeypatch.setattr("app.auth.CLERK_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr("app.auth.Clerk", FakeClerk)

    headers = {"Authorization": "Bearer looks-like-a-jwt"}
    with TestClient(app) as client:
        created = client.post("/api/vaults", json={"label": "owned vault"}, headers=headers)
        assert created.status_code == 200
        assert created.json()["owner_user_id"] == "user_owner_1"

        mine = client.get("/api/vaults/mine", headers=headers)
        assert mine.status_code == 200
        ids = [v["id"] for v in mine.json()]
        assert created.json()["id"] in ids

        # anonymous vaults never show up in someone else's "mine" list
        anon = client.post("/api/vaults", json={"label": "still anonymous"})
        assert anon.json()["id"] not in ids
