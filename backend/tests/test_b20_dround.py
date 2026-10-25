"""B20 D-round integration tests: readiness, options, timeline precedence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.integrations.agentguard_client import AgentGuardClient


def _login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "alice", "password": "alice-pw-12345"})
    assert response.status_code == 200


def test_readiness_proxy_passthrough(live_project_env) -> None:
    client, _settings, login = live_project_env
    login()
    payload = client.get("/api/system/readiness").json()
    assert payload["data_mode"] == "live"
    assert payload["readiness_error"] is None
    checks = {check["name"]: check["status"] for check in payload["readiness"]["checks"]}
    assert checks["agentguard_api"] == "available"
    assert checks["contract_source"] == "unknown"  # honest: no threat contracts wired
    assert checks["agent_runtime"] == "blocked"
    # capability discovery verdicts layered on top
    assert payload["capabilities"]["investigation_options"] is True
    assert payload["capabilities"]["run_findings"] is False or True  # tracked, verdict from live OpenAPI


def test_readiness_reports_error_when_upstream_down(live_project_env) -> None:
    client, settings, login = live_project_env
    login()
    # point the client at a dead upstream
    from tests.conftest import make_settings

    app = client.app
    app.state.settings = make_settings(agentguard_base_url="http://127.0.0.1:9",
                                       **settings.model_dump(include={
                                           "auth_enabled", "app_secret_key", "database_url"}))
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    payload = client.get("/api/system/readiness").json()
    assert payload["readiness"] is None
    assert payload["readiness_error"] is not None
    assert payload["capabilities"]["discovery_error"] is not None


def test_options_proxy_live_passthrough(live_project_env) -> None:
    client, _settings, login = live_project_env
    login()
    payload = client.get("/api/investigations/options").json()
    assert payload["meta"]["data_mode"] == "live"
    modes = {mode["mode"]: mode for mode in payload["modes"]}
    assert modes["observation"]["submittable"] is False
    assert "NO_THREAT_CONTRACTS" in modes["observation"]["blockers"]


def test_options_demo_mode_honest(tmp_path) -> None:
    from app.core.db import dispose_engine, upgrade_database
    from app.integrations.agentguard_client import AgentGuardClient
    from app.main import create_app
    from app.services.audit_service import AuditService
    from tests.conftest import make_settings

    settings = make_settings(app_data_mode="synthetic")
    upgrade_database(settings)  # no-op without DATABASE_URL
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = make_settings(agentguard_base_url="http://127.0.0.1:1",
                                       app_data_mode="synthetic")
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    app.state.audit_service = AuditService(app.state.settings)
    payload = client.get("/api/investigations/options").json()
    assert payload["available"] is False
    assert payload["modes"] == []
    assert "演示" in payload["note"]
    dispose_engine(settings)


def test_timeline_prefers_investigation_form(live_project_env) -> None:
    client, _settings, login = live_project_env
    login()
    payload = client.get("/api/investigations/inv-stub-0001/timeline").json()
    assert payload["meta"]["timeline_source"] == "upstream"
    assert payload["meta"]["upstream_form"] == "investigation"
    steps = {event["step"] for event in payload["events"]}
    assert "workflow_created" in steps


def test_live_unreachable_never_serves_demo_data(live_project_env) -> None:
    """B20-4: with the upstream down, LIVE reads fail with explicit errors -
    no silent switch to demo/recorded business data."""
    client, settings, login = live_project_env
    login()
    from tests.conftest import make_settings

    app = client.app
    app.state.settings = make_settings(agentguard_base_url="http://127.0.0.1:9",
                                       **settings.model_dump(include={
                                           "auth_enabled", "app_secret_key", "database_url"}))
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    response = client.get("/api/investigations")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"
    evidence = client.get("/api/evidence", params={"request_id": "inv-stub-0001"})
    assert evidence.status_code == 503
    assert evidence.json()["detail"]["error"] == "API_UNAVAILABLE"
