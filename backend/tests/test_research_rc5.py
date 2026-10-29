"""Project ownership, durable idempotency and truthful RC5 research status."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.integrations.agentguard_client import AgentGuardClient
from app.models.app import Project, ProjectMember, ProjectStudySubmission


def _csrf(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("qwb_csrf", "")}


def _project_id(client) -> int:
    response = client.get("/api/projects")
    assert response.status_code == 200, response.text
    return next(item["project_id"] for item in response.json()["items"] if item["name"] == "p-live")


def _registration() -> dict:
    return {
        "title": "Paired protocol for RC5 integration",
        "research_question": "Does this preregistered method change the declared outcome?",
        "primary_hypothesis": "The treatment arm will differ from baseline on the registered outcome.",
        "primary_outcome": "srr_itt",
        "planned_pairs": 20,
        "planned_case_families": 10,
        "matching_variables": ["case_family"],
        "inclusion_criteria": ["Records satisfy the preregistered schema."],
        "stopping_rule": "Stop after all planned pairs have a final state.",
        "missing_data_rule": "Report missing pairs and do not impute outcomes.",
        "track": "mechanism_testbed",
        "arms": [
            {"arm_id": "baseline", "role": "baseline", "method_id": "control", "method_version": "1"},
            {"arm_id": "treatment", "role": "treatment", "method_id": "candidate", "method_version": "1"},
        ],
    }


def test_study_registration_is_project_scoped_and_idempotent(live_project_env) -> None:
    client, settings, login = live_project_env
    login()
    project_id = _project_id(client)
    payload = _registration()
    headers = {**_csrf(client), "Idempotency-Key": "rc5-study-test-001"}

    capability = client.get("/api/research/capabilities")
    assert capability.status_code == 200, capability.text
    assert capability.json()["meta"]["data_mode"] == "synthetic"
    assert capability.json()["report"]["backend_status"] == "blocked"

    created = client.post(f"/api/projects/{project_id}/studies", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    item = created.json()["submission"]
    assert item["status"] == "LINKED"
    assert item["study_id"] == "study-stub-0001"
    assert item["source"]["origin_mode"] == "synthetic"

    replay = client.post(f"/api/projects/{project_id}/studies", json=payload, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["submission"]["study_id"] == item["study_id"]

    changed = {**payload, "primary_hypothesis": "A different hypothesis under the same key."}
    conflict = client.post(f"/api/projects/{project_id}/studies", json=changed, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"] == "IDEMPOTENCY_CONFLICT"

    listed = client.get(f"/api/projects/{project_id}/studies?track=mechanism_testbed")
    assert listed.status_code == 200, listed.text
    assert listed.json()["meta"]["data_mode"] == "recorded"
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["study_id"] == item["study_id"]

    detail = client.get(f"/api/projects/{project_id}/studies/{item['study_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["meta"]["data_mode"] == "synthetic"
    assert detail.json()["study"]["study_id"] == item["study_id"]
    integrity = client.get(f"/api/projects/{project_id}/studies/{item['study_id']}/integrity")
    assert integrity.status_code == 200, integrity.text
    analyses = client.get(f"/api/projects/{project_id}/studies/{item['study_id']}/analyses")
    assert analyses.status_code == 200, analyses.text
    assert analyses.json()["items"] == []

    with Session(get_engine(settings)) as session:
        rows = session.query(ProjectStudySubmission).all()
        assert len(rows) == 1
        assert rows[0].status == "LINKED"
        assert rows[0].request_payload
        assert len(rows[0].idempotency_key_hash) == 64
        other = Project(name="p-study-isolation", description=None, status="active", created_by="alice")
        session.add(other)
        session.flush()
        session.add(ProjectMember(
            project_id=other.id, username="alice", role="admin", added_by="alice",
        ))
        other_project_id = other.id
        session.commit()

    cross_project = client.get(
        f"/api/projects/{other_project_id}/studies/{item['study_id']}"
    )
    assert cross_project.status_code == 404
    assert cross_project.json()["detail"]["error"] == "STUDY_NOT_FOUND"
    for suffix in ("/runs", "/runs/known-workflow"):
        denied = client.get(
            f"/api/projects/{other_project_id}/studies/{item['study_id']}{suffix}"
        )
        assert denied.status_code == 404
    denied_submit = client.post(
        f"/api/projects/{other_project_id}/studies/{item['study_id']}/runs",
        json={"arm_id": "baseline"}, headers={**_csrf(client), "Idempotency-Key": "cross-project"},
    )
    assert denied_submit.status_code == 404


def test_ambiguous_study_post_requires_explicit_same_key_replay(
    live_project_env, stub_base_url_study_ambiguous: str,
) -> None:
    client, settings, login = live_project_env
    login()
    project_id = _project_id(client)
    client.app.state.agentguard_client.close()
    client.app.state.agentguard_client = AgentGuardClient(
        type(settings)(
            agentguard_base_url=stub_base_url_study_ambiguous,
            database_url=settings.database_url,
            auth_enabled=settings.auth_enabled,
            app_secret_key=settings.app_secret_key,
        )
    )
    payload = _registration()
    headers = {**_csrf(client), "Idempotency-Key": "rc5-study-ambiguous-001"}

    uncertain = client.post(f"/api/projects/{project_id}/studies", json=payload, headers=headers)
    assert uncertain.status_code == 202, uncertain.text
    assert uncertain.json()["submission"]["status"] == "SUBMISSION_AMBIGUOUS"
    records = client.get(f"/api/projects/{project_id}/studies")
    assert records.json()["items"][0]["status"] == "SUBMISSION_AMBIGUOUS"

    replay = client.post(f"/api/projects/{project_id}/studies", json=payload, headers=headers)
    assert replay.status_code == 201, replay.text
    assert replay.json()["submission"]["study_id"] == "study-stub-0001"
    with Session(get_engine(settings)) as session:
        rows = session.query(ProjectStudySubmission).all()
        assert len(rows) == 1
        assert rows[0].status == "LINKED"
        assert rows[0].study_id == "study-stub-0001"
