"""Application-layer business tables (B8).

Only BFF-owned data lives here: users, projects, memberships, bookmarks,
report exports, demo scenario profiles, UI preferences and app audit events.
AgentGuard-stored investigations/evidence/experiences are never duplicated
wholesale; read-only upstream responses are only cached with an explicit
TTL, source and invalidation policy (see docs/architecture/overview.md).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(16), index=True)
    display_name: Mapped[str | None] = mapped_column(String(128))
    # B9: PBKDF2 hash (app.core.passwords) for real accounts; demo accounts are
    # source-level constants that never enter this table.
    password_hash: Mapped[str | None] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    # B12: active | archived; the creator (username) owns the project.
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectMember(Base):
    """Project-scoped membership (B12).

    Membership is keyed by username (not FK): database users and gated demo
    users share the same identity namespace, and removing a row immediately
    revokes project access without touching global roles.
    """

    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "username", name="uq_project_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    # Project-level role within the global viewer/analyst/operator/admin scale:
    # caps what this user may do inside this project only.
    role: Mapped[str] = mapped_column(String(16))
    added_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectInvestigation(Base):
    """Reference from a project to an AgentGuard-stored investigation (B12).

    Only the reference and business metadata live here; run state stays
    authoritative in AgentGuard and is never duplicated. `last_known_run_id`
    (B19) is the authorization bridge for run_id-addressed resources (reports):
    it is refreshed on authorized investigation reads.
    """

    __tablename__ = "project_investigations"
    __table_args__ = (UniqueConstraint("project_id", "agentguard_request_id", name="uq_project_investigation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    agentguard_request_id: Mapped[str] = mapped_column(String(256), index=True)
    created_by: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text)
    # whether the BFF verified the request_id exists upstream at link time
    verification: Mapped[str] = mapped_column(String(16), default="unverified")
    # Existing rows cannot be assumed to have been checked against Live data.
    verification_source: Mapped[str] = mapped_column(String(16), default="unknown")
    last_known_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectInvestigationLoop(Base):
    """Project-scoped mapping of an E6 investigation loop (B28).

    Only the mapping lives here; loop state stays authoritative in AgentGuard.
    loop_id is the authorization bridge for loop-addressed resources.
    """

    __tablename__ = "project_investigation_loops"
    __table_args__ = (
        UniqueConstraint("project_id", "loop_id", name="uq_project_loop"),
        UniqueConstraint("loop_id", name="uq_loop_id_unique"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    base_request_id: Mapped[str] = mapped_column(String(256), index=True)
    loop_id: Mapped[str] = mapped_column(String(256), index=True)
    created_by: Mapped[str | None] = mapped_column(String(64))
    verified_source: Mapped[str] = mapped_column(String(16), default="unverified")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvestigationLoopSubmission(Base):
    """Durable BFF submission state for safe, idempotent loop creation."""

    __tablename__ = "investigation_loop_submissions"
    __table_args__ = (
        UniqueConstraint("project_id", "submission_id", name="uq_project_loop_submission"),
        UniqueConstraint("idempotency_key", name="uq_loop_submission_idempotency_key"),
        Index(
            "uq_active_loop_submission_per_base",
            "project_id",
            "base_request_id",
            unique=True,
            sqlite_where=text("status IN ('PREPARED', 'SUBMITTING', 'SUBMISSION_AMBIGUOUS', 'LINK_PENDING')"),
            postgresql_where=text("status IN ('PREPARED', 'SUBMITTING', 'SUBMISSION_AMBIGUOUS', 'LINK_PENDING')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    base_request_id: Mapped[str] = mapped_column(String(256), index=True)
    submission_id: Mapped[str] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(String(64), index=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    request_payload: Mapped[str] = mapped_column(Text)
    baseline_loop_ids: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    loop_id: Mapped[str | None] = mapped_column(String(256), index=True)
    response_payload: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_status_code: Mapped[int | None] = mapped_column()
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvestigationBookmark(Base):
    __tablename__ = "investigation_bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "request_id", name="uq_user_bookmark"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportExport(Base):
    __tablename__ = "report_exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(8))  # json | pdf
    exported_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DemoSenario(Base):
    """Profile for an offline demo scenario (recorded/synthetic replay)."""

    __tablename__ = "demo_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    data_mode: Mapped[str] = mapped_column(String(16))  # recorded | synthetic
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UiPreference(Base):
    __tablename__ = "ui_preferences"
    __table_args__ = (UniqueConstraint("user_id", "pref_key", name="uq_user_pref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    pref_key: Mapped[str] = mapped_column(String(64))
    pref_value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppAuditEvent(Base):
    __tablename__ = "app_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str | None] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str | None] = mapped_column(String(128))
    # B12: optional project scope so audit queries can filter per project.
    project_id: Mapped[int | None] = mapped_column(index=True)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
