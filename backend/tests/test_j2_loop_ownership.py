"""J2.1: verified loop ownership registration and access isolation."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import dispose_engine, get_engine, upgrade_database
from app.core.passwords import hash_password
from app.integrations.agentguard_client import AgentGuardError
from app.main import create_app
from app.models.app import (
    Project,
    ProjectInvestigation,
    ProjectInvestigationLoop,
    ProjectMember,
    User,
)
from app.services import resource_access
from app.services.audit_service import AuditService
from tests.conftest import make_settings

APP_SECRET = "j2-loop-ownership-secret-key-0123456789"


class LoopUpstream:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.list_response: dict = {
            "items": [], "count": 0, "offset": 0, "limit": 100, "next_offset": None,
        }
        self.list_pages: dict[int, dict] = {}
        self.list_error: AgentGuardError | None = None
        self.discovery_error = None
        self.operations = {
            "GET /v1/investigation-loops": True,
            "GET /v1/investigation-loops/{loop_id}": True,
            "GET /v1/investigation-loops/{loop_id}/decisions": True,
            "GET /v1/investigation-loops/{loop_id}/evidence-changes": True,
            "GET /v1/investigation-loops/{loop_id}/budget": True,
        }

    def close(self) -> None:
        return

    def health(self) -> dict:
        self.calls.append(("health",))
        return {"status": "ok"}

    def discover_operations(self) -> dict[str, bool]:
        self.calls.append(("discover",))
        return self.operations

    def list_investigation_loops(
        self, base_request_id: str, *, limit: int = 50, offset: int = 0,
    ) -> dict:
        self.calls.append(("list", base_request_id, limit, offset))
        if self.list_error:
            raise self.list_error
        return self.list_pages.get(offset, self.list_response)

    def get_investigation_loop(self, loop_id: str) -> dict:
        self.calls.append(("detail", loop_id))
        return {"loop_id": loop_id, "base_request_id": "inv-a", "phase": "completed"}


@pytest.fixture
def loop_env(tmp_path: Path):
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=APP_SECRET,
        app_data_mode="live",
        database_url=f"sqlite:///{(tmp_path / 'j2-loops.db').as_posix()}",
    )
    upgrade_database(settings)
    with Session(get_engine(settings)) as session:
        session.add_all([
            User(username="alice", role="analyst", display_name="Alice",
                 password_hash=hash_password("alice-password-123"), is_active=True),
            User(username="bob", role="analyst", display_name="Bob",
                 password_hash=hash_password("bob-password-123"), is_active=True),
        ])
        project_a = Project(name="project-a", status="active", created_by="alice")
        project_b = Project(name="project-b", status="active", created_by="bob")
        session.add_all([project_a, project_b])
        session.flush()
        session.add_all([
            ProjectMember(project_id=project_a.id, username="alice", role="viewer"),
            ProjectMember(project_id=project_b.id, username="bob", role="viewer"),
            ProjectInvestigation(
                project_id=project_a.id,
                agentguard_request_id="inv-a",
                created_by="alice",
                verification="verified",
                verification_source="live",
            ),
        ])
        project_a_id, project_b_id = project_a.id, project_b.id
        session.commit()

    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = settings
    upstream = LoopUpstream()
    app.state.agentguard_client = upstream
    app.state.audit_service = AuditService(settings)
    yield client, settings, upstream, project_a_id, project_b_id
    client.__exit__(None, None, None)
    dispose_engine(settings)


def login(client: TestClient, username: str = "alice") -> None:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": f"{username}-password-123"}
    )
    assert response.status_code == 200, response.text


def loop(loop_id: str = "loop-a", base_request_id: str = "inv-a") -> dict:
    return {"loop_id": loop_id, "base_request_id": base_request_id,
            "phase": "completed", "strategy": "information_value"}


def mapped_loops(settings) -> list[ProjectInvestigationLoop]:
    with Session(get_engine(settings)) as session:
        return list(session.scalars(select(ProjectInvestigationLoop)).all())


def test_authorized_list_registers_mapping_and_detail_uses_same_loop(loop_env) -> None:
    client, settings, upstream, project_a_id, _ = loop_env
    login(client)
    upstream.list_response = {
        "items": [loop()], "count": 1, "offset": 0, "limit": 100, "next_offset": None,
    }

    listed = client.get("/api/investigations/inv-a/loops")
    assert listed.status_code == 200
    assert listed.json()["meta"]["ownership_verified"] is True
    rows = mapped_loops(settings)
    assert len(rows) == 1
    assert (rows[0].project_id, rows[0].base_request_id, rows[0].loop_id) == (
        project_a_id, "inv-a", "loop-a")
    assert rows[0].verified_source == "agentguard"

    detail = client.get("/api/investigation-loops/loop-a")
    assert detail.status_code == 200
    assert detail.json()["loop_id"] == "loop-a"
    assert ("detail", "loop-a") in upstream.calls


def test_empty_list_succeeds_without_creating_mapping(loop_env) -> None:
    client, settings, upstream, *_ = loop_env
    login(client)
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert mapped_loops(settings) == []
    assert any(call[:2] == ("list", "inv-a") for call in upstream.calls)


def test_complete_multi_page_list_registers_all_loops_before_enabling_detail(loop_env) -> None:
    client, settings, upstream, project_a_id, _ = loop_env
    login(client)
    first_page = [loop(f"loop-{index}") for index in range(100)]
    last_page = [loop("loop-100")]
    upstream.list_pages = {
        0: {"items": first_page, "count": 100, "offset": 0, "limit": 100, "next_offset": 100},
        100: {"items": last_page, "count": 1, "offset": 100, "limit": 100, "next_offset": None},
    }

    listed = client.get("/api/investigations/inv-a/loops")
    assert listed.status_code == 200
    assert listed.json()["count"] == 101
    assert len(listed.json()["items"]) == 101
    assert [call[3] for call in upstream.calls if call[0] == "list"] == [0, 100]
    rows = mapped_loops(settings)
    assert len(rows) == 101
    assert all(row.project_id == project_a_id for row in rows)

    detail = client.get("/api/investigation-loops/loop-100")
    assert detail.status_code == 200
    assert ("detail", "loop-100") in upstream.calls


def test_invalid_loop_pagination_fails_before_any_ownership_write(loop_env) -> None:
    client, settings, upstream, *_ = loop_env
    login(client)
    upstream.list_response = {
        "items": [loop("loop-a")],
        "count": 1,
        "offset": 0,
        "limit": 100,
        "next_offset": 100,
    }

    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "INVALID_UPSTREAM_CONTRACT"
    assert mapped_loops(settings) == []


def test_loop_list_requires_the_complete_read_surface(loop_env) -> None:
    client, settings, upstream, *_ = loop_env
    login(client)
    upstream.operations["GET /v1/investigation-loops/{loop_id}/budget"] = False

    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "LOOP_READ_UNSUPPORTED"
    assert not any(call[0] == "list" for call in upstream.calls)
    assert mapped_loops(settings) == []


def test_repeated_list_registration_is_idempotent_and_survives_engine_restart(loop_env) -> None:
    client, settings, upstream, *_ = loop_env
    login(client)
    upstream.list_response = {
        "items": [loop()], "count": 1, "offset": 0, "limit": 100, "next_offset": None,
    }
    assert client.get("/api/investigations/inv-a/loops").status_code == 200
    assert client.get("/api/investigations/inv-a/loops").status_code == 200
    assert len(mapped_loops(settings)) == 1

    dispose_engine(settings)
    assert len(mapped_loops(settings)) == 1


def test_base_request_mismatch_rejects_list_without_writing(loop_env) -> None:
    client, settings, upstream, *_ = loop_env
    login(client)
    upstream.list_response = {
        "items": [loop(base_request_id="inv-other")], "count": 1,
        "offset": 0, "limit": 100, "next_offset": None,
    }
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "INVALID_UPSTREAM_CONTRACT"
    assert mapped_loops(settings) == []


def test_missing_identity_fields_rejects_upstream_contract(loop_env) -> None:
    client, settings, upstream, *_ = loop_env
    login(client)
    upstream.list_response = {
        "items": [{"loop_id": "loop-a"}], "count": 1,
        "offset": 0, "limit": 100, "next_offset": None,
    }
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "INVALID_UPSTREAM_CONTRACT"
    assert mapped_loops(settings) == []


def test_conflicting_base_investigation_ownership_is_rejected_before_upstream(loop_env) -> None:
    client, settings, upstream, _, project_b_id = loop_env
    with Session(get_engine(settings)) as session:
        session.add(ProjectInvestigation(project_id=project_b_id,
                                         agentguard_request_id="inv-a",
                                         created_by="bob", verification="verified"))
        session.commit()
    login(client)
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "INVESTIGATION_OWNERSHIP_CONFLICT"
    assert not any(call[0] == "list" for call in upstream.calls)
    assert mapped_loops(settings) == []


def test_legacy_or_demo_verified_base_is_not_trusted_as_live(loop_env) -> None:
    client, settings, upstream, *_ = loop_env
    with Session(get_engine(settings)) as session:
        base = session.scalar(select(ProjectInvestigation).where(
            ProjectInvestigation.agentguard_request_id == "inv-a"))
        base.verification_source = "unknown"
        session.commit()
    login(client)
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "INVESTIGATION_OWNERSHIP_UNVERIFIED"
    assert not any(call[0] == "list" for call in upstream.calls)


def test_loop_already_owned_by_another_project_rolls_back_whole_registration(loop_env) -> None:
    client, settings, upstream, _, project_b_id = loop_env
    with Session(get_engine(settings)) as session:
        session.add(ProjectInvestigationLoop(project_id=project_b_id,
                                             base_request_id="inv-b",
                                             loop_id="loop-conflict",
                                             created_by="bob",
                                             verified_source="agentguard"))
        session.commit()
    login(client)
    upstream.list_response = {
        "items": [loop("loop-new"), loop("loop-conflict")],
        "count": 2, "offset": 0, "limit": 100, "next_offset": None,
    }
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "LOOP_OWNERSHIP_CONFLICT"
    assert {row.loop_id for row in mapped_loops(settings)} == {"loop-conflict"}


def test_database_write_failure_returns_503_without_claiming_success(loop_env, monkeypatch) -> None:
    client, settings, upstream, *_ = loop_env
    login(client)
    upstream.list_response = {
        "items": [loop()], "count": 1, "offset": 0, "limit": 100, "next_offset": None,
    }
    original_open_session = resource_access.open_session
    calls = 0

    def fail_on_registration(db_settings):
        nonlocal calls
        calls += 1
        if calls >= 4:
            return None
        return original_open_session(db_settings)

    monkeypatch.setattr(resource_access, "open_session", fail_on_registration)
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "OWNERSHIP_STORAGE_UNAVAILABLE"
    assert mapped_loops(settings) == []


def test_upstream_timeout_is_not_returned_as_an_empty_list(loop_env) -> None:
    client, settings, upstream, *_ = loop_env
    login(client)
    upstream.list_error = AgentGuardError(504, "UPSTREAM_TIMEOUT", "AgentGuard request timed out")
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 504
    assert response.json()["detail"]["error"] == "UPSTREAM_TIMEOUT"
    assert mapped_loops(settings) == []


def test_unauthorized_user_cannot_trigger_any_upstream_request(loop_env) -> None:
    client, _settings, upstream, *_ = loop_env
    login(client, "bob")
    response = client.get("/api/investigations/inv-a/loops")
    assert response.status_code == 404
    assert upstream.calls == []


def test_unknown_loop_and_cross_project_loop_are_denied_before_upstream(loop_env) -> None:
    client, settings, upstream, project_a_id, *_ = loop_env
    with Session(get_engine(settings)) as session:
        session.add(ProjectInvestigationLoop(project_id=project_a_id,
                                             base_request_id="inv-a",
                                             loop_id="loop-owned-a",
                                             created_by="alice",
                                             verified_source="agentguard"))
        session.commit()

    login(client)
    unknown = client.get("/api/investigation-loops/not-mapped")
    assert unknown.status_code == 404
    assert upstream.calls == []

    login(client, "bob")
    cross_project = client.get("/api/investigation-loops/loop-owned-a")
    assert cross_project.status_code == 404
    assert upstream.calls == []
