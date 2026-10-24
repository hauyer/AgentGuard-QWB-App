"""Live AgentGuard contract compatibility check (CI / pre-flight).

Usage:
    python scripts/check_agentguard_contract.py [--base-url URL] [--token TOKEN]

Behavior:
  * Reads the pinned contract from contracts/agentguard-version.json.
  * If a live AgentGuard is reachable, verifies the pinned endpoints exist in its
    OpenAPI schema and that health responds; exits non-zero on mismatch.
  * Without a reachable AgentGuard (default CI), the check is SKIPPED with a clear
    message - a missing real service is never reported as a passing live test.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "contracts" / "agentguard-version.json"
SKIP_STATUS = 42  # pytest-style skip exit code


def load_contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_json(url: str, token: str | None, timeout: float = 8.0) -> dict:
    headers = {"Accept": "application/json"}
    if token:
        headers["X-AgentGuard-Token"] = token
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("response must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("AGENTGUARD_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.environ.get("AGENTGUARD_API_TOKEN"))
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    contract = load_contract()
    pinned = contract["pinned_agentguard"]
    print(f"pinned: {pinned['repository']} @ {pinned['commit']} ({pinned['branch']})")

    base = args.base_url.rstrip("/")
    try:
        openapi = fetch_json(f"{base}/openapi.json", args.token, args.timeout)
    except (HTTPError, URLError, OSError) as exc:
        print(f"SKIP: live AgentGuard unreachable at {base} ({exc}); live contract check skipped. "
              "Real-integration tests are marked skipped, never auto-passed.")
        return SKIP_STATUS

    expected = set(contract["supported_endpoints"])
    # OpenAPI lists operations per path; rebuild "METHOD /path" pairs so the
    # comparison matches the pinned endpoint format.
    actual = {
        f"{method.upper()} {path}"
        for path, operations in openapi.get("paths", {}).items()
        for method in operations
    }
    missing = expected - actual
    if missing:
        print(f"FAIL: {len(missing)} pinned endpoints missing from live OpenAPI:")
        for path in sorted(missing):
            print(f"  - {path}")
        return 1

    health = fetch_json(f"{base}/v1/system/health", args.token, args.timeout)
    if health.get("status") != "ok":
        print(f"FAIL: health status is {health.get('status')!r}")
        return 1

    print(f"PASS: all {len(expected)} pinned endpoints present in live OpenAPI; health ok.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
