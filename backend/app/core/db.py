"""Database engine management for BFF-owned tables.

The engine is created lazily from DATABASE_URL and cached per settings object.
Audit persistence (B9) and database-backed users both go through here. Schema
ownership stays with Alembic; `upgrade_database` runs pending migrations at
startup when DATABASE_URL is configured so deployments (including containers)
start with a known schema instead of silently writing to nothing.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

logger = logging.getLogger(__name__)

_ENGINES: dict[str, Engine] = {}
_SESSION_FACTORIES: dict[str, sessionmaker] = {}
_LOCK = threading.Lock()
# Alembic environment lives at backend/migrations (two levels above app/core).
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def get_engine(settings: Settings) -> Engine | None:
    """Return the shared engine for DATABASE_URL, or None when unset (dev)."""
    if not settings.database_url:
        return None
    with _LOCK:
        engine = _ENGINES.get(settings.database_url)
        if engine is None:
            engine = create_engine(
                settings.database_url,
                # SQLite needs check_same_thread=False: FastAPI serves requests
                # from a thread pool while the engine is process-global.
                connect_args={"check_same_thread": False}
                if settings.database_url.startswith("sqlite")
                else {},
            )
            if settings.database_url.startswith("sqlite"):
                @event.listens_for(engine, "connect")
                def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()
            _ENGINES[settings.database_url] = engine
    return engine


def get_session_factory(settings: Settings) -> sessionmaker | None:
    engine = get_engine(settings)
    if engine is None:
        return None
    with _LOCK:
        factory = _SESSION_FACTORIES.get(settings.database_url)
        if factory is None:
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            _SESSION_FACTORIES[settings.database_url] = factory
    return factory


def open_session(settings: Settings) -> Session | None:
    factory = get_session_factory(settings)
    if factory is None:
        return None
    return factory()


def dispose_engine(settings: Settings) -> None:
    """Drop cached engine/factory (used by tests and on shutdown)."""
    with _LOCK:
        engine = _ENGINES.pop(settings.database_url, None)
        _SESSION_FACTORIES.pop(settings.database_url, None)
    if engine is not None:
        engine.dispose()


def upgrade_database(settings: Settings) -> bool:
    """Run Alembic migrations to head. Returns False when no DATABASE_URL.

    Fail fast on migration errors: a mis-deployed schema must stop the service
    instead of degrading audit persistence to a memory buffer.
    """
    if not settings.database_url:
        return False
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")
    logger.info("database schema upgraded to head (%s)", settings.database_url.split("://")[0])
    return True
