"""Alembic migration test (B8): upgrade head creates all BFF-owned tables."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.db import dispose_engine, get_engine
from app.models.app import ProjectInvestigationLoop

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def test_initial_migration_creates_all_app_tables(tmp_path) -> None:
    db_path = tmp_path / "b8-migrate.db"
    database_url = f"sqlite:///{db_path.as_posix()}"

    cfg = _alembic_config(database_url)
    command.upgrade(cfg, "head")

    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    expected = {
        "users",
        "projects",
        "project_members",
        "project_investigations",
        "project_investigation_loops",
        "investigation_bookmarks",
        "report_exports",
        "demo_scenarios",
        "ui_preferences",
        "app_audit_events",
    }
    assert expected <= tables


def test_migration_downgrade_removes_app_tables(tmp_path) -> None:
    db_path = tmp_path / "b8-downgrade.db"
    database_url = f"sqlite:///{db_path.as_posix()}"

    cfg = _alembic_config(database_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "app_audit_events" not in tables
    assert "users" not in tables


def test_loop_ownership_migration_matches_orm_and_enforces_constraints(tmp_path) -> None:
    db_path = tmp_path / "j2-empty.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    command.upgrade(_alembic_config(database_url), "head")

    # Use the application's engine so SQLite foreign-key enforcement matches
    # runtime behavior, not just the presence of FK metadata.
    settings = Settings(database_url=database_url)
    engine = get_engine(settings)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "project_investigation_loops" in tables

        loop_constraints = {
            constraint["name"]: tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("project_investigation_loops")
        }
        orm_loop_constraints = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in ProjectInvestigationLoop.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert loop_constraints == orm_loop_constraints == {
            "uq_project_loop": ("project_id", "loop_id"),
            "uq_loop_id_unique": ("loop_id",),
        }
        db_indexes = {
            index["name"]: tuple(index["column_names"])
            for index in inspector.get_indexes("project_investigation_loops")
        }
        orm_indexes = {
            index.name: tuple(column.name for column in index.columns)
            for index in ProjectInvestigationLoop.__table__.indexes
        }
        assert db_indexes == orm_indexes == {
            "ix_project_investigation_loops_project_id": ("project_id",),
            "ix_project_investigation_loops_base_request_id": ("base_request_id",),
            "ix_project_investigation_loops_loop_id": ("loop_id",),
        }
        assert inspector.get_foreign_keys("project_investigation_loops") == [
            {
                "name": None,
                "constrained_columns": ["project_id"],
                "referred_schema": None,
                "referred_table": "projects",
                "referred_columns": ["id"],
                "options": {},
            }
        ]
        assert inspector.get_columns("project_investigations")[2]["type"].length == 256
        investigation_columns = {
            column["name"]: column for column in inspector.get_columns("project_investigations")
        }
        assert investigation_columns["verification_source"]["default"] == "'unknown'"
        loop_columns = {
            column["name"]: column
            for column in inspector.get_columns("project_investigation_loops")
        }
        assert loop_columns["base_request_id"]["type"].length == 256
        assert loop_columns["loop_id"]["type"].length == 256

        with engine.begin() as connection:
            project_id = connection.execute(
                text("INSERT INTO projects (name, description, status, created_by) "
                     "VALUES ('j2-project', NULL, 'active', 'alice') RETURNING id")
            ).scalar_one()
            connection.execute(
                text("INSERT INTO project_investigation_loops "
                     "(project_id, base_request_id, loop_id, created_by, verified_source) "
                     "VALUES (:project_id, :base_request_id, :loop_id, 'alice', 'agentguard')"),
                {"project_id": project_id, "base_request_id": "r" * 100, "loop_id": "l" * 100},
            )
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text("INSERT INTO project_investigation_loops "
                     "(project_id, base_request_id, loop_id, created_by, verified_source) "
                     "VALUES (:project_id, 'inv-other', :loop_id, 'bob', 'agentguard')"),
                {"project_id": project_id, "loop_id": "l" * 100},
            )
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text("INSERT INTO project_investigation_loops "
                     "(project_id, base_request_id, loop_id, created_by, verified_source) "
                     "VALUES (999999, 'inv-invalid-project', 'loop-no-project', 'alice', 'agentguard')")
            )
    finally:
        dispose_engine(settings)


def test_upgrade_from_0004_preserves_existing_project_investigation_data(tmp_path) -> None:
    db_path = tmp_path / "j2-from-0004.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    cfg = _alembic_config(database_url)
    command.upgrade(cfg, "0004")

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            project_id = connection.execute(
                text("INSERT INTO projects (name, description, status, created_by) "
                     "VALUES ('legacy-project', 'keep me', 'active', 'alice') RETURNING id")
            ).scalar_one()
            connection.execute(
                text("INSERT INTO project_investigations "
                     "(project_id, agentguard_request_id, created_by, display_name, notes, verification, "
                     "last_known_run_id) VALUES (:project_id, 'legacy-request', 'alice', 'Legacy', 'preserve', "
                     "'verified', 'legacy-run')"),
                {"project_id": project_id},
            )
    finally:
        engine.dispose()

    command.upgrade(cfg, "head")
    verify_engine = create_engine(database_url)
    try:
        with verify_engine.connect() as connection:
            project = connection.execute(
                text("SELECT name, description FROM projects WHERE id=:id"), {"id": project_id}
            ).one()
            investigation = connection.execute(
                text("SELECT agentguard_request_id, display_name, notes, verification, verification_source, "
                     "last_known_run_id "
                     "FROM project_investigations WHERE project_id=:id"), {"id": project_id}
            ).one()
        assert tuple(project) == ("legacy-project", "keep me")
        assert tuple(investigation) == (
            "legacy-request", "Legacy", "preserve", "verified", "unknown", "legacy-run")
        assert "project_investigation_loops" in set(inspect(verify_engine).get_table_names())
    finally:
        verify_engine.dispose()
