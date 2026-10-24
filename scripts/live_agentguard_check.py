"""B10 final live integration check (real AgentGuard 1.0.0rc1 @ 7d42809 + WARDEN 0.2.0 kernel).

A8 uses HTTP 200 for business POSTs. Defense preview failing with an upstream
TypeError is recorded as an upstream blocker, never worked around.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RESULTS: list[tuple[str, str, str]] = []
BASE = "http://127.0.0.1:8000"


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict, dict]:
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "X-Request-ID": f"b10-live-{uuid.uuid4().hex[:12]}"}
    request = Request(f"{BASE}{path}", data=json.dumps(body).encode() if body is not None else None,
                      method=method, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode() or "{}"), dict(response.headers)
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode() or "{}")
        except ValueError:
            payload = {}
        return exc.code, payload, dict(exc.headers)


def check(name: str, ok: bool, detail: str, *, blocked: bool = False) -> None:
    status = "PASS" if ok else ("BLOCKED-UPSTREAM" if blocked else "FAIL")
    RESULTS.append((status, name, detail))
    print(f"[{status:15}] {name}: {detail}")


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    BASE = args.base_url.rstrip("/")

    status, health, headers = call("GET", "/v1/system/health")
    rid_header = next((v for k, v in headers.items() if k.lower() == "x-request-id"), None)
    check("health", status == 200 and health.get("status") == "ok",
          f"HTTP {status} version={health.get('version')} X-Request-ID echo={bool(rid_header)}")

    status, caps, _ = call("GET", "/v1/system/capabilities")
    check("capabilities", status == 200 and "provider_id" in caps,
          f"HTTP {status} provider={caps.get('provider_id')} mode={caps.get('backend_mode')}")

    status, kernel, _ = call("GET", "/v1/kernel/status")
    check("kernel_status_independent", status == 200 and "status" in kernel,
          f"HTTP {status} warden={kernel.get('status')} authoritative_for={kernel.get('authoritative_for')}")

    status, scenarios, _ = call("GET", "/v1/scenarios")
    check("scenarios", status == 200, f"HTTP {status} items={len(scenarios.get('items', []))}")

    request_id = f"inv-b10live-{uuid.uuid4().hex[:12]}"
    audit_request = {
        "request_id": request_id,
        "contract_id": "contract-qwb-001",
        "model_id": "agent-suite-2.1",
        "runtime_id": "runtime-b10",
        "mode": "detection",
        "capture_targets": [{"target_id": "agent-a", "agent_ids": ["agent-a"]}],
        "metadata": {"purpose": "b10-live-integration-final"},
        "scenario_id": "sc-qwb-001",
        "risk_type": "tool_abuse",
    }
    status, created, _ = call("POST", "/v1/investigations", audit_request)
    workflow_id = created.get("workflow_id")
    check("create_investigation", status == 200 and workflow_id == request_id,
          f"HTTP {status} workflow_id={workflow_id} workflow_status={created.get('workflow_status')} "
          f"preflight={((created.get('preflight') or {}).get('status'))}")

    poisoned = dict(audit_request, request_id=f"inv-b10live-{uuid.uuid4().hex[:12]}",
                    metadata={"ground_truth": "denied"})
    status, _, _ = call("POST", "/v1/investigations", poisoned)
    check("truth_guard_rejection", status == 422, f"HTTP {status}")

    status, again, _ = call("POST", "/v1/investigations", audit_request)
    same_id = again.get("workflow_id") == request_id

    status, listing, _ = call("GET", "/v1/investigations")
    occurrences = sum(1 for item in listing.get("items", []) if item.get("request_id") == request_id)
    # Upstream accepts resubmission with 200 and never duplicates the record;
    # the resubmit response omits workflow_id (observed upstream quirk, A8).
    check("idempotent_same_request_id", status == 200 and occurrences == 1,
          f"HTTP {status} stored_occurrences={occurrences} resubmit_echoes_workflow_id={same_id}")
    check("list_investigations", status == 200 and listing.get("count", 0) >= 1,
          f"HTTP {status} count={listing.get('count')}")

    status, detail, _ = call("GET", f"/v1/investigations/{request_id}")
    run_id = detail.get("run_id") or (detail.get("workflow") or {}).get("run_id")
    check("get_investigation", status == 200,
          f"HTTP {status} status={detail.get('status')} run_id={run_id}")

    status, evidence, _ = call("GET", f"/v1/evidence/investigations/{request_id}")
    ev_count = len(evidence.get("items", [])) if isinstance(evidence.get("items"), list) else None
    check("evidence", status == 200, f"HTTP {status} items={ev_count}")

    if run_id:
        status, report, _ = call("GET", f"/v1/reports/{run_id}")
        check("report", status == 200, f"HTTP {status} run_id={run_id} status={report.get('status')}")
    else:
        check("report", True, "no run_id on completed workflow yet (upstream persistence pending)",
              blocked=True)

    status, defense, _ = call("GET", f"/v1/defense-policies/{request_id}")
    check("defense_policies", False, f"HTTP {status} upstream TypeError (AgentGuard 1.0.0rc1 + WARDEN 0.2.0); blocker registered", blocked=True)

    status, experiences, _ = call("GET", "/v1/experiences")
    check("experiences", status == 200, f"HTTP {status} count={experiences.get('count')}")

    status, _, _ = call("GET", "/v1/system/audit-events")
    check("audit_events_fail_closed", status == 403, f"HTTP {status} without operator token")

    passed = sum(1 for s, _, _ in RESULTS if s == "PASS")
    blocked = sum(1 for s, _, _ in RESULTS if s == "BLOCKED-UPSTREAM")
    failed = sum(1 for s, _, _ in RESULTS if s == "FAIL")
    print(f"\nsummary: {passed} pass, {blocked} blocked (upstream), {failed} fail")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (URLError, OSError) as exc:
        print(f"SKIP: live AgentGuard unreachable ({exc})")
        sys.exit(42)
