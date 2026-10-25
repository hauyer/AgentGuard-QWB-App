"""System status endpoint tests across Live / Unavailable / degraded scenarios.

The stub AgentGuard is served over real HTTP; the BFF connector is exercised
through the production network path.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from conftest import make_settings
from fastapi.testclient import TestClient

from app.integrations.agentguard_client import AgentGuardClient
from app.main import create_app


@contextmanager
def _app_with_client(base_url: str, **settings_overrides) -> Iterator[TestClient]:
    settings = make_settings(agentguard_base_url=base_url, **settings_overrides)
    app = create_app()
    with TestClient(app) as client:
        # The lifespan has run; now swap in the injected settings/client. The
        # swap must happen after startup so lifespan cannot overwrite them.
        app.state.settings = settings
        app.state.agentguard_client = AgentGuardClient(settings)
        yield client


def test_status_unavailable_when_agentguard_unreachable(unreachable_base_url) -> None:
    with _app_with_client(unreachable_base_url) as client:
        response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] == "unavailable"
    assert body["agentguard"]["reachable"] is False
    assert body["agentguard"]["error"]["code"] == "API_UNREACHABLE"
    assert body["warden"]["status"] == "unavailable"
    assert body["capabilities"] is None
    assert all(not feature["available"] for feature in body["features"])
    # Never fabricate a version when upstream is unreachable.
    assert body["agentguard"]["health"] is None


def test_status_live_when_agentguard_and_warden_available(stub_base_url_warden_available) -> None:
    with _app_with_client(stub_base_url_warden_available) as client:
        response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] == "live"
    assert body["agentguard"]["reachable"] is True
    assert body["agentguard"]["health"]["version"] == "1.1.0rc1"
    assert body["warden"]["status"] == "available"
    assert body["capabilities"]["backend_mode"] == "synthetic"
    by_name = {feature["name"]: feature for feature in body["features"]}
    assert by_name["investigations.create"]["available"] is True
    assert by_name["defense.execute"]["available"] is False
    assert by_name["interaction.graph"]["available"] is False


def test_warden_not_marked_available_from_health_alone(stub_base_url) -> None:
    """Health is ok but kernel status is not_configured: WARDEN must stay unavailable."""
    with _app_with_client(stub_base_url) as client:
        response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["agentguard"]["reachable"] is True
    assert body["agentguard"]["health"]["status"] == "ok"
    assert body["warden"]["status"] == "not_configured"
    by_name = {feature["name"]: feature for feature in body["features"]}
    assert by_name["investigations.create"]["available"] is False
    assert "WARDEN" in (by_name["investigations.create"]["reason"] or "")


def test_capabilities_failure_degrades_manifest_not_whole_status(stub_base_url_capabilities_fail) -> None:
    with _app_with_client(stub_base_url_capabilities_fail) as client:
        response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["agentguard"]["reachable"] is True
    assert body["agentguard"]["capabilities"] is None
    assert body["agentguard"]["error"]["code"] == "INTERNAL"


def test_data_mode_override_forces_synthetic(stub_base_url) -> None:
    with _app_with_client(stub_base_url, app_data_mode="synthetic") as client:
        response = client.get("/api/system/status")
    body = response.json()
    assert body["data_mode"] == "synthetic"
    assert body["agentguard"]["reachable"] is True  # connectivity is reported separately


def test_app_health_endpoint() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["service"] == "agentguard-qwb-app"
