"""Shared fixtures for backend tests.

The AgentGuard stub is served over real HTTP (uvicorn on an ephemeral port) so
the connector is exercised through the same network path as production. The stub
is a documented contract stand-in, never a claim of real WARDEN availability.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn

from app.core.config import Settings
from tests.stub_agentguard import create_stub_app


def make_settings(**overrides) -> Settings:
    base = {
        "agentguard_base_url": "http://127.0.0.1:8000",
        "agentguard_api_token": None,
        "agentguard_operator_api_token": None,
        "agentguard_api_timeout": 15.0,
        "app_cors_origins": "http://localhost:5173",
    }
    base.update(overrides)
    return Settings(**base)


class _StubServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:
        # No signal handlers inside a test thread.
        return


def _serve(app) -> str:
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = _StubServer(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("stub server did not start")
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    return f"http://127.0.0.1:{port}"


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def stub_base_url() -> Iterator[str]:
    yield _serve(create_stub_app())


@pytest.fixture(scope="session")
def stub_base_url_warden_available() -> Iterator[str]:
    yield _serve(create_stub_app(kernel_status="available", warden_available=True))


@pytest.fixture(scope="session")
def stub_base_url_capabilities_fail() -> Iterator[str]:
    yield _serve(create_stub_app(capabilities_status=500))


@pytest.fixture
def unreachable_base_url() -> str:
    return f"http://127.0.0.1:{_unused_port()}"
