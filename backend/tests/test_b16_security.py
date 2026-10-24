"""B16 security and reliability regressions.

Covers: login rate limiting, login failure/success auditing, report export
filename sanitization, and concurrency smoke on project membership.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.integrations.agentguard_client import AgentGuardClient
from app.main import create_app
from tests.conftest import make_settings

STRONG_KEY = "b16-security-secret-key-0123456789abcdef"
_open_clients: list[TestClient] = []


@pytest.fixture(autouse=True)
def _close_clients():
    _open_clients.clear()
    yield
    for client in _open_clients:
        client.__exit__(None, None, None)
    import app.api.routes.auth as auth_module

    auth_module._login_failures.clear()


def _client(base_url: str = "http://127.0.0.1:1", **overrides) -> TestClient:
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = make_settings(agentguard_base_url=base_url, **overrides)
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    _open_clients.append(client)
    return client


def _auth_client(**overrides) -> TestClient:
    return _client(auth_enabled=True, app_secret_key=STRONG_KEY, **overrides)


def test_login_rate_limited_after_repeated_failures() -> None:
    client = _auth_client(app_data_mode="synthetic")
    for _ in range(10):
        response = client.post("/api/auth/login", json={"username": "operator", "password": "wrong"})
        assert response.status_code == 401
    throttled = client.post("/api/auth/login", json={"username": "operator", "password": "operator-demo"})
    assert throttled.status_code == 429
    assert throttled.json()["detail"]["error"] == "TOO_MANY_ATTEMPTS"
    # a different username is not affected by the first one's counter
    other = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer-demo"})
    assert other.status_code == 200


def test_login_events_are_audited() -> None:
    client = _auth_client(app_data_mode="synthetic")
    client.post("/api/auth/login", json={"username": "operator", "password": "wrong"})
    client.post("/api/auth/login", json={"username": "operator", "password": "operator-demo"})
    audit = client.get("/api/audit/events").json()
    actions = [item["action"] for item in audit["items"]]
    assert "auth.login.failed" in actions
    assert "auth.login.success" in actions
    # failed logins must never record the attempted password
    failed = next(item for item in audit["items"] if item["action"] == "auth.login.failed")
    assert "wrong" not in (failed["detail"] or "")


def test_report_export_filename_is_sanitized(stub_base_url: str) -> None:
    client = _client(stub_base_url)
    # header injection attempt without path separators (FastAPI would split on '/')
    hostile = 'run-x"%0d%0aX-Injected:%201'
    response = client.get(f"/api/reports/{hostile}/export")
    if response.status_code == 200:
        disposition = response.headers["content-disposition"]
        # hostile CRLF must be neutralized into a single-line safe filename
        assert "\r" not in disposition and "\n" not in disposition
        assert disposition.startswith("attachment; filename=\"report-")
        assert disposition.endswith(".pdf\"")
        assert response.headers.get("x-injected") is None
    else:
        # upstream rejected the id - no injection surface either
        assert response.status_code in {404, 422, 502}


def test_concurrent_project_member_add_is_safe(tmp_path) -> None:
    """Parallel duplicate adds must not create two memberships."""
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy.orm import Session

    from app.core.config import Settings
    from app.core.db import dispose_engine, get_engine, upgrade_database
    from app.core.passwords import hash_password
    from app.models.app import Project, User
    from app.services.auth_service import AppUser
    from app.services.project_service import ProjectServiceError, add_member, require_project_access
    from tests.conftest import make_settings as _ms

    settings: Settings = _ms(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        database_url=f"sqlite:///{(tmp_path / 'b16.db').as_posix()}",
    )
    upgrade_database(settings)
    with Session(get_engine(settings)) as session:
        session.add(User(username="owner", role="admin", display_name="O",
                         password_hash=hash_password("owner-pw-12345")))
        session.add(Project(name="p-concurrent", description=None, status="active", created_by="owner"))
        session.commit()
    owner = AppUser(username="owner", display_name="O", role="admin", source="database")

    def attempt(_: int) -> str:
        try:
            context = require_project_access(settings, owner, 1, required_role="admin")
            add_member(settings, context, actor=owner, username="newcomer", role="viewer")
            return "added"
        except ProjectServiceError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))
    assert results.count("added") == 1
    assert results.count("MEMBER_EXISTS") == 3
    dispose_engine(settings)
