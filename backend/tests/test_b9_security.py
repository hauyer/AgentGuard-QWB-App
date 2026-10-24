"""B9 security regression tests.

Covers the hardening commitments:
  * fail-closed configuration (no fallback secret, production posture enforced)
  * demo accounts restricted to development/demo environments
  * database users with PBKDF2 password hashes (login + deactivation)
  * audit event persistence, pagination, filters and restart survival
  * proxy-independent upstream connection (trust_env=False)
  * PDF rendering input safety (escaping of upstream-controlled fields)
  * strict data-mode separation (forced live never faked when unreachable)
  * session lifetime and CSRF cookie lifetime alignment
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import dispose_engine, upgrade_database
from app.core.passwords import hash_password, is_hashed_password, verify_password
from app.core.security import verify_session
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardUnavailable
from app.main import create_app
from app.models.app import User
from app.schemas.investigations import CreateInvestigationRequest
from app.services.audit_service import AuditService
from app.services.auth_service import verify_credentials
from app.services.investigations_service import InvestigationServiceError, create_investigation
from app.services.reports_service import render_report_pdf
from tests.conftest import make_settings

_open_clients: list[TestClient] = []

STRONG_KEY = "b9-regression-secret-key-0123456789abcdef"


@pytest.fixture(autouse=True)
def _close_clients():
    _open_clients.clear()
    yield
    for client in _open_clients:
        client.__exit__(None, None, None)


def _client(base_url: str, **overrides) -> tuple[TestClient, object]:
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    app.state.settings = make_settings(agentguard_base_url=base_url, **overrides)
    app.state.agentguard_client = AgentGuardClient(app.state.settings)
    app.state.audit_service = AuditService(app.state.settings)
    _open_clients.append(client)
    return client, app


# ------------------------------------------------------------------ #
# B9-1: fail-closed configuration
# ------------------------------------------------------------------ #
def test_auth_enabled_without_secret_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        make_settings(auth_enabled=True)


def test_empty_secret_key_is_rejected_when_auth_enabled() -> None:
    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        make_settings(auth_enabled=True, app_secret_key="   ")


def test_production_requires_auth() -> None:
    with pytest.raises(ValueError, match="AUTH_ENABLED"):
        make_settings(
            app_env="production",
            app_secret_key=STRONG_KEY,
            session_cookie_secure=True,
            database_url="sqlite:///./b9-prod-test.db",
        )


def test_production_requires_strong_secret() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        make_settings(
            app_env="production",
            auth_enabled=True,
            app_secret_key="short",
            session_cookie_secure=True,
            database_url="sqlite:///./b9-prod-test.db",
        )


def test_production_requires_secure_cookies() -> None:
    with pytest.raises(ValueError, match="SESSION_COOKIE_SECURE"):
        make_settings(
            app_env="production",
            auth_enabled=True,
            app_secret_key=STRONG_KEY,
            database_url="sqlite:///./b9-prod-test.db",
        )


def test_production_requires_database_url() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL"):
        make_settings(app_env="production", auth_enabled=True, app_secret_key=STRONG_KEY, session_cookie_secure=True)


def test_signing_refuses_missing_secret_even_if_bypassed() -> None:
    """Defence in depth: even if a misconfigured Settings object is constructed
    directly, the signing helpers raise instead of using a fallback key."""
    from app.core.security import SecretKeyNotConfigured, issue_session

    settings = Settings(app_secret_key="", auth_enabled=False)  # dev: config passes
    with pytest.raises(SecretKeyNotConfigured):
        issue_session(settings, "someone")


def test_invalid_app_env_rejected() -> None:
    with pytest.raises(ValueError, match="APP_ENV"):
        make_settings(app_env="staging")


# ------------------------------------------------------------------ #
# B9-2: demo accounts are environment-gated
# ------------------------------------------------------------------ #
def test_demo_accounts_enabled_in_development() -> None:
    settings = make_settings()
    assert settings.demo_users_enabled is True
    assert verify_credentials(settings, "admin", "admin-demo") is not None


def test_demo_accounts_enabled_in_demo_env() -> None:
    settings = make_settings(app_env="demo")
    assert settings.demo_users_enabled is True


def test_demo_accounts_rejected_in_production_regardless_of_flag() -> None:
    settings = make_settings(
        app_env="production",
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        session_cookie_secure=True,
        database_url="sqlite:///./b9-prod-test.db",
        auth_demo_users_enabled=True,  # even an explicit override is ignored
    )
    assert settings.demo_users_enabled is False
    assert verify_credentials(settings, "admin", "admin-demo") is None


def test_demo_accounts_can_be_disabled_in_development() -> None:
    settings = make_settings(auth_demo_users_enabled=False)
    assert settings.demo_users_enabled is False
    assert verify_credentials(settings, "admin", "admin-demo") is None


def test_login_rejects_demo_credentials_when_demo_users_disabled(tmp_path: Path) -> None:
    db_path = tmp_path / "users.db"
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        auth_demo_users_enabled=False,
        database_url=f"sqlite:///{db_path.as_posix()}",
    )
    upgrade_database(settings)
    from sqlalchemy.orm import Session

    from app.core.db import get_engine

    with Session(get_engine(settings)) as session:
        session.add(
            User(username="real-analyst", role="analyst", display_name="Real", password_hash=hash_password("s3cret!pw"))
        )
        session.commit()

    client, _app = _client("http://127.0.0.1:1", **settings.model_dump(include={
        "auth_enabled", "app_secret_key", "auth_demo_users_enabled", "database_url",
    }))
    demo_login = client.post("/api/auth/login", json={"username": "analyst", "password": "analyst-demo"})
    assert demo_login.status_code == 401
    real_login = client.post("/api/auth/login", json={"username": "real-analyst", "password": "s3cret!pw"})
    assert real_login.status_code == 200
    assert real_login.json()["user"]["source"] == "database"
    dispose_engine(settings)


def test_deactivated_database_user_session_is_rejected(tmp_path: Path) -> None:
    db_path = tmp_path / "users2.db"
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        database_url=f"sqlite:///{db_path.as_posix()}",
    )
    upgrade_database(settings)
    from sqlalchemy.orm import Session

    from app.core.db import get_engine

    with Session(get_engine(settings)) as session:
        session.add(
            User(username="temp-admin", role="admin", display_name="Temp", password_hash=hash_password("hunter22334"))
        )
        session.commit()

    overrides = settings.model_dump(include={"auth_enabled", "app_secret_key", "database_url"})
    client, _app = _client("http://127.0.0.1:1", **overrides)
    ok = client.post("/api/auth/login", json={"username": "temp-admin", "password": "hunter22334"})
    assert ok.status_code == 200
    assert client.get("/api/system/settings").status_code == 200

    # Deactivate; the still-valid signed cookie must stop working immediately.
    with Session(get_engine(settings)) as session:
        row = session.query(User).filter_by(username="temp-admin").one()
        row.is_active = False
        session.commit()
    denied = client.get("/api/system/settings")
    assert denied.status_code == 401
    dispose_engine(settings)


def test_password_hash_roundtrip_and_plaintext_guard() -> None:
    stored = hash_password("correct horse battery staple")
    assert is_hashed_password(stored)
    assert verify_password("correct horse battery staple", stored)
    assert not verify_password("wrong", stored)
    assert not is_hashed_password("plaintext-password")
    assert not verify_password("plaintext-password", "plaintext-password")


# ------------------------------------------------------------------ #
# B9-3: audit persistence
# ------------------------------------------------------------------ #
def test_audit_events_persist_across_service_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    settings = make_settings(database_url=f"sqlite:///{db_path.as_posix()}")
    upgrade_database(settings)

    first = AuditService(settings)
    for index in range(5):
        first.record(actor="analyst", role="analyst", action="investigation.create", target=f"inv-{index}")

    # A fresh service (simulating a restart) must see the persisted events.
    second = AuditService(settings)
    items, total = second.query(limit=10, offset=0)
    assert total == 5
    assert [item["target"] for item in items] == [f"inv-{index}" for index in reversed(range(5))]
    assert second.persisted is True
    dispose_engine(settings)


def test_audit_query_pagination_and_filters(tmp_path: Path) -> None:
    db_path = tmp_path / "audit2.db"
    settings = make_settings(database_url=f"sqlite:///{db_path.as_posix()}")
    upgrade_database(settings)
    service = AuditService(settings)
    for index in range(7):
        service.record(actor="analyst", role="analyst", action="investigation.create", target=f"inv-{index}")
    for index in range(3):
        service.record(actor="operator", role="operator", action="defense.preview", target=f"dp-{index}")

    page1, total = service.query(limit=4, offset=0)
    page2, _ = service.query(limit=4, offset=4)
    assert total == 10
    assert len(page1) == 4 and len(page2) == 4

    only_create, create_total = service.query(action="investigation.create")
    assert create_total == 7 and all(item["action"] == "investigation.create" for item in only_create)
    only_operator, operator_total = service.query(actor="operator")
    assert operator_total == 3 and all(item["actor"] == "operator" for item in only_operator)
    dispose_engine(settings)


def test_audit_api_reports_persistence_and_supports_pagination(tmp_path: Path) -> None:
    db_path = tmp_path / "audit3.db"
    settings = make_settings(
        auth_enabled=True,
        app_secret_key=STRONG_KEY,
        database_url=f"sqlite:///{db_path.as_posix()}",
    )
    upgrade_database(settings)
    client, _app = _client("http://127.0.0.1:1", **settings.model_dump(include={
        "auth_enabled", "app_secret_key", "database_url",
    }))
    login = client.post("/api/auth/login", json={"username": "operator", "password": "operator-demo"})
    assert login.status_code == 200
    response = client.get("/api/audit/events", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["persisted"] is True
    assert body["limit"] == 5 and body["offset"] == 0 and "total" in body
    dispose_engine(settings)


def test_audit_api_memory_mode_flags_persisted_false() -> None:
    client, _app = _client("http://127.0.0.1:1")
    _login_operator(client)
    body = client.get("/api/audit/events").json()
    assert body["persisted"] is False


def _login_operator(client: TestClient) -> None:
    login = client.post("/api/auth/login", json={"username": "operator", "password": "operator-demo"})
    assert login.status_code == 200


# ------------------------------------------------------------------ #
# B9-5: connection and rendering input safety
# ------------------------------------------------------------------ #
def test_upstream_connection_ignores_ambient_proxy(stub_base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A dead ambient proxy must not capture upstream traffic (token exfiltration)."""
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    client = AgentGuardClient(make_settings(agentguard_base_url=stub_base_url))
    try:
        payload = client.health()
        assert payload["status"] == "ok"
    finally:
        client.close()


def test_report_pdf_escapes_markup_in_upstream_fields() -> None:
    hostile = {
        "run_id": "run-<script>alert(1)</script>",
        "request_id": "inv-x",
        "status": "completed",
        "findings": [
            {
                "finding_id": "f-1",
                "severity": "high & 'critical'",
                "risk_type": "<b>tool_abuse</b>",
                "summary": "injected <b onmouseover=alert(1)>markup</b> & trailing ampersand",
                "evidence_ids": ["ev-1", "ev-2"],
            }
        ],
        "evidence": [],
        "defense_candidates": [],
        "limitations": ["<a href='http://evil.example'>link</a>"],
    }
    pdf = render_report_pdf(hostile, {})
    assert pdf[:5] == b"%PDF-"
    import io

    from pypdf import PdfReader

    text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    # Literal characters survive; markup was never interpreted as structure.
    assert "<b onmouseover=alert(1)>markup</b>" in text
    assert "high & 'critical'" in text


def test_security_headers_on_all_responses(stub_base_url: str) -> None:
    client, _app = _client(stub_base_url)
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_csrf_cookie_expires_with_session() -> None:
    client, _app = _client(
        "http://127.0.0.1:1", auth_enabled=True, app_secret_key=STRONG_KEY, session_max_age_seconds=3600
    )
    _login_operator(client)
    for cookie_header in client.headers.get_list("set-cookie"):
        if cookie_header.startswith("qwb_csrf=") or cookie_header.startswith("qwb_session="):
            assert "Max-Age=3600" in cookie_header


def test_expired_session_is_rejected() -> None:
    from app.core.security import issue_session

    settings = make_settings(app_secret_key=STRONG_KEY, session_max_age_seconds=1)
    token = issue_session(settings, "viewer")
    assert verify_session(settings, token) == "viewer"
    expired_settings = make_settings(app_secret_key=STRONG_KEY, session_max_age_seconds=-10)
    expired_token = issue_session(expired_settings, "viewer")
    assert verify_session(settings, expired_token) is None


# ------------------------------------------------------------------ #
# B10: contract alignment and reconciliation
# ------------------------------------------------------------------ #
def test_hidden_truth_metadata_rejected_at_bff() -> None:
    with pytest.raises(ValueError, match="hidden evaluator fields"):
        CreateInvestigationRequest(
            contract_id="ct-1",
            model_id="m",
            runtime_id="rt",
            metadata={"notes": {"ground_truth": "should-not-be-here"}},
        )


def test_capture_targets_require_unique_nonblank_agent_ids() -> None:
    with pytest.raises(ValueError):
        CreateInvestigationRequest(
            contract_id="ct-1",
            model_id="m",
            runtime_id="rt",
            capture_targets=[{"target_id": "t", "agent_ids": []}],
        )
    with pytest.raises(ValueError):
        CreateInvestigationRequest(
            contract_id="ct-1",
            model_id="m",
            runtime_id="rt",
            capture_targets=[{"target_id": "t", "agent_ids": ["a", "a"]}],
        )


class _UnusedDemo:
    """LIVE-only service paths never touch the demo service."""


def test_wait_for_completion_timeout_budget_enforced() -> None:
    class _HealthyClient:
        def health(self) -> dict:
            return {"status": "ok"}

        def create_investigation(self, payload, *, request_id=None) -> dict:  # pragma: no cover
            raise AssertionError("budget check must fire before any submission")

    settings = make_settings(agentguard_api_timeout=15.0)
    request = CreateInvestigationRequest(
        contract_id="ct-1",
        model_id="m",
        runtime_id="rt",
        wait_for_completion=True,
        timeout_seconds=60.0,
    )

    with pytest.raises(InvestigationServiceError) as excinfo:
        create_investigation(
            _HealthyClient(),
            _UnusedDemo(),
            mode_override=None,
            request=request,
            settings=settings,
        )
    assert excinfo.value.code == "TIMEOUT_BUDGET_INVALID"


class _TimeoutPostClient:
    """Duck-typed connector stand-in: POST is network-ambiguous, GET reconciles.

    POST count is tracked so the test can assert there was never a resubmit.
    """

    def __init__(self, get_result: dict | None, get_error: Exception | None = None) -> None:
        self._get_result = get_result
        self._get_error = get_error
        self.post_count = 0

    def health(self) -> dict:
        return {"status": "ok"}

    def create_investigation(self, payload, *, request_id=None) -> dict:
        self.post_count += 1
        raise AgentGuardUnavailable(0, "API_UNREACHABLE", "AgentGuard API request timed out: ReadTimeout")

    def get_investigation(self, request_id: str) -> dict:
        if self._get_error is not None:
            raise self._get_error
        return dict(self._get_result or {})


def test_submission_reconciliation_found() -> None:
    """POST is network-ambiguous, but GET finds the investigation upstream:
    return the real record; never resubmit."""
    client = _TimeoutPostClient(get_result={"request_id": "inv-x", "status": "running"})
    request = CreateInvestigationRequest(contract_id="ct-1", model_id="m", runtime_id="rt")
    payload, meta = create_investigation(
        client, _UnusedDemo(), mode_override=None, request=request, settings=make_settings()
    )
    assert payload["request_id"] == "inv-x"
    assert payload["recovered_after_timeout"] is True
    assert meta["recovered_after_timeout"] is True
    assert client.post_count == 1


def test_submission_reconciliation_absent_is_retryable() -> None:
    """Upstream conclusively reports 404 for the request_id: the submission
    never landed, so the caller may safely retry with a new request."""
    from app.integrations.agentguard_client import AgentGuardError

    client = _TimeoutPostClient(
        get_result=None,
        get_error=AgentGuardError(404, "NOT_FOUND", "unknown workflow"),
    )
    request = CreateInvestigationRequest(contract_id="ct-1", model_id="m", runtime_id="rt")
    with pytest.raises(InvestigationServiceError) as excinfo:
        create_investigation(
            client, _UnusedDemo(), mode_override=None, request=request, settings=make_settings()
        )
    assert excinfo.value.code == "SUBMISSION_NOT_RECORDED"
    assert client.post_count == 1


def test_submission_reconciliation_unknown_stays_ambiguous() -> None:
    """Reconciliation itself fails: the outcome must stay ambiguous instead of
    guessing, and nothing may be resubmitted."""
    from app.integrations.agentguard_client import AgentGuardError

    client = _TimeoutPostClient(
        get_result=None,
        get_error=AgentGuardError(0, "API_UNREACHABLE", "AgentGuard API request failed"),
    )
    request = CreateInvestigationRequest(contract_id="ct-1", model_id="m", runtime_id="rt")
    with pytest.raises(InvestigationServiceError) as excinfo:
        create_investigation(
            client, _UnusedDemo(), mode_override=None, request=request, settings=make_settings()
        )
    assert excinfo.value.code == "SUBMISSION_AMBIGUOUS"
    assert client.post_count == 1


# ------------------------------------------------------------------ #
# B10: strict data-mode separation
# ------------------------------------------------------------------ #
def test_forced_live_mode_downgrades_to_unavailable_when_upstream_down() -> None:
    from app.core.data_mode import effective_data_mode

    assert effective_data_mode("live", agentguard_available=False) == "unavailable"
    assert effective_data_mode("live", agentguard_available=True) == "live"
    assert effective_data_mode("unavailable", agentguard_available=True) == "unavailable"
    assert effective_data_mode("synthetic", agentguard_available=True) == "synthetic"
    assert effective_data_mode(None, agentguard_available=False) == "unavailable"


def test_forced_live_never_claims_live_without_upstream(stub_base_url: str) -> None:
    client, _app = _client("http://127.0.0.1:1", app_data_mode="live")
    body = client.get("/api/system/status").json()
    assert body["data_mode"] == "unavailable"
    assert body["agentguard"]["reachable"] is False


def test_unreachable_upstream_never_serves_recorded_data_as_live(tmp_path: Path) -> None:
    client, _app = _client("http://127.0.0.1:1", app_data_mode="live")
    response = client.get("/api/investigations")
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "API_UNAVAILABLE"


def test_explicit_unavailable_override_is_honoured(stub_base_url: str) -> None:
    client, _app = _client(stub_base_url, app_data_mode="unavailable")
    body = client.get("/api/system/status").json()
    assert body["data_mode"] == "unavailable"
