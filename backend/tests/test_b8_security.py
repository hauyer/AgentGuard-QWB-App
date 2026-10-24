"""B8 security tests: credentials, cookies, roles, audit, SSRF guard."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.integrations.agentguard_client import AgentGuardClient
from app.main import create_app
from tests.conftest import make_settings

_open_clients: list[TestClient] = []


@pytest.fixture(autouse=True)
def _close_clients():
    _open_clients.clear()
    yield
    for client in _open_clients:
        client.__exit__(None, None, None)


def _client(base_url: str, **overrides) -> TestClient:
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = make_settings(agentguard_base_url=base_url, **overrides)
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    _open_clients.append(client)
    return client


def _login(client: TestClient, username: str = "viewer") -> TestClient:
    response = client.post("/api/auth/login", json={"username": username, "password": f"{username}-demo"})
    assert response.status_code == 200
    return client


def _csrf_header(client: TestClient) -> dict:
    value = client.cookies.get("qwb_csrf", "")
    return {"X-CSRF-Token": value}


def test_session_cookie_is_httponly_samesite_and_not_secure_by_default() -> None:
    client = _client("http://127.0.0.1:1", auth_enabled=True, app_secret_key="test-secret")
    response = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer-demo"})
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "qwb_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" not in set_cookie  # local HTTP dev default


def test_session_cookie_secure_when_configured() -> None:
    client = _client(
        "http://127.0.0.1:1", auth_enabled=True, app_secret_key="test-secret", session_cookie_secure=True
    )
    response = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer-demo"})
    assert response.status_code == 200
    assert "Secure" in response.headers.get("set-cookie", "")


def test_system_status_never_leaks_agentguard_token() -> None:
    client = _client("http://127.0.0.1:1", agentguard_api_token="super-secret-token")
    response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.text
    assert "super-secret-token" not in body
    assert "X-AgentGuard-Token" not in body


def test_viewer_cannot_create_investigation() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic", auth_enabled=True, app_secret_key="test-secret")
    _login(client, "viewer")
    payload = {
        "contract_id": "ct-qwb-001",
        "model_id": "agent-suite-2.1",
        "runtime_id": "run-rt-001",
        "mode": "causal_audit",
    }
    response = client.post("/api/investigations", json=payload, headers=_csrf_header(client))
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "PERMISSION_DENIED"


def test_analyst_can_create_and_audit_records_mutation() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic", auth_enabled=True, app_secret_key="test-secret")
    _login(client, "analyst")
    payload = {
        "contract_id": "ct-qwb-001",
        "model_id": "agent-suite-2.1",
        "runtime_id": "run-rt-001",
        "mode": "detection",
    }
    response = client.post("/api/investigations", json=payload, headers=_csrf_header(client))
    assert response.status_code == 201
    request_id = response.json()["created"]["request_id"]

    # analyst cannot read the audit trail (operator+ only)
    denied = client.get("/api/audit/events")
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "PERMISSION_DENIED"

    # same app instance: logout analyst, login operator, read audit events
    logout = client.post("/api/auth/logout", headers=_csrf_header(client))
    assert logout.status_code == 200
    _login(client, "operator")
    audit = client.get("/api/audit/events").json()
    assert audit["count"] >= 1
    assert any(event["action"] == "investigation.create" and event["target"] == request_id for event in audit["items"])
    assert any(event["action"] == "auth.login.success" for event in audit["items"])
    # B16: auth events are audited too; the mutation itself is still the analyst's
    assert all(
        event["actor"] == "analyst"
        for event in audit["items"] if event["action"] == "investigation.create"
    )


def test_audit_route_requires_operator() -> None:
    client = _client("http://127.0.0.1:1", auth_enabled=True, app_secret_key="test-secret")
    _login(client, "viewer")
    response = client.get("/api/audit/events")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "PERMISSION_DENIED"


def test_upstream_url_rejects_credentials_and_paths() -> None:
    for bad in ("http://user:pass@127.0.0.1:8000", "https://127.0.0.1:8000/api/v1", "ftp://127.0.0.1"):
        with pytest.raises(ValueError):
            make_settings(agentguard_base_url=bad)
    ok = make_settings(agentguard_base_url="https://agentguard.example.com")
    assert ok.agentguard_base_url == "https://agentguard.example.com"
