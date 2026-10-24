"""Investigation workflow tests (B3) + auth session tests."""

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


VALID_BODY = {
    "contract_id": "contract-qwb-001",
    "model_id": "agent-suite-2.1",
    "runtime_id": "runtime-stub-1",
    "mode": "causal_audit",
    "capture_targets": [
        {"target_id": "agent-a", "agent_ids": ["agent-a"], "component": "settlement", "retain_gradient": False}
    ],
    "metadata": {"purpose": "test"},
    "scenario_id": "sc-qwb-001",
    "risk_type": "tool_abuse",
    "timeout_seconds": 30.0,
    "poll_interval_seconds": 0.5,
}


def test_list_investigations_demo_mode() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.get("/api/investigations")
    assert response.status_code == 200
    payload = response.json()
    # fixture metadata describes the RECORDED source (not the configured mode)
    assert payload["meta"]["data_mode"] == "recorded"
    assert payload["meta"]["fixture_id"] == "fx-inv-001"
    assert payload["count"] == 6


def test_list_investigations_demo_filter_and_pagination() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.get("/api/investigations", params={"status": "completed", "limit": 1, "offset": 0})
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["status"] == "completed"
    assert payload["next_offset"] == 1
    assert payload["total"] == 2


def test_list_investigations_live_with_stub(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    response = client.get("/api/investigations")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["data_mode"] == "live"


def test_list_investigations_unavailable() -> None:
    client = _client("http://127.0.0.1:1")
    response = client.get("/api/investigations")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"


def test_create_investigation_demo_records_without_pretending() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.post("/api/investigations", json=VALID_BODY)
    assert response.status_code == 201
    created = response.json()["created"]
    assert created["status"] == "pending"
    assert "演示模式" in created["demo_note"]
    assert created["run_id"] is None
    # The demo submission appears in the list overlay afterwards
    listed = client.get("/api/investigations").json()
    assert any(item["request_id"] == created["request_id"] for item in listed["items"])
    detail = client.get(f"/api/investigations/{created['request_id']}").json()["investigation"]
    assert detail["demo_note"] == created["demo_note"]
    # The demo timeline confirms only the creation step; the rest stays pending
    events = client.get(f"/api/investigations/{created['request_id']}/timeline").json()["events"]
    assert len(events) == 8
    assert events[0]["status"] == "completed"
    assert all(event["status"] == "pending" for event in events[1:])


def test_create_investigation_live_with_warden(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    response = client.post("/api/investigations", json=VALID_BODY)
    assert response.status_code == 201
    created = response.json()["created"]
    assert created["status"] == "planned"
    assert created["plan"]["plan_id"]


def test_create_investigation_warden_not_configured(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    response = client.post("/api/investigations", json=VALID_BODY)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "WARDEN_NOT_CONFIGURED"


@pytest.mark.parametrize(
    "mutate,error_part",
    [
        ({"mode": "random_mode"}, "mode"),
        ({"timeout_seconds": 999}, "timeout_seconds"),
        ({"contract_id": ""}, "contract_id"),
        ({"capture_targets": [{"target_id": ""}]}, "target_id"),
    ],
)
def test_create_investigation_contract_validation(mutate: dict, error_part: str) -> None:
    body = {**VALID_BODY, **mutate}
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.post("/api/investigations", json=body)
    assert response.status_code == 422
    assert error_part in response.text


def test_investigation_detail_and_404_demo() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    ok = client.get("/api/investigations/inv-qwb-0001")
    assert ok.status_code == 200
    assert ok.json()["investigation"]["run_id"] == "run-qwb-0001"
    missing = client.get("/api/investigations/inv-nope")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "NOT_FOUND"


def test_timeline_demo_recorded_events() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    events = client.get("/api/investigations/inv-qwb-0001/timeline").json()["events"]
    assert len(events) == 8
    assert events[0]["status"] == "completed"
    assert events[-1]["status"] == "completed"
    running_events = client.get("/api/investigations/inv-qwb-0002/timeline").json()["events"]
    assert any(event["status"] == "running" for event in running_events)


def test_timeline_live_derivation_is_honest(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    events = client.get("/api/investigations/inv-stub-0001/timeline").json()["events"]
    # stub detail is completed: final step completed, no fabricated steps
    assert events[-1]["status"] == "completed"
    assert all(event["status"] in {"completed", "pending", "running"} for event in events)


def test_scenarios_demo() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/scenarios").json()
    assert payload["items"][0]["scenario_id"] == "sc-qwb-001"


# ------------------------------------------------------------------ #
# auth / session / role enforcement
# ------------------------------------------------------------------ #
def _client_with_auth() -> TestClient:
    # B9 fail-closed: auth_enabled requires an explicit APP_SECRET_KEY.
    return _client(
        "http://127.0.0.1:1",
        app_data_mode="synthetic",
        auth_enabled=True,
        app_secret_key="unit-test-secret-key-0123456789abcdef",
    )


def _csrf_header(client: TestClient) -> dict:
    return {"X-CSRF-Token": client.cookies.get("qwb_csrf", "")}


def test_auth_disabled_grants_local_admin() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    me = client.get("/api/auth/me").json()
    assert me["authenticated"] is True
    assert me["auth_enabled"] is False
    assert me["user"]["role"] == "admin"
    # implicit admin may create in demo mode (CSRF skipped when auth disabled)
    response = client.post("/api/investigations", json=VALID_BODY)
    assert response.status_code == 201


def test_login_logout_flow() -> None:
    client = _client_with_auth()
    me = client.get("/api/auth/me").json()
    assert me["authenticated"] is False
    assert me["auth_enabled"] is True

    bad = client.post("/api/auth/login", json={"username": "analyst", "password": "wrong"})
    assert bad.status_code == 401

    ok = client.post("/api/auth/login", json={"username": "analyst", "password": "analyst-demo"})
    assert ok.status_code == 200
    assert ok.json()["user"]["role"] == "analyst"
    assert ok.cookies.get("qwb_session")

    me2 = client.get("/api/auth/me").json()
    assert me2["authenticated"] is True

    out = client.post("/api/auth/logout", headers=_csrf_header(client))
    assert out.json()["authenticated"] is False
    me3 = client.get("/api/auth/me").json()
    assert me3["authenticated"] is False


def test_role_enforcement_viewer_cannot_create() -> None:
    client = _client_with_auth()
    client.post("/api/auth/login", json={"username": "viewer", "password": "viewer-demo"})
    response = client.post("/api/investigations", json=VALID_BODY, headers=_csrf_header(client))
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "PERMISSION_DENIED"


def test_role_enforcement_analyst_can_create() -> None:
    client = _client_with_auth()
    client.post("/api/auth/login", json={"username": "analyst", "password": "analyst-demo"})
    response = client.post("/api/investigations", json=VALID_BODY, headers=_csrf_header(client))
    assert response.status_code == 201


def test_csrf_mismatch_rejected() -> None:
    client = _client_with_auth()
    client.post("/api/auth/login", json={"username": "analyst", "password": "analyst-demo"})
    response = client.post("/api/investigations", json=VALID_BODY, headers={"X-CSRF-Token": "forged"})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "CSRF_MISMATCH"


def test_unauthenticated_read_is_rejected_when_auth_enabled() -> None:
    client = _client_with_auth()
    response = client.get("/api/investigations")
    assert response.status_code == 401
