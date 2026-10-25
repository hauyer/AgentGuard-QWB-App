"""B19 cross-project authorization tests (written first to reproduce real risk).

Fixture: one SQLite database, two projects with disjoint members, the same
shared AgentGuard stub credentials. Live-mode reads must be project-scoped via
project_investigations; demo namespace stays login-gated but project-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.db import dispose_engine, upgrade_database
from app.integrations.agentguard_client import AgentGuardClient
from app.main import create_app
from app.models.app import Project, ProjectInvestigation, ProjectMember, User
from app.services.audit_service import AuditService
from tests.conftest import _serve, make_settings
from tests.stub_agentguard import create_stub_app

STRONG_KEY = "b19-isolation-secret-key-0123456789abcdef"
_open_clients: list[TestClient] = []
_open_engines: list = []


@pytest.fixture(autouse=True)
def _teardown():
    _open_clients.clear()
    _open_engines.clear()
    yield
    for client in _open_clients:
        client.__exit__(None, None, None)
    for settings in _open_engines:
        dispose_engine(settings)


@pytest.fixture(scope="module")
def stub_url() -> str:
    return _serve(create_stub_app(kernel_status="available", warden_available=True))


@pytest.fixture()
def env(tmp_path: Path, stub_url: str):
    """App with DB + two projects; alice owns p-a (member), bob owns p-b."""
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        database_url=f"sqlite:///{(tmp_path / 'b19.db').as_posix()}",
    )
    upgrade_database(settings)

    from sqlalchemy.orm import Session

    from app.core.db import get_engine
    from app.core.passwords import hash_password

    with Session(get_engine(settings)) as session:
        for username, role, password in (
            ("alice", "admin", "alice-pw-12345"),
            ("bob", "analyst", "bob-pw-1234567"),
            ("carol", "analyst", "carol-pw-12345"),
            ("dave", "viewer", "dave-pw-123456"),
        ):
            session.add(User(username=username, role=role, display_name=username,
                             password_hash=hash_password(password), is_active=True))
        project_a = Project(name="p-a", description=None, status="active", created_by="alice")
        project_b = Project(name="p-b", description=None, status="active", created_by="bob")
        session.add_all([project_a, project_b])
        session.flush()
        session.add(ProjectMember(project_id=project_a.id, username="alice", role="admin", added_by="alice"))
        session.add(ProjectMember(project_id=project_a.id, username="carol", role="analyst", added_by="alice"))
        session.add(ProjectMember(project_id=project_b.id, username="bob", role="admin", added_by="bob"))
        session.add(ProjectInvestigation(project_id=project_a.id, agentguard_request_id="inv-stub-0001",
                                         created_by="alice", verification="verified",
                                         last_known_run_id="run-stub-0001"))
        session.add(ProjectInvestigation(project_id=project_b.id, agentguard_request_id="inv-b-0002",
                                         created_by="bob", verification="verified"))
        session.commit()

    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = make_settings(agentguard_base_url=stub_url, **settings.model_dump(include={
        "auth_enabled", "app_secret_key", "database_url"}))
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    app.state.audit_service = AuditService(app.state.settings)
    _open_clients.append(client)
    _open_engines.append(settings)
    return client, settings


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text


def _csrf(client: TestClient) -> dict:
    return {"X-CSRF-Token": client.cookies.get("qwb_csrf", "")}


# ------------------------------------------------------------------ #
# investigation access
# ------------------------------------------------------------------ #
def test_member_of_other_project_cannot_read_investigation(env) -> None:
    client, _settings = env
    _login(client, "bob", "bob-pw-1234567")  # bob is NOT a member of p-a
    response = client.get("/api/investigations/inv-stub-0001")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "INVESTIGATION_NOT_ACCESSIBLE"


def test_project_member_can_read_linked_investigation(env) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")  # carol is a p-a member
    response = client.get("/api/investigations/inv-stub-0001")
    assert response.status_code == 200
    assert response.json()["investigation"]["request_id"] == "inv-stub-0001"


def test_unlinked_live_investigation_hidden_from_non_admin(env) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")
    # known to the stub but linked to no project
    response = client.get("/api/investigations/inv-stub-graph-0002")
    assert response.status_code == 404


def test_live_list_returns_only_linked_investigations(env) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")
    body = client.get("/api/investigations").json()
    ids = [item.get("request_id") for item in body["items"]]
    assert "inv-stub-0001" in ids
    assert "inv-b-0002" not in ids


def test_global_admin_reads_unlinked_investigation(env) -> None:
    client, _settings = env
    _login(client, "alice", "alice-pw-12345")  # global admin
    response = client.get("/api/investigations/inv-stub-graph-0002")
    assert response.status_code == 200
    audit = client.get("/api/audit/events").json()
    assert any(event["action"] == "resource.admin_access" for event in audit["items"])


# ------------------------------------------------------------------ #
# evidence / defense / graph
# ------------------------------------------------------------------ #
@pytest.mark.parametrize("path", [
    "/api/evidence?request_id=inv-stub-0001",
    "/api/defense?request_id=inv-stub-0001",
    "/api/interaction-graph?request_id=inv-stub-0001",
])
def test_cross_project_object_reads_denied(env, path: str) -> None:
    client, _settings = env
    _login(client, "bob", "bob-pw-1234567")
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", [
    "/api/evidence?request_id=inv-stub-0001",
    "/api/defense?request_id=inv-stub-0001",
    "/api/interaction-graph?request_id=inv-stub-0001",
])
def test_member_reads_project_objects(env, path: str) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")
    assert client.get(path).status_code == 200


def test_cross_project_defense_preview_denied(env) -> None:
    client, _settings = env
    _login(client, "bob", "bob-pw-1234567")
    response = client.post("/api/defense/inv-stub-0001/preview", headers=_csrf(client))
    assert response.status_code == 404


# ------------------------------------------------------------------ #
# report access via run_id
# ------------------------------------------------------------------ #
def test_report_of_other_project_run_denied(env) -> None:
    client, _settings = env
    _login(client, "bob", "bob-pw-1234567")  # run-stub-0001 belongs to p-a
    response = client.get("/api/reports/run-stub-0001")
    assert response.status_code == 404
    export = client.get("/api/reports/run-stub-0001/export")
    assert export.status_code == 404


def test_report_of_project_run_allowed(env) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")
    assert client.get("/api/reports/run-stub-0001").status_code == 200
    assert client.get("/api/reports/run-stub-0001/export").status_code == 200


def test_unknown_run_id_denied_for_member(env) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")
    assert client.get("/api/reports/run-not-mapped").status_code == 404


# ------------------------------------------------------------------ #
# experiments / experiences scope (live)
# ------------------------------------------------------------------ #
def test_live_experiments_restricted_to_global_admin(env) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")
    response = client.get("/api/experiments")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "EXPERIMENTS_SCOPE_RESTRICTED"
    _login(client, "alice", "alice-pw-12345")
    assert client.get("/api/experiments").status_code == 200


def test_live_experiences_restricted_to_global_admin(env) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")
    response = client.get("/api/experiences")
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "EXPERIENCES_SCOPE_RESTRICTED"


def test_live_compare_restricted_to_global_admin(env) -> None:
    client, _settings = env
    _login(client, "carol", "carol-pw-12345")
    response = client.post("/api/experiments/compare", json={"run_ids": ["run-stub-0001", "run-stub-0002"]},
                           headers=_csrf(client))
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "EXPERIMENTS_SCOPE_RESTRICTED"


# ------------------------------------------------------------------ #
# demo namespace: login-gated, project-free, isolated
# ------------------------------------------------------------------ #
def test_demo_namespace_readable_by_any_authenticated_user(tmp_path: Path) -> None:
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        app_data_mode="synthetic",
        database_url=f"sqlite:///{(tmp_path / 'b19-demo.db').as_posix()}",
    )
    upgrade_database(settings)
    from sqlalchemy.orm import Session

    from app.core.db import get_engine
    from app.core.passwords import hash_password

    with Session(get_engine(settings)) as session:
        session.add(User(username="dave", role="viewer", display_name="d",
                         password_hash=hash_password("dave-pw-123456")))
        session.commit()
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = make_settings(agentguard_base_url="http://127.0.0.1:1",
                                       **settings.model_dump(include={
                                           "auth_enabled", "app_secret_key", "database_url", "app_data_mode"}))
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    app.state.audit_service = AuditService(app.state.settings)
    _open_clients.append(client)
    _open_engines.append(settings)

    _login(client, "dave", "dave-pw-123456")
    list_meta = client.get("/api/investigations").json()["meta"]
    # demo fixtures keep their recorded provenance label inside the synthetic run
    assert list_meta["data_mode"] in {"recorded", "synthetic"}
    assert client.get("/api/evidence", params={"request_id": "inv-qwb-0001"}).status_code == 200


# ------------------------------------------------------------------ #
# lifecycle: removal / deactivation / archive / shared request_id
# ------------------------------------------------------------------ #
def test_removed_member_loses_live_access(env) -> None:
    client, settings = env
    _login(client, "carol", "carol-pw-12345")
    assert client.get("/api/investigations/inv-stub-0001").status_code == 200

    from sqlalchemy.orm import Session

    from app.core.db import get_engine

    with Session(get_engine(settings)) as session:
        member = session.query(ProjectMember).filter_by(username="carol").one()
        session.delete(member)
        session.commit()
    assert client.get("/api/investigations/inv-stub-0001").status_code == 404


def test_deactivated_user_cannot_read(env) -> None:
    client, settings = env
    _login(client, "carol", "carol-pw-12345")

    from sqlalchemy.orm import Session

    from app.core.db import get_engine
    from app.models.app import User

    with Session(get_engine(settings)) as session:
        row = session.query(User).filter_by(username="carol").one()
        row.is_active = False
        session.commit()
    assert client.get("/api/investigations/inv-stub-0001").status_code == 401


def test_archived_project_allows_read_blocks_link(env) -> None:
    client, settings = env
    from sqlalchemy.orm import Session

    from app.core.db import get_engine

    with Session(get_engine(settings)) as session:
        project = session.query(Project).filter_by(name="p-a").one()
        project.status = "archived"
        session.commit()
    _login(client, "carol", "carol-pw-12345")
    assert client.get("/api/investigations/inv-stub-0001").status_code == 200
    response = client.post("/api/projects/1/investigations",
                           json={"agentguard_request_id": "inv-stub-graph-0002"}, headers=_csrf(client))
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "PROJECT_ARCHIVED"


def test_same_request_id_in_two_projects_both_members_can_read(tmp_path: Path, stub_url: str) -> None:
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        database_url=f"sqlite:///{(tmp_path / 'b19-shared.db').as_posix()}",
    )
    upgrade_database(settings)
    from sqlalchemy.orm import Session

    from app.core.db import get_engine
    from app.core.passwords import hash_password

    with Session(get_engine(settings)) as session:
        for username, password in (("alice", "alice-pw-12345"), ("bob", "bob-pw-1234567")):
            session.add(User(username=username, role="analyst", display_name=username,
                             password_hash=hash_password(password)))
        p1 = Project(name="p1", description=None, status="active", created_by="alice")
        p2 = Project(name="p2", description=None, status="active", created_by="bob")
        session.add_all([p1, p2])
        session.flush()
        session.add(ProjectMember(project_id=p1.id, username="alice", role="admin", added_by="alice"))
        session.add(ProjectMember(project_id=p2.id, username="bob", role="admin", added_by="bob"))
        # shared request_id uses a stub-known investigation so upstream 404s don't
        # mask the authorization flow
        session.add(ProjectInvestigation(project_id=p1.id, agentguard_request_id="inv-stub-0001",
                                         verification="verified"))
        session.add(ProjectInvestigation(project_id=p2.id, agentguard_request_id="inv-stub-0001",
                                         verification="verified"))
        session.commit()
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = make_settings(agentguard_base_url=stub_url, **settings.model_dump(include={
        "auth_enabled", "app_secret_key", "database_url"}))
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    app.state.audit_service = AuditService(app.state.settings)
    _open_clients.append(client)
    _open_engines.append(settings)

    _login(client, "alice", "alice-pw-12345")
    assert client.get("/api/investigations/inv-stub-0001").status_code == 200
    _login(client, "bob", "bob-pw-1234567")
    assert client.get("/api/investigations/inv-stub-0001").status_code == 200
