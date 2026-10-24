"""Dashboard endpoint + demo fixture tests (B2/B7)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import create_app
from app.services.demo_service import DemoFixtureError, DemoService
from tests.conftest import make_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "demo" / "fixtures"


@pytest.fixture
def demo_service() -> DemoService:
    return DemoService(FIXTURES_DIR)


def test_demo_service_loads_and_verifies_hashes(demo_service: DemoService) -> None:
    assert demo_service.fixture("investigations.json")["items"]
    assert demo_service.fixture("graph.json")["nodes"]


def test_demo_service_rejects_tampered_fixture(demo_service: DemoService, tmp_path: Path) -> None:
    # Copy the fixtures, mutate one file, and confirm the integrity check fails.
    import shutil

    target = tmp_path / "fixtures"
    shutil.copytree(FIXTURES_DIR, target)
    (target / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
    service = DemoService(target)
    with pytest.raises(DemoFixtureError, match="sha256 mismatch"):
        service.fixture("graph.json")


def test_demo_investigation_pagination(demo_service: DemoService) -> None:
    page1 = demo_service.list_investigations(limit=4, offset=0)
    assert page1["count"] == 4
    assert page1["next_offset"] == 4
    page2 = demo_service.list_investigations(limit=4, offset=4)
    assert page2["count"] == 2
    assert page2["next_offset"] is None
    assert page1["total"] == 6


def test_demo_investigation_filter(demo_service: DemoService) -> None:
    page = demo_service.list_investigations(status="completed")
    assert page["count"] == 2
    assert all(item["status"] == "completed" for item in page["items"])


def test_demo_summaries(demo_service: DemoService) -> None:
    inv = demo_service.investigation_summary()
    assert inv["available"] is True
    assert inv["total"] == 6
    assert inv["running"] == 1 and inv["completed"] == 2 and inv["blocked"] == 1 and inv["failed"] == 1
    ev = demo_service.evidence_summary()
    assert ev["by_level"].get("observational") == 2
    assert ev["by_level"].get("causal_validated") == 1
    pol = demo_service.policy_summary()
    assert pol["pending_approval"] == 2
    assert pol["approved"] == 1
    assert pol["verified_historical"] == 1


def _dashboard_payload(client: TestClient) -> dict:
    response = client.get("/api/dashboard")
    assert response.status_code == 200, response.text
    return response.json()


def test_dashboard_unavailable_when_agentguard_down(unreachable_base_url: str) -> None:
    app = create_app()
    with TestClient(app) as client:
        app.state.settings = make_settings(agentguard_base_url=unreachable_base_url)
        app.state.agentguard_client = _make_client(unreachable_base_url)
        payload = _dashboard_payload(client)
    assert payload["system"]["data_mode"] == "unavailable"
    assert payload["investigation_summary"]["available"] is False
    assert payload["evidence_summary"]["available"] is False
    assert payload["policy_summary"]["available"] is False
    assert payload["meta"]["data_mode"] == "unavailable"
    assert payload["dependency_blockers"]


def test_dashboard_live_with_stub(stub_base_url_warden_available: str) -> None:
    app = create_app()
    with TestClient(app) as client:
        app.state.settings = make_settings(agentguard_base_url=stub_base_url_warden_available)
        app.state.agentguard_client = _make_client(stub_base_url_warden_available)
        payload = _dashboard_payload(client)
    assert payload["system"]["data_mode"] == "live"
    assert payload["investigation_summary"]["available"] is True
    assert payload["investigation_summary"]["sample_based"] is True
    assert payload["meta"]["data_mode"] == "live"


def test_dashboard_demo_mode_with_fixtures() -> None:
    app = create_app()
    with TestClient(app) as client:
        app.state.settings = make_settings(app_data_mode="synthetic")
        app.state.agentguard_client = _make_client("http://127.0.0.1:1")
        payload = _dashboard_payload(client)
    assert payload["system"]["data_mode"] == "synthetic"
    assert payload["investigation_summary"]["total"] == 6
    assert payload["investigation_summary"]["available"] is True
    assert payload["evidence_summary"]["by_level"]["causal_validated"] == 1
    assert payload["policy_summary"]["pending_approval"] == 2
    assert payload["meta"]["fixture_id"] == "fx-inv-001"


def _make_client(base_url: str):
    from app.integrations.agentguard_client import AgentGuardClient

    return AgentGuardClient(make_settings(agentguard_base_url=base_url))
