"""Demo centre endpoint tests (B7)."""

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


def test_demo_overview_demo_mode_full_flow() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/demo/overview").json()
    assert payload["meta"]["fixture_id"] == "fx-scenarios-001"
    flow = payload["flow"]
    # complete reproducible flow: 9 steps covering open -> scenario -> graph
    # -> investigation -> findings -> evidence -> defense -> experiments -> report
    assert [step["step"] for step in flow] == list(range(1, 10))
    assert flow[2]["path"] == "/interaction-graph"
    assert flow[5]["path"] == "/evidence?request_id=inv-qwb-0001"
    assert flow[6]["path"] == "/defenses?request_id=inv-qwb-0001"
    assert flow[8]["path"] == "/reports"
    assert payload["scenarios_error"] is None
    assert any(scenario["scenario_id"] == "sc-qwb-001" for scenario in payload["scenarios"])


def test_demo_overview_live_mode_scenarios_from_agentguard(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    payload = client.get("/api/demo/overview").json()
    assert payload["meta"]["data_mode"] == "live"
    assert len(payload["flow"]) == 9
    assert payload["scenarios_error"] is None
    assert isinstance(payload["scenarios"], list)


def test_demo_overview_unavailable_keeps_flow() -> None:
    client = _client("http://127.0.0.1:1")
    payload = client.get("/api/demo/overview").json()
    assert payload["meta"]["data_mode"] == "unavailable"
    assert len(payload["flow"]) == 9
    assert payload["scenarios"] == []
    assert payload["scenarios_error"] == "API_UNAVAILABLE"
