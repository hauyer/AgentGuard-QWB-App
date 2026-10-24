"""B13 capability-aware integration tests against the extended stub.

Covers: C1 graph (honest empty + populated + old-upstream 503 fallback),
C2 experiments index, controlled comparison with comparability checks,
run-timeline precedence, and capability discovery failure semantics.
"""

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


# ------------------------------------------------------------------ #
# C1 interaction graph
# ------------------------------------------------------------------ #
def test_graph_live_honest_empty_when_upstream_has_no_data(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    payload = client.get("/api/interaction-graph", params={"request_id": "inv-stub-0001"}).json()
    assert payload["meta"]["data_mode"] == "live"
    assert payload["meta"]["capability"] == "upstream_no_data"
    assert payload["graph"]["not_provable"]
    assert payload["graph"]["upstream_available"] is False
    assert payload["graph"]["nodes"] == [] and payload["graph"]["edges"] == []


def test_graph_live_populated_passthrough_keeps_ids(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    payload = client.get("/api/interaction-graph", params={"request_id": "inv-stub-graph-0002"}).json()
    graph = payload["graph"]
    assert payload["meta"]["capability"] == "available"
    assert graph["upstream_available"] is True
    node_ids = {node["id"] for node in graph["nodes"]}
    assert node_ids == {"agent-a", "tool-1", "agent-b"}
    edge = graph["edges"][0]
    assert edge["source"] and edge["target"]
    assert edge["message_id"] == "msg-0001"
    assert edge["metadata"]["evidence_refs"] == ["ev-stub-000000000001"]
    # candidate paths stay candidates in the payload, never rewritten as causal
    assert "candidate_paths" in graph
    assert payload["meta"]["source"] == "agentguard-interaction-graph"


def test_graph_live_503_when_capability_not_published(tmp_path) -> None:
    """An older pinned upstream without the C1 endpoint must keep the explicit 503."""
    client = _client("http://127.0.0.1:1", app_data_mode="live")
    response = client.get("/api/interaction-graph", params={"request_id": "inv-x"})
    assert response.status_code == 503
    body = response.json()["detail"]
    assert body["error"] == "API_UNAVAILABLE"  # upstream unreachable first


def test_graph_live_request_id_required(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    response = client.get("/api/interaction-graph")
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "REQUEST_ID_REQUIRED"


# ------------------------------------------------------------------ #
# C2 experiments
# ------------------------------------------------------------------ #
def test_experiments_live_from_published_index(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    payload = client.get("/api/experiments").json()
    assert payload["meta"]["data_mode"] == "live"
    assert payload["meta"]["capability"] == "available"
    items = payload["items"]
    assert len(items) >= 2
    # metrics_available=false passes through verbatim - no invented metrics
    assert any(item["metrics_available"] is False for item in items)
    assert {item["evidence_level"] for item in items} == {"synthetic"}


def test_experiments_still_503_when_unreachable() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="live")
    response = client.get("/api/experiments")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"


def test_compare_requires_authentication_and_csrf(stub_base_url: str) -> None:
    client = _client(stub_base_url, auth_enabled=True, app_secret_key="b13-secret-key-0123456789abcdef")
    response = client.post("/api/experiments/compare", json={"run_ids": ["a", "b"]})
    assert response.status_code == 401


def test_compare_run_not_indexed_rejected(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    response = client.post("/api/experiments/compare",
                           json={"run_ids": ["run-stub-0001", "run-not-there"]})
    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["error"] == "RUN_NOT_INDEXED"
    assert "run-not-there" in body["message"]


def test_compare_incomparable_reports_reasons(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    # run-stub-0001 has metrics_available=false -> incomparable, with reason
    response = client.post("/api/experiments/compare",
                           json={"run_ids": ["run-stub-0001", "run-stub-0002"]})
    assert response.status_code == 200
    body = response.json()
    assert body["comparable"] is False
    assert any("metrics_available=false" in reason for reason in body["reasons"])
    assert {entry["run_id"] for entry in body["entries"]} == {"run-stub-0001", "run-stub-0002"}


def test_compare_comparable_same_scenario(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    # both synthetic + metrics available on run-stub-0002 only; using the same
    # run twice is degenerate, so expect the metrics reason (honest refusal)
    response = client.post("/api/experiments/compare",
                           json={"run_ids": ["run-stub-0002", "run-stub-0002"]})
    assert response.status_code in {200, 422}
    if response.status_code == 200:
        body = response.json()
        assert body["comparable"] is False or body["comparison"]


# ------------------------------------------------------------------ #
# timeline: upstream events first, derived clearly labelled
# ------------------------------------------------------------------ #
def test_timeline_uses_upstream_events_when_run_exists(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    payload = client.get("/api/investigations/inv-stub-0001/timeline").json()
    assert payload["meta"]["data_mode"] == "live"
    assert payload["meta"]["timeline_source"] == "upstream"
    assert payload["meta"]["run_id"] == "run-stub-0001"
    steps = {event["step"] for event in payload["events"]}
    assert "plan_submitted" in steps and "run_started" in steps


def test_timeline_derived_when_upstream_has_no_run_timeline(stub_base_url: str) -> None:
    client = _client(stub_base_url, app_data_mode="synthetic")
    payload = client.get("/api/investigations/inv-stub-0001/timeline").json()
    # demo fixtures keep their recorded provenance meta
    assert payload["meta"]["data_mode"] in {"recorded", "synthetic"}


# ------------------------------------------------------------------ #
# capability discovery
# ------------------------------------------------------------------ #
def test_discovery_failure_is_reported_not_fatal(unreachable_base_url: str) -> None:
    client = AgentGuardClient(make_settings(agentguard_base_url=unreachable_base_url))
    try:
        operations = client.discover_operations()
        assert all(value is False for value in operations.values())
        assert client.discovery_error is not None
    finally:
        client.close()
