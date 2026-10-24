"""Alembic migration test (B8): upgrade head creates all BFF-owned tables."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

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
