"""J5 BFF contract tests for persisted strategy evaluation reads."""

from __future__ import annotations

import pytest

from app.integrations.agentguard_client import AgentGuardClient
from tests.conftest import _serve, make_settings
from tests.stub_agentguard import create_stub_app

STRATEGY_EVAL_SECRET = "j5-strategy-evaluation-secret-0123456789abcdef"


@pytest.fixture(scope="module")
def evaluation_stub_url() -> str:
    return _serve(create_stub_app(
        kernel_status="available",
        warden_available=True,
        strategy_evaluations_available=True,
    ))


@pytest.fixture()
def evaluation_env(live_project_env, evaluation_stub_url: str):
    client, settings, login = live_project_env
    client.app.state.agentguard_client = AgentGuardClient(
        make_settings(
            agentguard_base_url=evaluation_stub_url,
            **settings.model_dump(include={"auth_enabled", "app_secret_key", "database_url"}),
        )
    )
    return client, settings, login


def test_strategy_evaluation_list_and_detail_preserve_upstream_fields(evaluation_env) -> None:
    client, _settings, login = evaluation_env
    login()

    listing = client.get("/api/research/strategy-evaluations")
    assert listing.status_code == 200
    list_body = listing.json()
    assert list_body["meta"]["data_mode"] == "live"
    assert list_body["items"][0]["evaluation_id"] == "eval-strategy-001"
    assert list_body["items"][0]["comparison_id"] == "comparison-contract-001"

    detail = client.get("/api/research/strategy-evaluations/eval-strategy-001")
    assert detail.status_code == 200
    body = detail.json()["evaluation"]
    assert body["comparison_id"] == list_body["items"][0]["comparison_id"]
    assert body["data_partition"] == list_body["items"][0]["data_partition"]
    assert body["runs"][0]["steps_to_first_evidence"] is None
    assert body["aggregates"][0]["mean_steps_to_first_evidence"] is None
    assert body["risk_identification_metrics"] is None
    assert body["defense_effectiveness_metrics"] is None


def test_empty_evaluation_list_is_returned_without_synthetic_fill(evaluation_env) -> None:
    client, _settings, login = evaluation_env
    login()
    response = client.get(
        "/api/research/strategy-evaluations", params={"data_partition": "training"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["count"] == 0


@pytest.mark.parametrize(
    ("evaluation_id", "status", "code"),
    [
        ("does-not-exist", 404, "EVALUATION_NOT_FOUND"),
        ("eval-artifact-missing", 410, "EVALUATION_ARTIFACT_UNAVAILABLE"),
    ],
)
def test_detail_not_found_and_missing_artifact_are_forwarded(
    evaluation_env, evaluation_id: str, status: int, code: str,
) -> None:
    client, _settings, login = evaluation_env
    login()
    response = client.get(f"/api/research/strategy-evaluations/{evaluation_id}")
    assert response.status_code == status
    assert response.json()["detail"]["error"] == code


def test_non_admin_cannot_read_global_live_evaluations(evaluation_env) -> None:
    client, settings, _login = evaluation_env
    from sqlalchemy.orm import Session

    from app.core.db import get_engine
    from app.core.passwords import hash_password
    from app.models.app import User

    with Session(get_engine(settings)) as session:
        session.add(User(
            username="j5-viewer",
            role="viewer",
            display_name="J5 Viewer",
            password_hash=hash_password("j5-viewer-password"),
            is_active=True,
        ))
        session.commit()
    response = client.post(
        "/api/auth/login", json={"username": "j5-viewer", "password": "j5-viewer-password"}
    )
    assert response.status_code == 200
    response = client.get("/api/research/strategy-evaluations")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "STRATEGY_EVALUATIONS_SCOPE_RESTRICTED"


def test_synthetic_mode_does_not_mix_or_expose_research_data(evaluation_env) -> None:
    client, settings, login = evaluation_env
    login()
    client.app.state.settings = make_settings(
        app_data_mode="synthetic",
        **settings.model_dump(include={"auth_enabled", "app_secret_key", "database_url"}),
    )
    response = client.get("/api/research/strategy-evaluations")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "STRATEGY_EVALUATIONS_LIVE_ONLY"


def test_upstream_without_research_routes_is_explicitly_unavailable(live_project_env) -> None:
    client, _settings, login = live_project_env
    login()
    response = client.get("/api/research/strategy-evaluations")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "STRATEGY_EVALUATIONS_UNAVAILABLE"


def test_upstream_unavailable_returns_bounded_error(evaluation_env) -> None:
    client, settings, login = evaluation_env
    login()
    client.app.state.agentguard_client = AgentGuardClient(make_settings(
        agentguard_base_url="http://127.0.0.1:9",
        agentguard_api_timeout=0.05,
        **settings.model_dump(include={"auth_enabled", "app_secret_key", "database_url"}),
    ))
    response = client.get("/api/research/strategy-evaluations")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "AGENTGUARD_UNAVAILABLE"
