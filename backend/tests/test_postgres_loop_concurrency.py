"""Production-dialect check for the per-investigation active submission lock."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

POSTGRES_URL = os.environ.get("QWB_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="QWB_TEST_POSTGRES_URL is not configured")


def test_postgres_allows_only_one_unresolved_submission_per_base() -> None:
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL)
    suffix = uuid4().hex
    project_name = f"pg-lock-{suffix}"
    request_id = f"pg-request-{suffix}"
    try:
        with engine.begin() as connection:
            project_id = connection.execute(
                text("INSERT INTO projects (name, status, created_by) VALUES (:name, 'active', 'test') RETURNING id"),
                {"name": project_name},
            ).scalar_one()
            values = {
                "project_id": project_id,
                "base_request_id": request_id,
                "submission_id": str(uuid4()),
                "idempotency_key": uuid4().hex,
                "request_fingerprint": "a" * 64,
                "request_payload": "{}",
                "status": "SUBMISSION_AMBIGUOUS",
                "created_by": "test",
            }
            connection.execute(
                text(
                    "INSERT INTO investigation_loop_submissions "
                    "(project_id, base_request_id, submission_id, idempotency_key, request_fingerprint, "
                    "request_payload, status, created_by) VALUES "
                    "(:project_id, :base_request_id, :submission_id, :idempotency_key, :request_fingerprint, "
                    ":request_payload, :status, :created_by)"
                ),
                values,
            )

        second = {**values, "submission_id": str(uuid4()), "idempotency_key": uuid4().hex}
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO investigation_loop_submissions "
                    "(project_id, base_request_id, submission_id, idempotency_key, request_fingerprint, "
                    "request_payload, status, created_by) VALUES "
                    "(:project_id, :base_request_id, :submission_id, :idempotency_key, :request_fingerprint, "
                    ":request_payload, :status, :created_by)"
                ),
                second,
            )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE investigation_loop_submissions SET status='FAILED' "
                    "WHERE base_request_id=:request_id"
                ),
                {"request_id": request_id},
            )
            connection.execute(
                text(
                    "INSERT INTO investigation_loop_submissions "
                    "(project_id, base_request_id, submission_id, idempotency_key, request_fingerprint, "
                    "request_payload, status, created_by) VALUES "
                    "(:project_id, :base_request_id, :submission_id, :idempotency_key, :request_fingerprint, "
                    ":request_payload, :status, :created_by)"
                ),
                second,
            )
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM investigation_loop_submissions WHERE base_request_id=:request_id"),
                {"request_id": request_id},
            )
            connection.execute(text("DELETE FROM projects WHERE name=:name"), {"name": project_name})
        engine.dispose()
