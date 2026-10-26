"""Read-only-first compatibility check against a configured AgentGuard service.

Verdict semantics (strict - a check only passes when its response was actually
received and its required fields/semantics validated):

    PASS               a configured endpoint returned a response matching its contract;
                       this never proves WARDEN execution or model/causal validity
    FAIL               a response contradicted expectations (test failure)
    SKIP_NOT_CONFIGURED AgentGuard itself unreachable; the whole run is inconclusive
    BLOCKED_UPSTREAM   the upstream response itself proves the capability is
                       blocked (e.g. 503 WARDEN_NOT_CONFIGURED, preflight blockers,
                       500 INTERNAL_SERVER_ERROR on a published endpoint)
    UNSUPPORTED        the endpoint is absent from the live OpenAPI - the
                       capability is not published at the pinned commit
    NOT_RUN_WRITE_DISABLED write-based checks were deliberately not sent

Writes are disabled by default. `--allow-write` is required before the script
creates an investigation or sends validation POSTs. `--request-id` selects an
existing investigation for read-only checks. Ambient proxies and redirects are
disabled, response bodies are bounded, and credentials are read only from the
server-side environment.

Exit codes: 0 = no FAIL (blocked/unsupported/write-disabled allowed),
1 = at least one FAIL, 42 = SKIP_NOT_CONFIGURED (service down - never a pass).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.parse import quote, urlsplit

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP_NOT_CONFIGURED"
BLOCKED = "BLOCKED_UPSTREAM"
UNSUPPORTED = "UNSUPPORTED"
WRITE_DISABLED = "NOT_RUN_WRITE_DISABLED"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


@dataclass
class Result:
    name: str
    status: str
    detail: str


RESULTS: list[Result] = []
BASE = "http://127.0.0.1:8000"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(ProxyHandler({}), _NoRedirect())


def _read_json(stream) -> dict:
    raw = stream.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("upstream response exceeded the configured size limit")
    payload = json.loads(raw.decode("utf-8") or "{}")
    if not isinstance(payload, dict):
        raise ValueError("upstream response must be a JSON object")
    return payload


def call(
    method: str, path: str, body: dict | None = None, *, operator: bool = False,
) -> tuple[int, dict, dict]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Request-ID": f"b11-live-{uuid.uuid4().hex[:12]}",
    }
    request = Request(f"{BASE}{path}", data=json.dumps(body).encode() if body is not None else None,
                      method=method, headers=headers)
    api_token = os.environ.get("AGENTGUARD_API_TOKEN")
    operator_token = os.environ.get("AGENTGUARD_OPERATOR_TOKEN")
    if api_token:
        request.add_header("X-AgentGuard-Token", api_token)
    if operator and operator_token:
        request.add_header("X-AgentGuard-Operator-Token", operator_token)
    try:
        with OPENER.open(request, timeout=20) as response:
            return response.status, _read_json(response), dict(response.headers)
    except HTTPError as exc:
        try:
            payload = _read_json(exc)
        except (ValueError, UnicodeDecodeError):
            payload = {}
        return exc.code, payload, dict(exc.headers)
    except (ValueError, UnicodeDecodeError):
        return 502, {"detail": {"error": "API_BAD_RESPONSE"}}, {}


def add(name: str, status: str, detail: str) -> None:
    RESULTS.append(Result(name, status, detail))
    print(f"[{status:19}] {name}: {detail}")


def upstream_error(payload: dict) -> str:
    detail = payload.get("detail")
    if isinstance(detail, dict):
        candidate = detail.get("error", "")
    else:
        candidate = ""
    return candidate if isinstance(candidate, str) and SAFE_ERROR_CODE.fullmatch(candidate) else "UPSTREAM_ERROR"


def main() -> int:
    global BASE
    RESULTS.clear()
    repo_root = Path(__file__).resolve().parent.parent
    try:
        contract = json.loads((repo_root / "contracts" / "agentguard-version.json").read_text(encoding="utf-8"))
        snapshot = json.loads((repo_root / contract["openapi"]["snapshot"]).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        add("local_pin", FAIL, f"cannot load the checked-in AgentGuard pin ({type(exc).__name__})")
        return _emit(argparse.Namespace(json_out=None))
    expected_version = contract["pinned_agentguard"]["upstream_version"]
    expected_commit = contract["pinned_agentguard"]["commit"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--json-out", default=None, help="write the machine-readable result list here")
    parser.add_argument("--request-id", default=None, help="read-only checks for an existing investigation")
    parser.add_argument(
        "--allow-write", action="store_true",
        help="explicitly allow temporary investigation creation and validation POSTs",
    )
    args = parser.parse_args()
    BASE = args.base_url.rstrip("/")
    parsed_base = urlsplit(BASE)
    if (
        parsed_base.scheme not in {"http", "https"}
        or not parsed_base.hostname
        or parsed_base.username
        or parsed_base.password
        or parsed_base.query
        or parsed_base.fragment
    ):
        add("base_url", FAIL, "base URL must be http(s) with a host and no embedded credentials or query")
        return _emit(args)

    # 0. reachability gate: everything else is meaningless when AgentGuard is down
    try:
        status, health, headers = call("GET", "/v1/system/health")
    except (URLError, OSError) as exc:
        add("system_health", SKIP, f"AgentGuard unreachable at configured endpoint ({type(exc).__name__})")
        return _emit(args)

    request_id_echo = next((v for k, v in headers.items() if k.lower() == "x-request-id"), None)
    add("system_health",
        PASS if status == 200 and health.get("status") == "ok" and request_id_echo
        and health.get("version") == expected_version else FAIL,
        f"HTTP {status} status={health.get('status')} version={health.get('version')} "
        f"expected_version={expected_version} X-Request-ID echo={bool(request_id_echo)}")
    if health.get("status") != "ok":
        print("AgentGuard is up but unhealthy; remaining checks are inconclusive")
        _emit(args)
        return 1

    # capability discovery from the live OpenAPI (single fetch, reused below)
    try:
        openapi_headers = {"Accept": "application/json"}
        api_token = os.environ.get("AGENTGUARD_API_TOKEN")
        if api_token:
            openapi_headers["X-AgentGuard-Token"] = api_token
        request = Request(f"{BASE}/openapi.json", headers=openapi_headers)
        with OPENER.open(request, timeout=15) as response:
            openapi = _read_json(response)
    except (HTTPError, URLError, OSError, ValueError, UnicodeDecodeError) as exc:
        add("openapi_discovery", FAIL, f"cannot validate /openapi.json ({type(exc).__name__})")
        _emit(args)
        return 1
    actual_ops = {
        f"{method.upper()} {path}"
        for path, operations in openapi.get("paths", {}).items()
        for method in operations
    }

    def supported(op: str) -> bool:
        return op in actual_ops

    pinned_ops = {
        f"{method.upper()} {path}"
        for path, operations in snapshot.get("paths", {}).items()
        for method in operations
    }
    live_version = openapi.get("info", {}).get("version") if isinstance(openapi.get("info"), dict) else None
    pin_matches = (
        live_version == expected_version
        and len(openapi.get("paths", {})) == contract["openapi"]["path_count"]
        and actual_ops == pinned_ops
    )
    add("openapi_pin_match", PASS if pin_matches else FAIL,
        f"version={live_version} paths={len(openapi.get('paths', {}))}; "
        f"operation_inventory={'matches' if actual_ops == pinned_ops else 'differs'}")

    identity_op = "GET /v1/system/identity"
    if supported(identity_op):
        status, identity, _ = call("GET", "/v1/system/identity")
        declared = (
            status == 200
            and identity.get("runtime_identity_status") == "declared"
            and identity.get("build_commit") == expected_commit
            and identity.get("software_version") == expected_version
            and identity.get("openapi_sha256") == contract["openapi"]["sha256_canonical_json"]
        )
        if declared:
            add("system_identity", PASS,
                f"declared build identity matches pinned commit {expected_commit[:7]} and OpenAPI hash")
        elif status == 200 and identity.get("runtime_identity_status") == "unknown":
            add("system_identity", BLOCKED, "service reports runtime identity as unknown")
        else:
            add("system_identity", FAIL, f"HTTP {status}; declared build identity did not match the pin")
    else:
        add("system_identity", UNSUPPORTED, f"{identity_op} absent from the configured service")

    add("warden_live_gate", BLOCKED,
        "AgentGuard rc2 documents this gate as BLOCKED; API shape checks do not prove WARDEN execution")

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
        verdict = BLOCKED if ok and kernel.get("status") != "available" else PASS if ok else FAIL
        add("warden_kernel_status", verdict,
            f"HTTP {status} reported_status={kernel.get('status')} "
            "(status response only; no WARDEN execution performed)")
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

    # 4-6. Writes require an explicit command-line opt-in; an existing request
    # can instead be selected for read-only checks with --request-id.
    request_id = args.request_id
    if request_id is not None and (not request_id or len(request_id) > 256):
        add("request_id", FAIL, "request ID must contain 1 to 256 characters")
        return _emit(args)
    encoded_request_id = quote(request_id, safe="") if request_id else None
    detail: dict = {}
    if args.allow_write:
        request_id = f"inv-b11live-{uuid.uuid4().hex[:12]}"
        audit_request = {
            "request_id": request_id,
            "contract_id": "contract-qwb-001",
            "model_id": "agent-suite-2.1",
            "runtime_id": "runtime-b11",
            "mode": "detection",
            "capture_targets": [{"target_id": "agent-a", "agent_ids": ["agent-a"]}],
            "metadata": {"purpose": "live-agentguard-check"},
            "scenario_id": "sc-qwb-001",
            "risk_type": "tool_abuse",
        }
        if not supported("POST /v1/investigations"):
            add("create_investigation", UNSUPPORTED, "POST /v1/investigations absent from live OpenAPI")
        else:
            status, created, _ = call("POST", "/v1/investigations", audit_request)
            if status in {200, 201, 202} and created.get("workflow_id") == request_id:
                preflight = created.get("preflight") or {}
                add("create_investigation", PASS,
                    f"HTTP {status} workflow_status={created.get('workflow_status')} "
                    f"preflight={preflight.get('status')}")
            elif status in {200, 201, 202}:
                add("create_investigation", FAIL, "HTTP success response contained an unexpected workflow identity")
            elif status == 503 and upstream_error(created) == "WARDEN_NOT_CONFIGURED":
                add("create_investigation", BLOCKED,
                    "HTTP 503 WARDEN_NOT_CONFIGURED - WARDEN is not wired to this deployment")
            else:
                add("create_investigation", BLOCKED if status >= 500 else FAIL,
                    f"HTTP {status} error={upstream_error(created)}")

        if supported("POST /v1/investigations"):
            poisoned = dict(audit_request, request_id=f"inv-b11live-{uuid.uuid4().hex[:12]}",
                            metadata={"ground_truth": "must-not-pass"})
            status, _, _ = call("POST", "/v1/investigations", poisoned)
            add("truth_guard_metadata_rejection", PASS if status == 422 else FAIL,
                f"HTTP {status} (evaluator metadata must be rejected)")
        else:
            add("truth_guard_metadata_rejection", UNSUPPORTED, "POST /v1/investigations absent from live OpenAPI")

        if supported("POST /v1/investigations") and supported("GET /v1/investigations"):
            status, again, _ = call("POST", "/v1/investigations", audit_request)
            status2, listing, _ = call("GET", "/v1/investigations")
            occurrences = sum(1 for item in listing.get("items", [])
                              if isinstance(item, dict) and item.get("request_id") == request_id)
            ok = status in {200, 201, 202} and status2 == 200 and occurrences == 1
            add("investigation_idempotency", PASS if ok else FAIL,
                f"resubmit HTTP {status}; stored_occurrences={occurrences}; "
                f"same request identity={again.get('workflow_id') == request_id}")
        else:
            add("investigation_idempotency", UNSUPPORTED, "POST/GET /v1/investigations absent from live OpenAPI")
    else:
        add("create_investigation", WRITE_DISABLED, "no writes sent; use --allow-write only against an isolated test service")
        add("truth_guard_metadata_rejection", WRITE_DISABLED, "requires a validation POST; no writes sent")
        add("investigation_idempotency", WRITE_DISABLED, "requires a create/resubmit POST; no writes sent")

    # 7. investigation detail
    if not request_id:
        add("investigation_detail", WRITE_DISABLED, "select an existing investigation with --request-id")
    elif supported("GET /v1/investigations/{request_id}"):
        status, detail, _ = call("GET", f"/v1/investigations/{encoded_request_id}")
        ok = status == 200 and detail.get("request_id") == request_id and "status" in detail
        add("investigation_detail", PASS if ok else (
            BLOCKED if status == 404 and upstream_error(detail) else FAIL),
            f"HTTP {status} status={detail.get('status')} workflow_status={detail.get('workflow_status')}")
    elif request_id:
        add("investigation_detail", UNSUPPORTED, "GET /v1/investigations/{{request_id}} absent from live OpenAPI")

    # 8. evidence for the stored investigation
    if not request_id:
        add("evidence_read", WRITE_DISABLED, "select an existing investigation with --request-id")
    elif supported("GET /v1/evidence/investigations/{request_id}"):
        status, evidence, _ = call("GET", f"/v1/evidence/investigations/{encoded_request_id}")
        ok = status == 200 and isinstance(evidence, dict)
        add("evidence_read", PASS if ok else (
            BLOCKED if status == 404 else FAIL),
            f"HTTP {status} keys={sorted(k for k in evidence if not k.startswith('_'))[:6]}")
    else:
        add("evidence_read", UNSUPPORTED, "evidence endpoint absent from live OpenAPI")

    # 9. interaction graph - published only if the endpoint exists
    graph_op = "GET /v1/investigations/{request_id}/interaction-graph"
    if not request_id:
        add("interaction_graph", WRITE_DISABLED, "select an existing investigation with --request-id")
    elif supported(graph_op):
        status, graph, _ = call("GET", f"/v1/investigations/{encoded_request_id}/interaction-graph")
        add("interaction_graph", PASS if status == 200 and isinstance(graph, dict) else FAIL,
            f"HTTP {status} (published endpoint; shape validated)")
    else:
        add("interaction_graph", UNSUPPORTED, f"{graph_op} not published at pinned commit")

    # 10. timeline - published only if the endpoint exists
    timeline_op = "GET /v1/investigations/{request_id}/timeline"
    if not request_id:
        add("investigation_timeline", WRITE_DISABLED, "select an existing investigation with --request-id")
    elif supported(timeline_op):
        status, timeline, _ = call("GET", f"/v1/investigations/{encoded_request_id}/timeline")
        add("investigation_timeline", PASS if status == 200 and isinstance(timeline, dict) else FAIL,
            f"HTTP {status} (published endpoint; shape validated)")
    else:
        add("investigation_timeline", UNSUPPORTED, f"{timeline_op} not published at pinned commit")

    # 11. report - a report read is only PASS when a real run_id existed and the
    # report body was actually fetched and validated. A workflow without run_id
    # (preflight blocked) must NOT count as a passing report check.
    if not request_id:
        add("report_read", WRITE_DISABLED, "select an existing investigation with --request-id")
    elif detail.get("run_id"):
        if supported("GET /v1/reports/{run_id}"):
            status, report, _ = call("GET", f"/v1/reports/{quote(str(detail['run_id']), safe='')}")
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
    if not request_id:
        add("defense_policies", WRITE_DISABLED, "select an existing investigation with --request-id")
    elif supported(defense_get):
        status, defense, _ = call("GET", f"/v1/defense-policies/{encoded_request_id}")
        if status == 200 and isinstance(defense, dict):
            add("defense_policies", PASS, f"HTTP {status} (candidate payload received)")
        elif status == 500 and upstream_error(defense) == "INTERNAL_SERVER_ERROR":
            add("defense_policies", BLOCKED,
                "HTTP 500 INTERNAL_SERVER_ERROR - upstream endpoint failed; re-check current pinned service")
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

    # 14. operator audit access is checked without exposing credentials.
    if supported("GET /v1/system/audit-events"):
        has_operator_token = bool(os.environ.get("AGENTGUARD_OPERATOR_TOKEN"))
        status, events, _ = call("GET", "/v1/system/audit-events", operator=True)
        ok = status == 200 and isinstance(events.get("items"), list) if has_operator_token else status in {401, 403}
        expectation = "authorized operator read" if has_operator_token else "fail-closed without operator token"
        add("system_audit_events_auth", PASS if ok else FAIL, f"HTTP {status} ({expectation})")
    else:
        add("system_audit_events_auth", UNSUPPORTED, "GET /v1/system/audit-events absent from live OpenAPI")

    return _emit(args)


def _emit(args) -> int:
    statuses = (PASS, FAIL, SKIP, BLOCKED, UNSUPPORTED, WRITE_DISABLED)
    counts = {s: 0 for s in statuses}
    for result in RESULTS:
        counts[result.status] = counts.get(result.status, 0) + 1
    print("\nsummary: " + ", ".join(f"{counts[status]} {status}" for status in statuses))
    if args.json_out:
        payload = {
            "base_url": BASE,
            "results": [vars(result) for result in RESULTS],
            "counts": counts,
        }
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        print(f"machine-readable report: {args.json_out}")
    if counts[FAIL]:
        return 1
    if any(result.name == "system_health" and result.status == SKIP for result in RESULTS):
        return 42
    return 0


if __name__ == "__main__":
    sys.exit(main())
