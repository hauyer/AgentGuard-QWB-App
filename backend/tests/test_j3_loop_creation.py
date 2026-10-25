"""J3: safe project-scoped loop creation and durable ambiguity recovery."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import dispose_engine, get_engine, upgrade_database
from app.core.passwords import hash_password
from app.integrations.agentguard_client import AgentGuardError
from app.main import create_app
from app.models.app import (
    InvestigationLoopSubmission,
    Project,
    ProjectInvestigation,
    ProjectInvestigationLoop,
    ProjectMember,
    User,
)
from app.services.audit_service import AuditService
from tests.conftest import make_settings

APP_SECRET = "j3-loop-create-secret-key-0123456789abcdef"
POST_OPERATION = "POST /v1/investigation-loops"
GET_OPERATION = "GET /v1/investigation-loops"


class LoopCreateUpstream:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.loops: list[dict] = []
        self.created: list[dict] = []
        self.create_error: AgentGuardError | None = None
        self.investigation_status = "completed"
        self.health_error: AgentGuardError | None = None
        self.operations = {POST_OPERATION: True, GET_OPERATION: True}
        self.discovery_error = None

    def close(self) -> None:
        return

    def health(self) -> dict:
        self.calls.append(("health",))
        if self.health_error:
            raise self.health_error
        return {"status": "ok"}

    def get_investigation(self, request_id: str) -> dict:
        self.calls.append(("investigation", request_id))
        return {"request_id": request_id, "status": self.investigation_status}

    def discover_operations(self) -> dict[str, bool]:
        self.calls.append(("discover",))
        return self.operations

    def list_investigation_loops(self, request_id: str, *, limit: int = 20, offset: int = 0) -> dict:
        self.calls.append(("list", request_id, limit, offset))
        rows = [row for row in self.loops if row["base_request_id"] == request_id]
        return {"items": rows[offset:offset + limit], "count": len(rows), "offset": offset, "limit": limit}

    def create_investigation_loop(self, payload: dict, *, idempotency_key: str) -> dict:
        self.calls.append(("create", idempotency_key, dict(payload)))
        self.created.append(dict(payload))
        if self.create_error:
            raise self.create_error
        row = {
            "loop_id": f"loop-{len(self.created)}",
            "base_request_id": payload["base_request_id"],
            "phase": "CREATED",
            "strategy": payload["strategy"],
            "rounds_executed": 0,
        }
        self.loops.append(row)
        return row

    def get_investigation_loop(self, loop_id: str) -> dict:
        self.calls.append(("loop_detail", loop_id))
        return next(row for row in self.loops if row["loop_id"] == loop_id)


@pytest.fixture
def loop_create_env(tmp_path: Path):
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=APP_SECRET,
        app_data_mode="live",
        agentguard_operator_api_token="operator-secret-for-tests",
        database_url=f"sqlite:///{(tmp_path / 'j3-loop-create.db').as_posix()}",
    )
    upgrade_database(settings)
    with Session(get_engine(settings)) as session:
        session.add_all([
            User(username="operator", role="operator", display_name="Operator",
                 password_hash=hash_password("operator-password-123"), is_active=True),
            User(username="viewer", role="viewer", display_name="Viewer",
                 password_hash=hash_password("viewer-password-123"), is_active=True),
        ])
        project = Project(name="j3-project", status="active", created_by="operator")
        session.add(project)
        session.flush()
        session.add_all([
            ProjectMember(project_id=project.id, username="operator", role="operator"),
            ProjectMember(project_id=project.id, username="viewer", role="viewer"),
            ProjectInvestigation(
                project_id=project.id,
                agentguard_request_id="inv-finished",
                created_by="operator",
                verification="verified",
                verification_source="live",
            ),
        ])
        project_id = project.id
        session.commit()

    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = settings
    upstream = LoopCreateUpstream()
    app.state.agentguard_client = upstream
    app.state.audit_service = AuditService(settings)
    yield client, settings, upstream, project_id
    client.__exit__(None, None, None)
    dispose_engine(settings)


def _login(client: TestClient, username: str = "operator") -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": f"{username}-password-123"},
    )
    assert response.status_code == 200, response.text


def _body(submission_id: str | None = None, **overrides) -> dict:
    return {
        "submission_id": submission_id or str(uuid4()),
        "strategy": "information_value",
        "max_actions": 8,
        "max_seconds": 300,
        "max_model_calls": 4,
        "no_new_evidence_rounds": 2,
        "data_partition": "held_out_family",
        **overrides,
    }


def _submit(client: TestClient, body: dict, *, headers: dict | None = None):
    return client.post(
        "/api/investigations/inv-finished/loops",
        json=body,
        headers=headers or {"X-CSRF-Token": client.cookies.get("qwb_csrf", "")},
    )


def test_live_create_persists_verified_ownership_and_is_idempotent(loop_create_env) -> None:
    client, settings, upstream, project_id = loop_create_env
    _login(client)
    body = _body()

    created = _submit(client, body)
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["meta"] == {"data_mode": "live", "source": "agentguard"}
    assert payload["submission"]["status"] == "COMPLETED"
    assert payload["loop"]["loop_id"] == "loop-1"
    with Session(get_engine(settings)) as session:
        mapping = session.scalar(select(ProjectInvestigationLoop))
        submission = session.scalar(select(InvestigationLoopSubmission))
        assert mapping is not None
        assert (mapping.project_id, mapping.base_request_id, mapping.loop_id, mapping.verified_source) == (
            project_id, "inv-finished", "loop-1", "agentguard")
        assert submission is not None and submission.status == "COMPLETED"
        saved_key = submission.idempotency_key

    replay = _submit(client, body)
    assert replay.status_code == 200
    assert replay.json()["submission"]["loop_id"] == "loop-1"
    assert len([call for call in upstream.calls if call[0] == "create"]) == 1
    assert saved_key == next(call[1] for call in upstream.calls if call[0] == "create")
    assert len([call for call in upstream.calls if call[0] == "list"]) == 1


def test_same_submission_id_with_different_parameters_conflicts(loop_create_env) -> None:
    client, _, upstream, _ = loop_create_env
    _login(client)
    submission_id = str(uuid4())
    assert _submit(client, _body(submission_id)).status_code == 201

    changed = _submit(client, _body(submission_id, max_actions=9))
    assert changed.status_code == 409
    assert changed.json()["detail"]["error"] == "SUBMISSION_IDEMPOTENCY_CONFLICT"
    assert len([call for call in upstream.calls if call[0] == "create"]) == 1


def test_pinned_version_without_create_capability_does_not_send_post(loop_create_env) -> None:
    client, _, upstream, _ = loop_create_env
    _login(client)
    upstream.operations[POST_OPERATION] = False

    response = _submit(client, _body())
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "LOOP_CREATE_UNSUPPORTED"
    assert not [call for call in upstream.calls if call[0] == "create"]


def test_unfinished_base_investigation_is_rejected(loop_create_env) -> None:
    client, _, upstream, _ = loop_create_env
    _login(client)
    upstream.investigation_status = "running"

    response = _submit(client, _body())
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "BASE_INVESTIGATION_NOT_FINISHED"
    assert not [call for call in upstream.calls if call[0] in {"discover", "create"}]


def test_global_viewer_cannot_create(loop_create_env) -> None:
    client, _, upstream, _ = loop_create_env
    _login(client, "viewer")

    response = _submit(client, _body())
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "PERMISSION_DENIED"
    assert not upstream.calls


def test_csrf_failure_is_rejected_before_upstream(loop_create_env) -> None:
    client, _, upstream, _ = loop_create_env
    _login(client)

    response = _submit(client, _body(), headers={"X-CSRF-Token": "bad-token"})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "CSRF_MISMATCH"
    assert not upstream.calls


def test_timeout_is_persisted_ambiguous_and_never_blindly_reposted(loop_create_env) -> None:
    client, settings, upstream, _ = loop_create_env
    _login(client)
    upstream.create_error = AgentGuardError(0, "UPSTREAM_UNAVAILABLE", "AgentGuard request timed out")
    body = _body()

    response = _submit(client, body)
    assert response.status_code == 503
    assert response.json()["submission"]["status"] == "SUBMISSION_AMBIGUOUS"
    assert len([call for call in upstream.calls if call[0] == "create"]) == 1
    with Session(get_engine(settings)) as session:
        row = session.scalar(select(InvestigationLoopSubmission))
        assert row is not None
        assert row.status == "SUBMISSION_AMBIGUOUS"
        idempotency_key = row.idempotency_key

    replay = _submit(client, body)
    assert replay.status_code == 503
    assert replay.json()["submission"]["status"] == "SUBMISSION_AMBIGUOUS"
    assert len([call for call in upstream.calls if call[0] == "create"]) == 1
    assert idempotency_key == next(call[1] for call in upstream.calls if call[0] == "create")


def test_timeout_reconciles_a_single_new_loop_and_recovers_local_link(loop_create_env) -> None:
    client, settings, upstream, project_id = loop_create_env
    _login(client)
    upstream.create_error = AgentGuardError(0, "UPSTREAM_UNAVAILABLE", "response lost")
    body = _body()
    first = _submit(client, body)
    assert first.status_code == 503

    upstream.create_error = None
    upstream.loops.append({
        "loop_id": "created-before-timeout",
        "base_request_id": "inv-finished",
        "phase": "CREATED",
        "strategy": "information_value",
    })
    recovered = _submit(client, body)
    assert recovered.status_code == 201
    assert recovered.json()["submission"]["status"] == "COMPLETED"
    assert recovered.json()["submission"]["loop_id"] == "created-before-timeout"
    assert len([call for call in upstream.calls if call[0] == "create"]) == 1
    assert len([call for call in upstream.calls if call[0] == "loop_detail"]) == 1
    with Session(get_engine(settings)) as session:
        mapping = session.scalar(select(ProjectInvestigationLoop))
        assert mapping is not None and mapping.project_id == project_id


def test_submission_status_remains_readable_when_agentguard_is_offline(loop_create_env) -> None:
    client, _, upstream, _ = loop_create_env
    _login(client)
    upstream.create_error = AgentGuardError(0, "UPSTREAM_UNAVAILABLE", "timeout")
    body = _body()
    assert _submit(client, body).status_code == 503
    upstream.health_error = AgentGuardError(0, "API_UNREACHABLE", "offline")

    response = client.get(
        f"/api/investigations/inv-finished/loop-submissions/{body['submission_id']}"
    )
    assert response.status_code == 200
    assert response.json()["submission"]["status"] == "SUBMISSION_AMBIGUOUS"
    assert len([call for call in upstream.calls if call[0] == "create"]) == 1
    assert len([call for call in upstream.calls if call[0] == "list"]) == 1
    assert not [call for call in upstream.calls if call[0] == "loop_detail"]


def test_missing_operator_token_blocks_creation(loop_create_env) -> None:
    client, _, upstream, _ = loop_create_env
    _login(client)
    client.app.state.settings.agentguard_operator_api_token = None

    response = _submit(client, _body())
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "OPERATOR_TOKEN_REQUIRED"
    assert not [call for call in upstream.calls if call[0] in {"discover", "create"}]


def test_operator_global_role_still_requires_project_operator(loop_create_env) -> None:
    client, _, upstream, _ = loop_create_env
    _login(client, "operator")
    with Session(get_engine(client.app.state.settings)) as session:
        member = session.scalar(
            select(ProjectMember).where(ProjectMember.username == "operator")
        )
        assert member is not None
        member.role = "viewer"
        session.commit()

    response = _submit(client, _body())
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "PERMISSION_DENIED"
    assert not [call for call in upstream.calls if call[0] in {"discover", "create"}]
