"""B12 project management and permission isolation tests.

All flows run against a per-test SQLite database (migrations applied) so
membership, audit and isolation behave exactly as in production. A global
analyst must NOT read a project they are not a member of; project-scoped roles
govern what members can do inside their project.
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
from tests.conftest import make_settings

STRONG_KEY = "b12-project-secret-key-0123456789abcdef"
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


@pytest.fixture()
def db_env(tmp_path: Path):
    """App + client wired to a fresh SQLite database with B12 users seeded."""
    db_path = tmp_path / "b12.db"
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        database_url=f"sqlite:///{db_path.as_posix()}",
        # demo accounts stay enabled in development, which is exactly what the
        # mixed-identity tests below exercise
    )
    upgrade_database(settings)

    from sqlalchemy.orm import Session

    from app.core.db import get_engine
    from app.core.passwords import hash_password

    with Session(get_engine(settings)) as session:
        session.add(User(username="alice", role="admin", display_name="Alice",
                         password_hash=hash_password("alice-pw-123456"), is_active=True))
        session.add(User(username="bob", role="analyst", display_name="Bob",
                         password_hash=hash_password("bob-pw-1234567"), is_active=True))
        session.add(User(username="carol", role="viewer", display_name="Carol",
                         password_hash=hash_password("carol-pw-123456"), is_active=True))
        session.add(User(username="dave", role="analyst", display_name="Dave",
                         password_hash=hash_password("dave-pw-12345678"), is_active=True))
        session.commit()

    app = create_app()
    client = TestClient(app)
    client.__enter__()
    overrides = settings.model_dump(include={"auth_enabled", "app_secret_key", "database_url"})
    app.state.settings = make_settings(agentguard_base_url="http://127.0.0.1:1", **overrides)
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


def _seed_project(settings, *, name: str, owner: str = "alice", members: dict[str, str] | None = None) -> int:
    from sqlalchemy.orm import Session

    from app.core.db import get_engine

    with Session(get_engine(settings)) as session:
        project = Project(name=name, description="seed", status="active", created_by=owner)
        session.add(project)
        session.flush()
        memberships = {owner: "admin", **(members or {})}
        for username, role in memberships.items():
            session.add(ProjectMember(project_id=project.id, username=username, role=role,
                                      added_by=owner))
        session.commit()
        return project.id


def _link_investigation(settings, project_id: int, request_id: str) -> None:
    from sqlalchemy.orm import Session

    from app.core.db import get_engine

    with Session(get_engine(settings)) as session:
        session.add(ProjectInvestigation(
            project_id=project_id, agentguard_request_id=request_id,
            created_by="alice", verification="verified"))
        session.commit()


# ------------------------------------------------------------------ #
# unauthenticated / unauthorised access
# ------------------------------------------------------------------ #
def test_unauthenticated_project_access_rejected(db_env) -> None:
    client, _settings = db_env
    project_id = _seed_project(_settings, name="p-unauth")
    assert client.get("/api/projects").status_code == 401
    assert client.get(f"/api/projects/{project_id}").status_code == 401
    assert client.get(f"/api/projects/{project_id}/members").status_code == 401
    response = client.post("/api/projects", json={"name": "x"})
    assert response.status_code == 401


def test_global_analyst_cannot_read_project_without_membership(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-private", owner="alice")
    _login(client, "dave", "dave-pw-12345678")  # global analyst, no membership
    response = client.get(f"/api/projects/{project_id}")
    # Uniform 404: outsiders must not even learn the project exists.
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "PROJECT_NOT_FOUND"


def test_project_list_shows_only_member_projects_for_non_admin(db_env) -> None:
    client, settings = db_env
    mine = _seed_project(settings, name="p-mine", members={"bob": "analyst"})
    _seed_project(settings, name="p-secret", owner="alice")
    _login(client, "bob", "bob-pw-1234567")
    body = client.get("/api/projects").json()
    ids = [item["project_id"] for item in body["items"]]
    assert mine in ids and all(item["name"] != "p-secret" for item in body["items"])


# ------------------------------------------------------------------ #
# project lifecycle
# ------------------------------------------------------------------ #
def test_analyst_creates_project_and_becomes_member_admin(db_env) -> None:
    client, _settings = db_env
    _login(client, "bob", "bob-pw-1234567")
    response = client.post("/api/projects", json={"name": "bob-project", "description": "d"},
                           headers=_csrf(client))
    assert response.status_code == 201, response.text
    payload = response.json()["created"]
    assert payload["created_by"] == "bob"
    assert {"username": "bob", "role": "admin"} in [
        {"username": m["username"], "role": m["role"]} for m in payload["members"]]


def test_duplicate_project_name_rejected(db_env) -> None:
    client, settings = db_env
    _seed_project(settings, name="dup")
    _login(client, "bob", "bob-pw-1234567")
    response = client.post("/api/projects", json={"name": "dup"}, headers=_csrf(client))
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "PROJECT_EXISTS"


def test_member_without_admin_role_cannot_add_members(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-roles", owner="alice",
                               members={"bob": "analyst", "carol": "viewer"})
    _login(client, "bob", "bob-pw-1234567")  # member but project role analyst
    response = client.post(f"/api/projects/{project_id}/members",
                           json={"username": "carol", "role": "viewer"}, headers=_csrf(client))
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "PERMISSION_DENIED"


def test_project_admin_adds_and_removes_member(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-admin", owner="alice")
    _login(client, "alice", "alice-pw-123456")
    added = client.post(f"/api/projects/{project_id}/members",
                        json={"username": "bob", "role": "analyst"}, headers=_csrf(client))
    assert added.status_code == 201, added.text
    duplicate = client.post(f"/api/projects/{project_id}/members",
                            json={"username": "bob", "role": "analyst"}, headers=_csrf(client))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["error"] == "MEMBER_EXISTS"
    removed = client.delete(f"/api/projects/{project_id}/members/bob", headers=_csrf(client))
    assert removed.status_code == 200
    missing = client.delete(f"/api/projects/{project_id}/members/bob", headers=_csrf(client))
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "MEMBER_NOT_FOUND"


def test_last_project_admin_cannot_be_removed(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-lastadmin", owner="alice")
    _login(client, "alice", "alice-pw-123456")
    response = client.delete(f"/api/projects/{project_id}/members/alice", headers=_csrf(client))
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "LAST_PROJECT_ADMIN"


def test_removed_member_loses_access_immediately(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-revoke", owner="alice",
                               members={"bob": "analyst"})
    _login(client, "alice", "alice-pw-123456")
    client.delete(f"/api/projects/{project_id}/members/bob", headers=_csrf(client))
    _login(client, "bob", "bob-pw-1234567")
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_deactivated_user_loses_project_access(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-deactivate", owner="alice",
                               members={"bob": "analyst"})
    _login(client, "bob", "bob-pw-1234567")
    assert client.get(f"/api/projects/{project_id}").status_code == 200

    from sqlalchemy.orm import Session

    from app.core.db import get_engine
    from app.models.app import User

    with Session(get_engine(settings)) as session:
        row = session.query(User).filter_by(username="bob").one()
        row.is_active = False
        session.commit()
    # Existing signed session must stop working on the next request.
    assert client.get(f"/api/projects/{project_id}").status_code == 401


def test_project_archive_blocks_writes_but_reads_remain(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-archive", owner="alice",
                               members={"bob": "analyst"})
    _login(client, "alice", "alice-pw-123456")
    archived = client.patch(f"/api/projects/{project_id}", json={"status": "archived"},
                            headers=_csrf(client))
    assert archived.status_code == 200
    assert archived.json()["updated"]["status"] == "archived"
    assert client.get(f"/api/projects/{project_id}").status_code == 200
    add_member = client.post(f"/api/projects/{project_id}/members",
                             json={"username": "carol", "role": "viewer"}, headers=_csrf(client))
    assert add_member.status_code == 409
    assert add_member.json()["detail"]["error"] == "PROJECT_ARCHIVED"


# ------------------------------------------------------------------ #
# investigation linking
# ------------------------------------------------------------------ #
def test_link_unknown_investigation_rejected_when_upstream_unavailable(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-link", owner="alice",
                               members={"bob": "analyst"})
    _login(client, "bob", "bob-pw-1234567")
    response = client.post(f"/api/projects/{project_id}/investigations",
                           json={"agentguard_request_id": "inv-unknown-1"}, headers=_csrf(client))
    # Upstream is unreachable in this test; the link must be refused rather
    # than recorded as unverified - no fabricated references.
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "VERIFICATION_UNAVAILABLE"


def test_link_verification_against_live_stub(tmp_path: Path) -> None:
    """With a reachable AgentGuard stub, unknown IDs are refused and known IDs link."""
    from sqlalchemy.orm import Session

    from app.core.db import get_engine
    from app.core.passwords import hash_password
    from app.models.app import User
    from tests.stub_agentguard import create_stub_app

    settings = make_settings(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        database_url=f"sqlite:///{(tmp_path / 'b12b.db').as_posix()}",
        agentguard_api_token=None,
    )
    upgrade_database(settings)
    with Session(get_engine(settings)) as session:
        session.add(User(username="alice", role="admin", display_name="A",
                         password_hash=hash_password("alice-pw-123456")))
        session.commit()

    from tests.conftest import _serve

    stub_url = _serve(create_stub_app(kernel_status="available", warden_available=True))

    app = create_app()
    client = TestClient(app)
    client.__enter__()
    overrides = settings.model_dump(include={"auth_enabled", "app_secret_key", "database_url"})
    app.state.settings = make_settings(agentguard_base_url=stub_url, **overrides)
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    app.state.audit_service = AuditService(app.state.settings)
    _open_clients.append(client)
    _open_engines.append(settings)

    project_id = _seed_project(settings, name="p-live-link")
    _login(client, "alice", "alice-pw-123456")
    unknown = client.post(f"/api/projects/{project_id}/investigations",
                          json={"agentguard_request_id": "inv-not-upstream"},
                          headers=_csrf(client))
    assert unknown.status_code == 422
    assert unknown.json()["detail"]["error"] == "INVESTIGATION_NOT_FOUND"

    known = client.post(f"/api/projects/{project_id}/investigations",
                        json={"agentguard_request_id": "inv-stub-0001",
                              "display_name": "stub investigation"},
                        headers=_csrf(client))
    assert known.status_code == 201, known.text
    assert known.json()["linked"]["verification"] == "verified"
    duplicate = client.post(f"/api/projects/{project_id}/investigations",
                            json={"agentguard_request_id": "inv-stub-0001"},
                            headers=_csrf(client))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["error"] == "INVESTIGATION_LINKED"


# ------------------------------------------------------------------ #
# audit persistence and filtering
# ------------------------------------------------------------------ #
def test_project_writes_are_audited_with_scope(db_env) -> None:
    client, settings = db_env
    project_id = _seed_project(settings, name="p-audit", owner="alice")
    _login(client, "alice", "alice-pw-123456")
    client.post("/api/projects", json={"name": "p-audit-2"}, headers=_csrf(client))
    client.post(f"/api/projects/{project_id}/members",
                json={"username": "carol", "role": "viewer"}, headers=_csrf(client))
    client.patch(f"/api/projects/{project_id}", json={"status": "archived"}, headers=_csrf(client))

    audit = client.get("/api/audit/events", params={"limit": 50}).json()
    assert audit["persisted"] is True
    actions = {item["action"] for item in audit["items"]}
    assert {"project.create", "project.member.add", "project.update"} <= actions
    scoped = client.get("/api/audit/events", params={"project_id": project_id}).json()
    assert scoped["total"] >= 2
    assert all(item["project_id"] == project_id for item in scoped["items"])

    # restart survival: a fresh service over the same DB sees the same events
    from app.services.audit_service import AuditService as AS

    fresh = AS(settings)
    items, total = fresh.query(action="project.create")
    assert total >= 1  # the API-created project (seeds write directly to the DB)
