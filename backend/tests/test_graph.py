"""Graph endpoint + fixture tests (B4)."""

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


def test_graph_demo_mode_serves_fixture() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/interaction-graph").json()
    graph = payload["graph"]
    # fixture metadata describes the SYNTHETIC source, not the configured mode
    assert payload["meta"]["data_mode"] == "synthetic"
    assert payload["meta"]["fixture_id"] == "fx-graph-001"
    assert len(graph["nodes"]) == 8
    assert len(graph["edges"]) == 6
    # every edge carries a source id (traceability requirement)
    assert all(edge["source_id"] for edge in graph["edges"])
    assert len(graph["candidate_paths"]) == 2


def test_graph_demo_accepts_request_id() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="recorded")
    payload = client.get("/api/interaction-graph", params={"request_id": "inv-qwb-0001"}).json()
    assert len(payload["graph"]["nodes"]) == 8


def test_graph_live_without_request_id_rejected(stub_base_url_warden_available: str) -> None:
    """B13: the C1 graph capability is published, so live mode requires a
    request_id instead of a blanket 503."""
    client = _client(stub_base_url_warden_available)
    response = client.get("/api/interaction-graph")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "REQUEST_ID_REQUIRED"


def test_graph_live_reports_upstream_no_data_honestly(stub_base_url_warden_available: str) -> None:
    """A workflow without message metadata gets an honest empty graph, not a
    fabricated one (upstream available=false is surfaced verbatim)."""
    client = _client(stub_base_url_warden_available)
    payload = client.get("/api/interaction-graph", params={"request_id": "inv-stub-0001"}).json()
    assert payload["meta"]["capability"] == "upstream_no_data"
    assert payload["graph"]["available"] is False
    assert payload["graph"]["nodes"] == []
    assert payload["meta"]["limitations"]


def test_graph_unavailable_without_demo() -> None:
    client = _client("http://127.0.0.1:1")
    response = client.get("/api/interaction-graph")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"


def test_graph_samples_demo() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/interaction-graph/samples").json()
    assert payload["samples"][0]["scenario_id"] == "sc-qwb-001"


def test_graph_samples_live_unavailable(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    response = client.get("/api/interaction-graph/samples")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "GRAPH_API_UNAVAILABLE"
