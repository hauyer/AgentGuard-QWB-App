"""Isolated BFF + deterministic AgentGuard Stub for Playwright.

This process owns a temporary SQLite database, enables real cookie auth, and
starts the contract Stub on a separate local HTTP port. It is test-only and
never points at a developer's configured AgentGuard instance.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


class ThreadedServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:
        return


def main() -> None:
    bff_port = int(os.environ.get("E2E_BFF_PORT", "8101"))
    stub_port = int(os.environ.get("E2E_STUB_PORT", "8102"))
    configured_temp_dir = os.environ.get("E2E_DATABASE_DIR")
    temp_dir = Path(configured_temp_dir) if configured_temp_dir else Path(
        tempfile.mkdtemp(prefix="agentguard-qwb-e2e-")
    )
    temp_dir.mkdir(parents=True, exist_ok=True)
    database_path = temp_dir / "isolated-e2e.db"
    os.environ.update({
        "APP_ENV": "development",
        "APP_HOST": "127.0.0.1",
        "APP_PORT": str(bff_port),
        "APP_CORS_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
        "APP_DATA_MODE": "",
        "APP_SECRET_KEY": "j7-isolated-e2e-secret-key-0123456789abcdef",
        "AUTH_ENABLED": "true",
        "AUTH_DEMO_USERS_ENABLED": "false",
        "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
        "AGENTGUARD_BASE_URL": f"http://127.0.0.1:{stub_port}",
        "AGENTGUARD_API_TIMEOUT": "2",
        "SESSION_COOKIE_SECURE": "false",
    })

    from app.core.config import get_settings
    from app.core.db import dispose_engine, open_session, upgrade_database
    from app.core.passwords import hash_password
    from app.models.app import User

    settings = get_settings()
    upgrade_database(settings)
    session = open_session(settings)
    if session is None:
        raise RuntimeError("the isolated Playwright database did not open")
    with session:
        session.add_all([
            User(username="alice", role="admin", display_name="Alice Admin",
                 password_hash=hash_password("alice-e2e-password"), is_active=True),
            User(username="user-a", role="analyst", display_name="User A",
                 password_hash=hash_password("user-a-e2e-password"), is_active=True),
            User(username="user-b", role="analyst", display_name="User B",
                 password_hash=hash_password("user-b-e2e-password"), is_active=True),
        ])
        session.commit()
    dispose_engine(settings)

    from tests.stub_agentguard import create_stub_app

    stub = ThreadedServer(uvicorn.Config(
        create_stub_app(
            strategy_evaluations_available=True,
            investigation_loop_report_available=True,
            e2e_isolation_loops=True,
        ),
        host="127.0.0.1",
        port=stub_port,
        log_level="warning",
    ))
    stub_thread = threading.Thread(target=stub.run, daemon=True)
    stub_thread.start()
    deadline = time.monotonic() + 15
    while not stub.started:
        if time.monotonic() >= deadline:
            raise RuntimeError("the deterministic AgentGuard Stub did not start")
        time.sleep(0.05)

    from app.main import create_app

    bff = uvicorn.Server(uvicorn.Config(
        create_app(), host="127.0.0.1", port=bff_port, log_level="warning"
    ))
    try:
        bff.run()
    finally:
        bff.should_exit = True
        stub.should_exit = True
        stub_thread.join(timeout=5)
        dispose_engine(settings)
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
