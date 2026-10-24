"""Experiment/report/experience endpoint tests (B6)."""

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
# experiments comparison
# ------------------------------------------------------------------ #
def test_experiments_demo_serves_fixture() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/experiments").json()
    assert payload["meta"]["fixture_id"] == "fx-experiments-001"
    assert len(payload["items"]) == 3
    # comparison dimensions are present
    item = payload["items"][0]
    assert item["model_version"] == "agent-suite-2.1"
    assert item["investigation_strategy"] == "causal_audit"
    assert item["defense_strategy"] == "whitelist-block"
    assert item["utility"]["normal_task_success_rate"] == 0.98
    assert item["budget"]["tokens"] == 18400
    assert item["result_source"].startswith("recorded:")


def test_experiments_live_uses_published_index(stub_base_url_warden_available: str) -> None:
    """B13: the C2 experiment index is published on the pinned upstream, so
    live mode serves the real list (with metrics_available verbatim) instead of
    the previous blanket 503."""
    client = _client(stub_base_url_warden_available)
    response = client.get("/api/experiments")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["data_mode"] == "live"
    assert body["meta"]["capability"] == "available"
    assert isinstance(body["items"], list) and body["items"]


def test_experiments_live_503_when_capability_absent() -> None:
    """An upstream without the C2 endpoint keeps the explicit EXPERIMENTS_UNAVAILABLE."""
    client = _client("http://127.0.0.1:1", app_data_mode="live")
    response = client.get("/api/experiments")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"


def test_experiments_unavailable_without_demo() -> None:
    client = _client("http://127.0.0.1:1")
    response = client.get("/api/experiments")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"


# ------------------------------------------------------------------ #
# reports
# ------------------------------------------------------------------ #
def test_report_demo_serves_fixture() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/reports/run-qwb-0001").json()
    report = payload["report"]
    assert payload["meta"]["fixture_id"] == "fx-reports-001"
    assert report["run_id"] == "run-qwb-0001"
    assert len(report["findings"]) == 2
    assert len(report["evidence"]) == 4
    assert report["limitations"]
    assert "不推断新的因果结论" in report["limitations"][0]


def test_report_demo_unknown_404() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.get("/api/reports/run-unknown")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "NOT_FOUND"


def test_report_live_proxies_stub(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    payload = client.get("/api/reports/run-stub-0001").json()
    assert payload["meta"]["data_mode"] == "live"
    assert payload["report"]["run_id"] == "run-stub-0001"


def test_report_pdf_export_demo() -> None:
    import io

    from pypdf import PdfReader

    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.get("/api/reports/run-qwb-0001/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    body = response.content
    assert body.startswith(b"%PDF")
    assert body.rstrip().endswith(b"%%EOF")
    # text-level verification via pypdf: metrics and ids must be present verbatim
    reader = PdfReader(io.BytesIO(body))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "run-qwb-0001" in text
    assert "fd-qwb-0001" in text
    assert "ev-qwb-0004" in text
    assert "def-qwb-0001" in text
    assert "metrics unchanged; no new causal conclusions" in text


def test_report_pdf_export_unknown_404() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    response = client.get("/api/reports/run-unknown/export")
    assert response.status_code == 404


# ------------------------------------------------------------------ #
# experiences
# ------------------------------------------------------------------ #
def test_experiences_demo_serves_fixture() -> None:
    client = _client("http://127.0.0.1:1", app_data_mode="synthetic")
    payload = client.get("/api/experiences").json()
    assert payload["meta"]["fixture_id"] == "fx-experiences-001"
    assert len(payload["items"]) == 2
    assert payload["items"][0]["verification_level"] == "verified"
    assert payload["items"][0]["recommendation_allowed"] is True
    assert payload["recommendation_note"]


def test_experiences_live_proxies_stub(stub_base_url_warden_available: str) -> None:
    client = _client(stub_base_url_warden_available)
    payload = client.get("/api/experiences").json()
    assert payload["meta"]["data_mode"] == "live"
    assert isinstance(payload["items"], list)


def test_experiences_unavailable_without_demo() -> None:
    client = _client("http://127.0.0.1:1")
    response = client.get("/api/experiences")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"
