"""Evidence + defense endpoint tests (B5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.integrations.agentguard_client import AgentGuardClient
from app.main import create_app
from app.schemas.evidence import normalize_evidence_item
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
# evidence
# ------------------------------------------------------------------ #
def test_evidence_demo_serves_fixture_with_levels_and_artifacts() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/evidence", params={"request_id": "inv-qwb-0001"}).json()
    evidence = payload["evidence"]
    assert payload["meta"]["fixture_id"] == "fx-evidence-001"
    assert evidence["request_id"] == "inv-qwb-0001"
    levels = [item["evidence_level"] for item in evidence["items"]]
    # observational evidence must remain distinguishable from causal_validated
    assert "observational" in levels and "causal_validated" in levels
    assert all(item["artifact_refs"] == [] for item in evidence["items"])


def test_evidence_demo_unknown_investigation_404() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.get("/api/evidence", params={"request_id": "inv-does-not-exist"})
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "NOT_FOUND"


def test_evidence_live_proxies_stub(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    payload = client.get("/api/evidence", params={"request_id": "inv-stub-0001"}).json()
    assert payload["meta"]["data_mode"] == "live"
    assert payload["evidence"]["items"][0]["evidence_id"].startswith("ev-stub-")


def test_evidence_unavailable_without_demo() -> None:
    client = _client("http://127.0.0.1:1")
    response = client.get("/api/evidence", params={"request_id": "inv-qwb-0001"})
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"


@pytest.mark.parametrize("item", [{}, {"evidence_level": "future_level"}])
def test_missing_or_unrecognized_evidence_level_stays_unknown(item: dict) -> None:
    assert normalize_evidence_item(item)["evidence_level"] == "unknown"


# ------------------------------------------------------------------ #
# defense
# ------------------------------------------------------------------ #
def test_defense_demo_candidates_never_executable() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/defense", params={"request_id": "inv-qwb-0001"}).json()
    defense = payload["defense"]
    assert payload["meta"]["fixture_id"] == "fx-defense-001"
    assert defense["status"] == "preview_only"
    assert defense["execution_performed"] is False
    assert all(candidate["execution_supported"] is False for candidate in defense["candidates"])
    assert any(candidate["candidate_id"] == "def-qwb-0001" for candidate in defense["candidates"])


def test_defense_demo_approved_but_still_unsupported() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/defense", params={"request_id": "inv-qwb-0005"}).json()
    candidates = payload["defense"]["candidates"]
    assert candidates[0]["status"] == "approved"
    assert candidates[0]["execution_supported"] is False


def test_defense_preview_live_persists_only(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    payload = client.post("/api/defense/inv-stub-0001/preview").json()
    assert payload["meta"]["data_mode"] == "live"
    assert payload["defense"]["execution_performed"] is False


def test_defense_preview_demo_readonly() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.post("/api/defense/inv-qwb-0001/preview")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "DEMO_READONLY"
    assert "演示模式" in detail["message"]


def test_defense_preview_unavailable() -> None:
    client = _client("http://127.0.0.1:1")
    response = client.post("/api/defense/inv-qwb-0001/preview")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"


def test_defense_outcomes_demo() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/defense/outcomes").json()
    assert payload["outcomes"][0]["outcome_id"] == "hist-def-0001"
    assert payload["outcomes"][0]["status"] == "verified"


def test_defense_outcomes_live_unavailable_not_fabricated(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    payload = client.get("/api/defense/outcomes").json()
    assert payload["outcomes"] == []
    assert payload["meta"]["available"] is False
