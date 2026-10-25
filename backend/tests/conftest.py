"""Shared fixtures for backend tests.

The AgentGuard stub is served over real HTTP (uvicorn on an ephemeral port) so
the connector is exercised through the same network path as production. The stub
is a documented contract stand-in, never a claim of real WARDEN availability.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.agentguard_client import AgentGuardClient
from app.main import create_app
from app.services.audit_service import AuditService
from tests.stub_agentguard import create_stub_app


def make_settings(**overrides) -> Settings:
    base = {
        "agentguard_base_url": "http://127.0.0.1:8000",
        "agentguard_api_token": None,
        "agentguard_operator_api_token": None,
        "agentguard_api_timeout": 15.0,
        "app_cors_origins": "http://localhost:5173",
    }
    base.update(overrides)
    return Settings(**base)


class _StubServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:
        # No signal handlers inside a test thread.
        return


def _serve(app) -> str:
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = _StubServer(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("stub server did not start")
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    return f"http://127.0.0.1:{port}"


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def stub_base_url() -> Iterator[str]:
    yield _serve(create_stub_app())


@pytest.fixture(scope="session")
def stub_base_url_warden_available() -> Iterator[str]:
    yield _serve(create_stub_app(kernel_status="available", warden_available=True))


@pytest.fixture(scope="session")
def stub_base_url_capabilities_fail() -> Iterator[str]:
    yield _serve(create_stub_app(capabilities_status=500))


@pytest.fixture
def unreachable_base_url() -> str:
    return f"http://127.0.0.1:{_unused_port()}"


B19_SECRET = "b19-fixture-secret-key-0123456789abcdef"


@pytest.fixture()
def live_project_env(tmp_path: Path, stub_base_url_warden_available: str):
    """Wired app for B19+ tests: DB-backed users, a project with alice (admin)
    as member, and the stub investigation linked. Live objects are reachable
    only through this project membership."""
    from sqlalchemy.orm import Session

    from app.core.db import dispose_engine, get_engine, upgrade_database
    from app.core.passwords import hash_password
    from app.models.app import Project, ProjectInvestigation, ProjectMember, User

    settings = make_settings(
        auth_enabled=True,
        app_secret_key=B19_SECRET,
        database_url=f"sqlite:///{(tmp_path / 'b19env.db').as_posix()}",
    )
    upgrade_database(settings)
    with Session(get_engine(settings)) as session:
        session.add(User(username="alice", role="admin", display_name="alice",
                         password_hash=hash_password("alice-pw-12345"), is_active=True))
        project = Project(name="p-live", description=None, status="active", created_by="alice")
        session.add(project)
        session.flush()
        session.add(ProjectMember(project_id=project.id, username="alice", role="admin", added_by="alice"))
        session.add(ProjectInvestigation(project_id=project.id, agentguard_request_id="inv-stub-0001",
                                         created_by="alice", verification="verified",
                                         last_known_run_id="run-stub-0001"))
        session.commit()

    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = make_settings(agentguard_base_url=stub_base_url_warden_available,
                                       **settings.model_dump(include={
                                           "auth_enabled", "app_secret_key", "database_url"}))
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    app.state.audit_service = AuditService(app.state.settings)

    def login(username: str = "alice", password: str = "alice-pw-12345") -> None:  # noqa: S107 - fixture credentials
        response = client.post("/api/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text

    yield client, settings, login
    client.__exit__(None, None, None)
    dispose_engine(settings)
