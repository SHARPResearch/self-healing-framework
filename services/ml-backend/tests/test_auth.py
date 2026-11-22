"""
Authentication and tenant isolation with AUTH_MODE=jwt (docs/adr/0014, 0015).

Tokens are signed here with an Ed25519 key, the algorithm the auth service uses; the backend's
JWKS lookup is replaced by that key's public half. Two organizations each get their own replay
fleet (one calm SMD window, so the test stays fast) and must never see or touch the other's.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings

settings.start_replay = False
settings.use_backing_services = False

from app import auth  # noqa: E402
from app.fleet import ServiceFleet  # noqa: E402
from app.main import app  # noqa: E402
from app.tenancy import tenants  # noqa: E402

KEY = Ed25519PrivateKey.generate()
ORG_A, ORG_B = "org-acme", "org-globex"


def token(org, role, email="user@example.com", **over):
    claims = {"sub": f"user-{email}", "email": email, "org": org, "role": role,
              "iss": settings.auth_issuer, "aud": settings.auth_audience, "exp": int(time.time()) + 600}
    claims.update(over)
    return jwt.encode(claims, KEY, algorithm="EdDSA")


def bearer(org, role, **kw):
    return {"Authorization": f"Bearer {token(org, role, **kw)}"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "jwt")
    monkeypatch.setattr(settings, "primary_tenant", "")
    monkeypatch.setattr(settings, "max_tenants", 2)
    monkeypatch.setattr(auth, "_signing_key", lambda _token: KEY.public_key())
    monkeypatch.setattr(tenants, "fleet_factory",
                        lambda: ServiceFleet([("service-orders", "Orders", "machine-1-2", 9250)]))
    with TestClient(app) as c:
        yield c


def test_requests_without_a_valid_token_are_rejected(client):
    assert client.get("/api/services").status_code == 401
    assert client.get("/api/services", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    expired = bearer(ORG_A, "owner", exp=int(time.time()) - 5)
    assert client.get("/api/services", headers=expired).status_code == 401
    wrong_audience = bearer(ORG_A, "owner", aud="someone-else")
    assert client.get("/api/services", headers=wrong_audience).status_code == 401
    no_org = bearer(None, "owner")
    assert client.get("/api/services", headers=no_org).status_code == 401
    # probes stay public and reveal no tenant data
    health = client.get("/api/health").json()
    assert health["status"] == "ok" and "services" not in health
    assert client.get("/api/ready").status_code == 200


def test_each_organization_sees_only_its_own_fleet(client):
    a, b = bearer(ORG_A, "operator"), bearer(ORG_B, "operator")
    assert [s["serviceId"] for s in client.get("/api/services", headers=a).json()] == ["service-orders"]
    assert client.get("/api/health", headers=a).json()["tenant"] == ORG_A
    assert client.post("/api/demo/service-orders/deploy", headers=a).status_code == 200
    state_a = client.get("/api/demo/state", headers=a).json()["services"][0]
    state_b = client.get("/api/demo/state", headers=b).json()["services"][0]
    assert state_a["injections"] == ["deploy"] and state_b["injections"] == []
    assert tenants.runtimes[ORG_A] is not tenants.runtimes[ORG_B]
    assert tenants.runtimes[ORG_A].store is not tenants.runtimes[ORG_B].store
    assert tenants.runtimes[ORG_A].bus.channel != tenants.runtimes[ORG_B].bus.channel


def test_roles_limit_what_a_member_can_do(client):
    viewer, operator, admin = (bearer(ORG_A, r) for r in ("viewer", "operator", "admin"))
    assert client.get("/api/models", headers=viewer).status_code == 200
    assert client.post("/api/demo/service-orders/incident", headers=viewer).status_code == 403
    assert client.post("/api/models/service-orders/validity-check", headers=operator).status_code == 200
    assert client.post("/api/models/service-orders/promote", json={}, headers=operator).status_code == 403
    assert client.post("/api/demo/reset", headers=operator).status_code == 403
    assert client.post("/api/demo/reset", headers=admin).status_code == 200


def test_the_number_of_demo_fleets_is_capped(client):
    for org in (ORG_A, ORG_B):
        assert client.get("/api/services", headers=bearer(org, "viewer")).status_code == 200
    assert client.get("/api/services", headers=bearer("org-third", "viewer")).status_code == 503


def test_the_websocket_needs_a_token_first_and_streams_one_tenant(client):
    with client.websocket_connect("/ws/events") as ws:
        ws.send_json({"type": "auth", "token": "nonsense"})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4401
    with client.websocket_connect("/ws/events") as ws:
        ws.send_json({"type": "auth", "token": token(ORG_B, "viewer")})
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert [s["serviceId"] for s in snapshot["data"]["services"]] == ["service-orders"]
    assert ORG_B in tenants.runtimes
