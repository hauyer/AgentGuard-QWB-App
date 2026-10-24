"""Run the AgentGuard stub service for offline LIVE-path verification.

The stub implements the documented public API shapes (contracts/agentguard-version.json)
and is used to verify the BFF's live path without a real AgentGuard. It never claims
to be a real WARDEN/model runtime.

Usage:
    python scripts/run_stub_agentguard.py [--port 8002] [--kernel available]
"""

from __future__ import annotations

import argparse

import uvicorn

from tests.stub_agentguard import create_stub_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--kernel", default="not_configured", choices=["not_configured", "available"])
    args = parser.parse_args()

    app = create_stub_app(kernel_status=args.kernel, warden_available=args.kernel == "available")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
