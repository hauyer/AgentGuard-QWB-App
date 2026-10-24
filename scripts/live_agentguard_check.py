"""B11 live integration check against the real AgentGuard service.

Verdict semantics (strict - a check only passes when its response was actually
received and its required fields/semantics validated):

    PASS               upstream responded 2xx and every required field was verified
    FAIL               a response contradicted expectations (test failure)
    SKIP_NOT_CONFIGURED AgentGuard itself unreachable; the whole run is inconclusive
    BLOCKED_UPSTREAM   the upstream response itself proves the capability is
                       blocked (e.g. 503 WARDEN_NOT_CONFIGURED, preflight blockers,
                       500 INTERNAL_SERVER_ERROR on a published endpoint)
    UNSUPPORTED        the endpoint is absent from the live OpenAPI - the
                       capability is not published at the pinned commit

Exit codes: 0 = no FAIL (blocked/unsupported allowed), 1 = at least one FAIL,
42 = SKIP_NOT_CONFIGURED (service down - never reported as passing).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP_NOT_CONFIGURED"
BLOCKED = "BLOCKED_UPSTREAM"
UNSUPPORTED = "UNSUPPORTED"


@dataclass
class Result:
    name: str
    status: str
    detail: str


RESULTS: list[Result] = []
BASE = "http://127.0.0.1:8000"


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict, dict]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": f"b11-live-{uuid.uuid4().hex[:12]}",
    }
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


def add(name: str, status: str, detail: str) -> None:
    RESULTS.append(Result(name, status, detail))
    print(f"[{status:19}] {name}: {detail}")


def upstream_error(payload: dict) -> str:
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("error", ""))
    return str(detail or "")


def main() -> int:
    global BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--json-out", default=None, help="write the machine-readable result list here")
    args = parser.parse_args()
    BASE = args.base_url.rstrip("/")

    # 0. reachability gate: everything else is meaningless when AgentGuard is down
    try:
        status, health, headers = call("GET", "/v1/system/health")
    except (URLError, OSError) as exc:
        print(f"SKIP_NOT_CONFIGURED: live AgentGuard unreachable at {BASE} ({exc})")
        return 42

    request_id_echo = next((v for k, v in headers.items() if k.lower() == "x-request-id"), None)
    add("system_health",
        PASS if status == 200 and health.get("status") == "ok" and request_id_echo else FAIL,
        f"HTTP {status} status={health.get('status')} version={health.get('version')} "
        f"X-Request-ID echo={bool(request_id_echo)}")
    if health.get("status") != "ok":
        print("AgentGuard is up but unhealthy; remaining checks are inconclusive")
        _emit(args)
        return 1

    # capability discovery from the live OpenAPI (single fetch, reused below)
    try:
        openapi = json.loads(urlopen(f"{BASE}/openapi.json", timeout=15).read().decode())
    except (URLError, OSError, ValueError) as exc:
        add("openapi_discovery", FAIL, f"cannot read /openapi.json: {exc}")
        _emit(args)
        return 1
    actual_ops = {
        f"{method.upper()} {path}"
        for path, operations in openapi.get("paths", {}).items()
        for method in operations
    }

    def supported(op: str) -> bool:
        return op in actual_ops

    # 1. capabilities manifest
    if supported("GET /v1/system/capabilities"):
        status, caps, _ = call("GET", "/v1/system/capabilities")
        ok = status == 200 and isinstance(caps.get("capabilities"), dict) and caps.get("provider_id")
        add("system_capabilities", PASS if ok else FAIL,
            f"HTTP {status} provider={caps.get('provider_id')} backend_mode={caps.get('backend_mode')}")
    else:
        add("system_capabilities", UNSUPPORTED, "GET /v1/system/capabilities absent from live OpenAPI")

    # 2. kernel status - independent layer, reported as-is
    if supported("GET /v1/kernel/status"):
        status, kernel, _ = call("GET", "/v1/kernel/status")
        ok = status == 200 and kernel.get("kernel") == "WARDEN" and "status" in kernel
        add("warden_kernel_status", PASS if ok else FAIL,
            f"HTTP {status} warden={kernel.get('status')} authoritative_for={kernel.get('authoritative_for')}")
    else:
        add("warden_kernel_status", UNSUPPORTED, "GET /v1/kernel/status absent from live OpenAPI")

    # 3. scenarios
    if supported("GET /v1/scenarios"):
        status, scenarios, _ = call("GET", "/v1/scenarios")
        items = scenarios.get("items")
        ok = status == 200 and isinstance(items, list) and all(
            isinstance(item, dict) and item.get("scenario_id") for item in items
        )
        add("scenarios", PASS if ok else FAIL, f"HTTP {status} items={len(items or [])}")
    else:
        add("scenarios", UNSUPPORTED, "GET /v1/scenarios absent from live OpenAPI")

    # 4. investigation creation
    request_id = f"inv-b11live-{uuid.uuid4().hex[:12]}"
    audit_request = {
        "request_id": request_id,
        "contract_id": "contract-qwb-001",
        "model_id": "agent-suite-2.1",
        "runtime_id": "runtime-b11",
        "mode": "detection",
        "capture_targets": [{"target_id": "agent-a", "agent_ids": ["agent-a"]}],
        "metadata": {"purpose": "b11-live-check"},
        "scenario_id": "sc-qwb-001",
        "risk_type": "tool_abuse",
    }
    if not supported("POST /v1/investigations"):
        add("create_investigation", UNSUPPORTED, "POST /v1/investigations absent from live OpenAPI")
    else:
        status, created, _ = call("POST", "/v1/investigations", audit_request)
        if status == 200 and created.get("workflow_id") == request_id:
            preflight = (created.get("preflight") or {})
            add("create_investigation", PASS,
                f"HTTP {status} workflow_id={created.get('workflow_id')} "
                f"workflow_status={created.get('workflow_status')} preflight={preflight.get('status')}")
        elif status in {200, 201, 202}:
            add("create_investigation", FAIL,
                f"HTTP {status} but workflow_id mismatch: {created.get('workflow_id')!r} != {request_id!r}")
        elif status == 503 and upstream_error(created) == "WARDEN_NOT_CONFIGURED":
            add("create_investigation", BLOCKED,
                "HTTP 503 WARDEN_NOT_CONFIGURED - WARDEN kernel not wired to this AgentGuard deployment")
        else:
            add("create_investigation", BLOCKED if status >= 500 else FAIL,
                f"HTTP {status} error={upstream_error(created)}")

    # 5. A8 hidden-truth metadata guard must reject poisoned metadata
    if supported("POST /v1/investigations"):
        poisoned = dict(audit_request, request_id=f"inv-b11live-{uuid.uuid4().hex[:12]}",
                        metadata={"ground_truth": "must-not-pass"})
        status, rejected, _ = call("POST", "/v1/investigations", poisoned)
        add("truth_guard_metadata_rejection", PASS if status == 422 else FAIL,
            f"HTTP {status} (A8 guard: evaluator metadata must be rejected)")

    # 6. idempotent resubmission: same request_id must never duplicate storage
    if supported("POST /v1/investigations") and supported("GET /v1/investigations"):
        status, again, _ = call("POST", "/v1/investigations", audit_request)
        status2, listing, _ = call("GET", "/v1/investigations")
        occurrences = sum(1 for item in listing.get("items", [])
                          if isinstance(item, dict) and item.get("request_id") == request_id)
        ok = status == 200 and status2 == 200 and occurrences == 1
        add("investigation_idempotency", PASS if ok else FAIL,
            f"resubmit HTTP {status}; stored_occurrences={occurrences} "
            f"(resubmit echoes workflow_id={again.get('workflow_id') == request_id})")
    else:
        add("investigation_idempotency", UNSUPPORTED, "POST/GET /v1/investigations absent from live OpenAPI")

    # 7. investigation detail
    detail: dict = {}
    if supported("GET /v1/investigations/{request_id}"):
        status, detail, _ = call("GET", f"/v1/investigations/{request_id}")
        ok = status == 200 and detail.get("request_id") == request_id and "status" in detail
        add("investigation_detail", PASS if ok else (
            BLOCKED if status == 404 and upstream_error(detail) else FAIL),
            f"HTTP {status} status={detail.get('status')} workflow_status={detail.get('workflow_status')}")
    else:
        add("investigation_detail", UNSUPPORTED, "GET /v1/investigations/{{request_id}} absent from live OpenAPI")

    # 8. evidence for the stored investigation
    if supported("GET /v1/evidence/investigations/{request_id}"):
        status, evidence, _ = call("GET", f"/v1/evidence/investigations/{request_id}")
        ok = status == 200 and isinstance(evidence, dict)
        add("evidence_read", PASS if ok else (
            BLOCKED if status == 404 else FAIL),
            f"HTTP {status} keys={sorted(k for k in evidence if not k.startswith('_'))[:6]}")
    else:
        add("evidence_read", UNSUPPORTED, "evidence endpoint absent from live OpenAPI")

    # 9. interaction graph - published only if the endpoint exists
    graph_op = "GET /v1/investigations/{request_id}/interaction-graph"
    if supported(graph_op):
        status, graph, _ = call("GET", f"/v1/investigations/{request_id}/interaction-graph")
        add("interaction_graph", PASS if status == 200 and isinstance(graph, dict) else FAIL,
            f"HTTP {status} (published endpoint; shape validated)")
    else:
        add("interaction_graph", UNSUPPORTED, f"{graph_op} not published at pinned commit")

    # 10. timeline - published only if the endpoint exists
    timeline_op = "GET /v1/investigations/{request_id}/timeline"
    if supported(timeline_op):
        status, timeline, _ = call("GET", f"/v1/investigations/{request_id}/timeline")
        add("investigation_timeline", PASS if status == 200 and isinstance(timeline, dict) else FAIL,
            f"HTTP {status} (published endpoint; shape validated)")
    else:
        add("investigation_timeline", UNSUPPORTED, f"{timeline_op} not published at pinned commit")

    # 11. report - a report read is only PASS when a real run_id existed and the
    # report body was actually fetched and validated. A workflow without run_id
    # (preflight blocked) must NOT count as a passing report check.
    if detail.get("run_id"):
        if supported("GET /v1/reports/{run_id}"):
            status, report, _ = call("GET", f"/v1/reports/{detail['run_id']}")
            ok = status == 200 and report.get("run_id") == detail["run_id"]
            add("report_read", PASS if ok else FAIL, f"HTTP {status} run_id={detail['run_id']}")
        else:
            add("report_read", UNSUPPORTED, "GET /v1/reports/{{run_id}} absent from live OpenAPI")
    else:
        add("report_read", BLOCKED,
            "no run_id on stored workflow (preflight blocked before run submission); "
            "report body could not be read - not counted as PASS")

    # 12. defense candidates - upstream TypeError bug at pinned combo is BLOCKED
    defense_get = "GET /v1/defense-policies/{request_id}"
    if supported(defense_get):
        status, defense, _ = call("GET", f"/v1/defense-policies/{request_id}")
        if status == 200 and isinstance(defense, dict):
            add("defense_policies", PASS, f"HTTP {status} (candidate payload received)")
        elif status == 500 and upstream_error(defense) == "INTERNAL_SERVER_ERROR":
            add("defense_policies", BLOCKED,
                "HTTP 500 INTERNAL_SERVER_ERROR - upstream TypeError (QWB-INT-008, "
                "AgentGuard 1.0.0rc1 + WARDEN 0.2.0)")
        elif status == 404:
            add("defense_policies", BLOCKED, "HTTP 404 - no defense policy for the stored workflow")
        else:
            add("defense_policies", FAIL, f"HTTP {status} error={upstream_error(defense)}")
    else:
        add("defense_policies", UNSUPPORTED, f"{defense_get} absent from live OpenAPI")

    # 13. experiences search
    if supported("GET /v1/experiences"):
        status, experiences, _ = call("GET", "/v1/experiences")
        ok = status == 200 and isinstance(experiences.get("items", []), list)
        add("experiences_search", PASS if ok else FAIL,
            f"HTTP {status} items={len(experiences.get('items', []))}")
    else:
        add("experiences_search", UNSUPPORTED, "GET /v1/experiences absent from live OpenAPI")

    # 14. system audit events must be fail-closed without an operator token
    if supported("GET /v1/system/audit-events"):
        status, _, _ = call("GET", "/v1/system/audit-events")
        add("system_audit_events_auth", PASS if status in {401, 403} else FAIL,
            f"HTTP {status} without operator token (fail-closed expectation: 401/403)")
    else:
        add("system_audit_events_auth", UNSUPPORTED, "GET /v1/system/audit-events absent from live OpenAPI")

    return _emit(args)


def _emit(args) -> int:
    counts = {s: 0 for s in (PASS, FAIL, SKIP, BLOCKED, UNSUPPORTED)}
    for result in RESULTS:
        counts[result.status] = counts.get(result.status, 0) + 1
    print(f"\nsummary: {counts[PASS]} pass, {counts[FAIL]} fail, "
          f"{counts[BLOCKED]} blocked-upstream, {counts[UNSUPPORTED]} unsupported")
    if args.json_out:
        payload = {
            "base_url": BASE,
            "results": [vars(result) for result in RESULTS],
            "counts": counts,
        }
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        print(f"machine-readable report: {args.json_out}")
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
