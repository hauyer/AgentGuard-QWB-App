"""J6 live, project-scoped investigation report and export tests."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.core.passwords import hash_password
from app.integrations.agentguard_client import AgentGuardClient
from app.models.app import ProjectInvestigation, ProjectInvestigationLoop, User
from tests.conftest import _serve, make_settings
from tests.stub_agentguard import create_stub_app


def _install_report_stub(client, settings, **options) -> None:
    upstream = _serve(create_stub_app(
        kernel_status="available",
        warden_available=True,
        investigation_loop_report_available=True,
        **options,
    ))
    client.app.state.agentguard_client = AgentGuardClient(make_settings(
        agentguard_base_url=upstream,
        **settings.model_dump(include={"auth_enabled", "app_secret_key", "database_url"}),
    ))


def _register_loop(settings, loop_id: str) -> int:
    with Session(get_engine(settings)) as session:
        investigation = session.scalar(
            select(ProjectInvestigation).where(
                ProjectInvestigation.agentguard_request_id == "inv-stub-0001"
            )
        )
        assert investigation is not None
        investigation.verification = "verified"
        investigation.verification_source = "live"
        project_id = investigation.project_id
        session.add(ProjectInvestigationLoop(
            project_id=project_id,
            base_request_id="inv-stub-0001",
            loop_id=loop_id,
            created_by="alice",
            verified_source="agentguard",
        ))
        session.commit()
        return project_id


@pytest.fixture()
def report_env(live_project_env):
    client, settings, login = live_project_env
    _register_loop(settings, "loop-stub-001")
    _install_report_stub(client, settings)
    return client, settings, login


def test_complete_report_json_pdf_chinese_and_facts_match(report_env) -> None:
    from pypdf import PdfReader

    client, _settings, login = report_env
    login()
    path = "/api/reports/investigations/inv-stub-0001/loops/loop-stub-001"
    preview = client.get(path)
    assert preview.status_code == 200
    report = preview.json()["report"]
    assert report["project"]["name"] == "p-live"
    assert report["investigation"]["request_id"] == "inv-stub-0001"
    assert report["loop"]["loop_id"] == "loop-stub-001"
    assert report["risk_analysis"]["data"]["findings"][0]["evidence_level"] == "observational"
    assert report["decisions"]["items"][0]["decision_id"] == "decision-report-001"
    assert report["evidence_changes"]["items"][0]["evidence_refs_after"] == ["ev-report-001"]
    assert report["budget"]["budget"]["max_actions"] == 3
    assert report["defense"]["data"]["execution_performed"] is False
    assert report["strategy_evaluation"] is None

    json_export = client.get(f"{path}/export.json")
    assert json_export.status_code == 200
    assert json_export.headers["content-disposition"] == (
        "attachment; filename=\"investigation-report-inv-stub-0001-loop-stub-001.json\""
    )
    exported_report = json_export.json()
    assert exported_report["loop"]["loop_id"] == report["loop"]["loop_id"]
    assert exported_report["decisions"]["items"][0]["decision_id"] == report["decisions"]["items"][0]["decision_id"]

    pdf_export = client.get(f"{path}/export.pdf")
    assert pdf_export.status_code == 200
    assert pdf_export.headers["content-type"].startswith("application/pdf")
    reader = PdfReader(io.BytesIO(pdf_export.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "inv-stub-0001" in text
    assert "loop-stub-001" in text
    assert "decision-report-001" in text
    assert "AgentGuard-QWB-App 调查报告" in text
    assert "/STSong-Light" in pdf_export.content.decode("latin-1")


def test_empty_evidence_is_reported_as_empty_not_filled(report_env) -> None:
    client, settings, login = report_env
    _install_report_stub(client, settings, report_empty_evidence=True)
    login()
    response = client.get("/api/reports/investigations/inv-stub-0001/loops/loop-stub-001")
    assert response.status_code == 200
    assert response.json()["report"]["evidence_changes"]["items"] == []


@pytest.mark.parametrize(
    ("loop_id", "phase"),
    [("loop-stub-blocked", "BLOCKED"), ("loop-stub-failed", "FAILED")],
)
def test_blocked_or_failed_loop_state_is_preserved(live_project_env, loop_id: str, phase: str) -> None:
    client, settings, login = live_project_env
    _register_loop(settings, loop_id)
    _install_report_stub(client, settings)
    login()
    response = client.get(f"/api/reports/investigations/inv-stub-0001/loops/{loop_id}")
    assert response.status_code == 200
    assert response.json()["report"]["loop"]["phase"] == phase
    if phase == "FAILED":
        assert response.json()["report"]["loop"]["stop_reason"] == "UPSTREAM_UNAVAILABLE"


def test_long_chinese_text_flows_across_pdf_pages(report_env) -> None:
    from pypdf import PdfReader

    client, settings, login = report_env
    _install_report_stub(client, settings, report_long_text=True)
    login()
    response = client.get(
        "/api/reports/investigations/inv-stub-0001/loops/loop-stub-001/export.pdf"
    )
    assert response.status_code == 200
    reader = PdfReader(io.BytesIO(response.content))
    assert len(reader.pages) > 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "风险分析中的中文长文本" in text


def test_cross_project_user_cannot_preview_or_export_report(report_env) -> None:
    client, settings, _login = report_env
    with Session(get_engine(settings)) as session:
        session.add(User(
            username="report-outsider",
            role="viewer",
            display_name="Outsider",
            password_hash=hash_password("report-outsider-password"),
            is_active=True,
        ))
        session.commit()
    login_response = client.post(
        "/api/auth/login", json={"username": "report-outsider", "password": "report-outsider-password"}
    )
    assert login_response.status_code == 200
    path = "/api/reports/investigations/inv-stub-0001/loops/loop-stub-001"
    for suffix in ("", "/export.json", "/export.pdf"):
        response = client.get(f"{path}{suffix}")
        assert response.status_code == 404


def test_unauthenticated_user_cannot_read_report(report_env) -> None:
    client, _settings, _login = report_env
    response = client.get("/api/reports/investigations/inv-stub-0001/loops/loop-stub-001")
    assert response.status_code == 401


def test_export_audit_records_json_and_pdf_actions(report_env) -> None:
    client, _settings, login = report_env
    login()
    path = "/api/reports/investigations/inv-stub-0001/loops/loop-stub-001"
    assert client.get(f"{path}/export.json").status_code == 200
    assert client.get(f"{path}/export.pdf").status_code == 200
    audit = client.app.state.audit_service
    events, _count = audit.query(limit=100, offset=0)
    actions = {event["action"] for event in events}
    assert "report.export.json" in actions
    assert "report.export.pdf" in actions


def test_export_filename_is_sanitized_for_untrusted_loop_id(live_project_env) -> None:
    client, settings, login = live_project_env
    loop_id = "loop evil;bad"
    _register_loop(settings, loop_id)
    _install_report_stub(client, settings)
    login()
    from urllib.parse import quote

    response = client.get(
        f"/api/reports/investigations/inv-stub-0001/loops/{quote(loop_id, safe='')}/export.json"
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith(
        'investigation-report-inv-stub-0001-loop_evil_bad.json"'
    )


def test_json_and_pdf_output_limits_are_enforced(monkeypatch) -> None:
    from app.api.routes.experiments import _report_json_bytes
    from app.services import reports_service
    from app.services.reports_service import ReportsServiceError

    with pytest.raises(ReportsServiceError) as json_error:
        _report_json_bytes({"text": "x" * reports_service.MAX_REPORT_JSON_BYTES})
    assert json_error.value.status_code == 413

    monkeypatch.setattr(reports_service, "MAX_PDF_BYTES", 1)
    with pytest.raises(ReportsServiceError) as pdf_error:
        reports_service.render_investigation_loop_report_pdf({"loop": {"loop_id": "loop-1"}})
    assert pdf_error.value.status_code == 413
