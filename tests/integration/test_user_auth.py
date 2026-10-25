import time
from datetime import date
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from signal_research.domain.enums import RunMode
from signal_research.main import create_app
from signal_research.worker.machine import ResearchMachine

PUBLISHABLE_KEY = "pk_test_c2V0dGxlZC1jcmF5ZmlzaC04NTUzLmNsZXJrLmFjY291bnRzLmRldiQ"
ISSUER = "https://settled-crayfish-8553.clerk.accounts.dev"
ORIGIN = "https://beyond-gtg4.onrender.com"


def test_required_auth_cannot_silently_fall_back_to_anonymous_access(settings):
    settings.auth_required = True
    settings.clerk_publishable_key = ""
    with pytest.raises(ValueError, match="CLERK_PUBLISHABLE_KEY is required"):
        create_app(settings)


@pytest.fixture
def private_app(settings, monkeypatch):
    settings.clerk_publishable_key = PUBLISHABLE_KEY
    app = create_app(settings)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(app.state.clerk_sessions.keys, "get_signing_key_from_jwt",
                        lambda token: SimpleNamespace(key=key.public_key()))

    def token(user="user_alice", **changes):
        now = int(time.time())
        claims = {"sub": user, "sid": "sess_test", "iss": ISSUER, "azp": ORIGIN,
                  "iat": now, "nbf": now - 1, "exp": now + 60, **changes}
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})

    with TestClient(app) as client:
        yield client, app.state.store, settings, token


def test_run_history_queue_evidence_and_exports_are_private_per_user(private_app):
    client, store, settings, token = private_app
    alice = {"Authorization": f"Bearer {token()}"}
    bob = {"Authorization": f"Bearer {token('user_bob')}"}
    company = store.search_companies("SYNTHBANK")[0]
    payload = {"company_id": str(company.id), "as_of": "2026-10-08", "mode": "replay"}
    assert client.post("/api/v1/runs", json=payload).status_code == 401
    assert client.get("/api/v1/runs/history", headers={"X-User-Id": "user_alice"}).status_code == 401
    a = client.post("/api/v1/runs", json=payload, headers={**alice, "Idempotency-Key": "same"}).json()["run_id"]
    b = client.post("/api/v1/runs", json=payload, headers={**bob, "Idempotency-Key": "same"}).json()["run_id"]
    assert a != b
    assert store.run_owner(a) == "user_alice" and store.run_owner(b) == "user_bob"
    assert client.post("/api/v1/runs", json=payload, headers={**alice, "Idempotency-Key": "same"}).json()["run_id"] == a
    assert [r["id"] for r in client.get("/api/v1/runs/history", headers=alice).json()["items"]] == [a]
    assert [r["id"] for r in client.get("/api/v1/runs/history", headers=bob).json()["items"]] == [b]
    assert client.get("/api/v1/runs/queue", headers=alice).json()["queued_count"] == 1
    assert client.post("/api/v1/runs/queue/clear", headers=alice).json()["run_ids"] == [a]
    assert store.get_summary(b).status == "queued"
    assert client.post(f"/api/v1/runs/{a}/resume", headers=alice).status_code == 202
    assert str(store.lease_next("private-report")) == a
    ResearchMachine(store, settings).process(a)
    report = store.get_report(a)
    assert report is not None
    paths = [f"/api/v1/runs/{a}", f"/api/v1/runs/{a}/events", f"/api/v1/runs/{a}/report",
             *(f"/api/v1/runs/{a}/exports/{suffix}" for suffix in
               ("report.json", "report.html", "facts.csv", "evidence.zip")),
             f"/api/v1/claims/{report.claims[0].id}?run_id={a}",
             f"/api/v1/documents/{report.documents[0].id}/passages?run_id={a}",
             f"/api/v1/calculations/{report.calculations[0].id}?run_id={a}"]
    for path in paths:
        response = client.get(path, headers=alice)
        assert response.status_code == 200, path
        assert response.headers["cache-control"] == "private, no-store"
        assert client.get(path, headers=bob).status_code == 404, path
        assert client.get(path).status_code == 401, path
    for action in ("cancel", "resume"):
        assert client.post(f"/api/v1/runs/{a}/{action}", headers=bob).status_code == 404
    anonymous = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    assert client.get(f"/api/v1/runs/{anonymous}", headers=alice).status_code == 404
    assert len(client.get("/api/v1/runs/history", headers=alice).json()["items"]) == 1
    assert client.get("/api/v1/health/live").status_code == 200


@pytest.mark.parametrize("changes", [
    {"exp": 1}, {"nbf": 4_000_000_000}, {"iss": "https://untrusted.example"},
    {"azp": "https://untrusted.example"}, {"sts": "pending"}, {"sub": "not-a-user"},
])
def test_invalid_or_expired_sessions_are_rejected(private_app, changes):
    client, _, _, token = private_app
    encoded = token(**changes)
    assert client.get("/api/v1/runs/history", headers={"Authorization": f"Bearer {encoded}"}).status_code == 401


def test_cookie_sessions_require_same_origin_for_mutations(private_app):
    client, store, _, token = private_app
    client.cookies.set("__session", token())
    assert client.get("/api/v1/runs/history").status_code == 200
    company = store.search_companies("SYNTHBANK")[0]
    payload = {"company_id": str(company.id), "as_of": "2026-10-08", "mode": "replay"}
    assert client.post("/api/v1/runs", json=payload).status_code == 403
    assert client.post("/api/v1/runs", json=payload, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/runs", json=payload, headers={"Origin": ORIGIN}).status_code == 202
    forged = jwt.encode({"sub": "user_alice"}, "attacker-secret-which-is-not-a-clerk-rsa-key", algorithm="HS256")
    assert client.get("/api/v1/runs/history", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
