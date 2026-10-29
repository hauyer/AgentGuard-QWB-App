"""Unified AgentGuard API client (BFF connector).

The exact committed implementation and snapshot are pinned in
contracts/agentguard-version.json (RC5 API version, 93 paths, 107 operations).
Study execution and arm batches use only frozen public WARDEN workflows. Result
views require verified artifacts; a healthy service does not prove measured effects.
Capability discovery lets older servers degrade explicitly. The original measured
analysis write gate remains independent of the verified read-only paired views.

Safety rules enforced here (mirror the upstream SDK contract):
  * upstream origin is fixed by server config; callers cannot choose arbitrary hosts
  * X-Request-ID is always sent; a caller-supplied value is preserved
  * timeout is bounded (0, 120] seconds
  * responses larger than 4 MiB are rejected
  * POST/PUT/PATCH/DELETE are never auto-retried (reconciliation for ambiguous
    POSTs is read-only and decided by the service layer, never a blind resubmit)
  * only idempotent GET requests may be retried, with a bounded backoff
  * redirects are never followed
  * request bodies and tokens are never written to logs
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
GET_RETRY_ATTEMPTS = 2
GET_RETRY_BACKOFF_SECONDS = (0.5, 1.0)
RETRYABLE_GET_STATUS = {502, 503, 504}

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SAFE_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_MESSAGES = {
    "WARDEN_NOT_CONFIGURED": "WARDEN is not configured on the AgentGuard service.",
    "LOOP_IDEMPOTENCY_CONFLICT": "This Loop idempotency key conflicts with an earlier request.",
    "EVALUATION_ARTIFACT_UNAVAILABLE": "The strategy evaluation artifact is unavailable.",
}


def _safe_request_id(value: str | None) -> str | None:
    return value if value and _SAFE_REQUEST_ID.fullmatch(value) else None


def _safe_error_code(value: Any) -> str:
    candidate = value if isinstance(value, str) else ""
    return candidate if _SAFE_ERROR_CODE.fullmatch(candidate) else "API_REQUEST_REJECTED"


def _safe_error_message(status_code: int, code: str) -> str:
    if code in _SAFE_MESSAGES:
        return _SAFE_MESSAGES[code]
    return {
        401: "AgentGuard rejected authentication.",
        403: "AgentGuard denied this operation.",
        404: "The requested AgentGuard resource was not found.",
        409: "The AgentGuard request conflicts with existing state.",
        410: "The requested AgentGuard resource is unavailable.",
        422: "AgentGuard rejected the request validation.",
        429: "AgentGuard is rate limiting requests.",
    }.get(status_code, "AgentGuard returned an upstream error.")


class AgentGuardError(RuntimeError):
    """A bounded AgentGuard API failure without response secrets or request bodies."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        super().__init__(message)


class AgentGuardUnavailable(AgentGuardError):
    """AgentGuard could not be reached at all (network / timeout / DNS)."""


class AgentGuardClient:
    """Stateless HTTP client for typed AgentGuard business API paths."""

    def __init__(self, settings: Settings | None = None, *, transport: httpx.BaseTransport | None = None) -> None:
        from app.core.config import get_settings

        self._settings = settings or get_settings()
        self._base_url = self._settings.agentguard_base_url
        self._timeout = self._settings.agentguard_api_timeout
        self._discovered: dict[str, bool] | None = None
        self._discovery_error: str | None = None
        # trust_env=False (B9): ignore ambient HTTP(S)_PROXY / system proxy
        # settings. The upstream origin is fixed server-side and normally
        # direct; routing it through an uncontrolled proxy would expose the
        # X-AgentGuard-Token header to that proxy and makes connectivity depend
        # on the operator's machine configuration.
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> AgentGuardClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # low-level request path
    # ------------------------------------------------------------------ #
    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        request_id: str | None = None,
        operator: bool = False,
        loop_idempotency_key: str | None = None,
        idempotency_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not path.startswith("/v1/") or "?" in path or "#" in path:
            raise ValueError("path must be a versioned AgentGuard /v1 path")
        method = method.upper()
        if timeout_seconds is not None and not 0 < timeout_seconds <= 120:
            raise ValueError("request timeout must be in (0, 120]")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("unsupported HTTP method")

        headers: dict[str, str] = {
            "Accept": "application/json",
            "X-Request-ID": request_id or str(uuid.uuid4()),
        }
        if _safe_request_id(headers["X-Request-ID"]) is None:
            raise ValueError("request_id contains unsupported characters or exceeds 128 characters")
        if self._settings.agentguard_api_token:
            headers["X-AgentGuard-Token"] = self._settings.agentguard_api_token
        if operator and self._settings.agentguard_operator_api_token:
            headers["X-AgentGuard-Operator-Token"] = self._settings.agentguard_operator_api_token
        if loop_idempotency_key:
            headers["X-Loop-Idempotency-Key"] = loop_idempotency_key
        if idempotency_key:
            if not _SAFE_IDEMPOTENCY_KEY.fullmatch(idempotency_key):
                raise ValueError("idempotency_key does not match the RC5 contract")
            headers["Idempotency-Key"] = idempotency_key

        params: dict[str, Any] = {key: value for key, value in (query or {}).items() if value is not None}
        json_body = None
        if body is not None:
            json_body = body
            headers["Content-Type"] = "application/json"

        attempt = 0
        retryable = method in _SAFE_METHODS
        while True:
            attempt += 1
            try:
                return self._perform(method, path, headers=headers, params=params, json_body=json_body,
                                     timeout_seconds=timeout_seconds)
            except (AgentGuardUnavailable, _TransientStatus) as exc:
                if not retryable or attempt > GET_RETRY_ATTEMPTS:
                    raise
                delay = GET_RETRY_BACKOFF_SECONDS[min(attempt - 1, len(GET_RETRY_BACKOFF_SECONDS) - 1)]
                logger.warning(
                    "AgentGuard GET failed (attempt %s/%s) with %s; retrying in %.1fs",
                    attempt, GET_RETRY_ATTEMPTS + 1, exc.code, delay,
                )
                time.sleep(delay)

    def _perform(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any],
        json_body: dict[str, Any] | None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        request_id = headers["X-Request-ID"]
        try:
            with self._http.stream(method, path, headers=headers, params=params, json=json_body,
                                   timeout=timeout_seconds or self._timeout) as response:
                response_request_id = _safe_request_id(response.headers.get("X-Request-ID")) or request_id
                if 300 <= response.status_code < 400:
                    raise AgentGuardError(
                        502, "API_REDIRECT_REJECTED", "AgentGuard returned an unexpected redirect", response_request_id
                    )

                content_length = response.headers.get("Content-Length")
                if content_length:
                    try:
                        if int(content_length) > MAX_RESPONSE_BYTES:
                            raise AgentGuardError(
                                502, "API_RESPONSE_TOO_LARGE", "AgentGuard API response exceeded the size limit",
                                response_request_id,
                            )
                    except ValueError:
                        # Ignore malformed Content-Length and enforce the streaming limit below.
                        pass

                raw = bytearray()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise AgentGuardError(
                            502, "API_RESPONSE_TOO_LARGE", "AgentGuard API response exceeded the size limit",
                            response_request_id,
                        )
                    raw.extend(chunk)

                payload: Any = {}
                if raw:
                    try:
                        payload = json.loads(raw)
                    except (ValueError, UnicodeDecodeError) as exc:
                        raise AgentGuardError(
                            502, "API_BAD_RESPONSE", "AgentGuard returned an invalid response",
                            response_request_id,
                        ) from exc
                if not isinstance(payload, dict):
                    raise AgentGuardError(
                        502, "API_BAD_RESPONSE", "AgentGuard returned an invalid response",
                        response_request_id,
                    )
                if (
                    method in _SAFE_METHODS
                    and 500 <= response.status_code < 600
                    and response.status_code in RETRYABLE_GET_STATUS
                ):
                    raise _TransientStatus(response.status_code, payload, response_request_id)
                if not 200 <= response.status_code < 300:
                    detail = payload.get("detail")
                    if not isinstance(detail, dict):
                        detail = {}
                    code = _safe_error_code(detail.get("error"))
                    response_request_id = (
                        response_request_id or _safe_request_id(detail.get("request_id")) or request_id
                    )
                    raise AgentGuardError(
                        response.status_code,
                        code,
                        _safe_error_message(response.status_code, code),
                        response_request_id,
                    )
                return payload
        except httpx.TimeoutException as exc:
            raise AgentGuardUnavailable(
                0, "API_UNREACHABLE", "AgentGuard API request timed out", request_id
            ) from exc
        except httpx.NetworkError as exc:
            raise AgentGuardUnavailable(
                0, "API_UNREACHABLE", "AgentGuard API connection failed", request_id
            ) from exc
        except httpx.HTTPError as exc:
            raise AgentGuardUnavailable(
                0, "API_UNREACHABLE", "AgentGuard API request failed", request_id
            ) from exc

    # ------------------------------------------------------------------ #
    # typed business methods (mirror AgentGuard sdk.py)
    # ------------------------------------------------------------------ #
    def health(self, *, request_id: str | None = None) -> dict[str, Any]:
        return self.request("GET", "/v1/system/health", request_id=request_id)

    def capabilities(self, *, request_id: str | None = None) -> dict[str, Any]:
        return self.request("GET", "/v1/system/capabilities", request_id=request_id)

    def kernel_status(self, *, request_id: str | None = None) -> dict[str, Any]:
        return self.request("GET", "/v1/kernel/status", request_id=request_id)

    def list_scenarios(self, *, request_id: str | None = None) -> dict[str, Any]:
        return self.request("GET", "/v1/scenarios", request_id=request_id)

    def create_investigation(
        self, payload: Mapping[str, Any], *, request_id: str | None = None
    ) -> dict[str, Any]:
        return self.request("POST", "/v1/investigations", body=payload, request_id=request_id)

    def list_investigations(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "GET", "/v1/investigations",
            query={"status": status, "limit": limit, "offset": offset},
            request_id=request_id,
        )

    def get_investigation(self, request_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/investigations/{_quote(request_id)}")

    def get_evidence(self, request_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/evidence/investigations/{_quote(request_id)}")

    def preview_defense_policies(self, request_id: str) -> dict[str, Any]:
        return self.request("POST", f"/v1/defense-policies/{_quote(request_id)}/preview")

    def get_defense_policies(self, request_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/defense-policies/{_quote(request_id)}")

    def get_report(self, run_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/reports/{_quote(run_id)}")

    def search_verified_experiences(
        self,
        *,
        query: str = "",
        scenario_id: str | None = None,
        risk_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self.request(
            "GET", "/v1/experiences",
            query={
                "q": query, "scenario_id": scenario_id, "risk_type": risk_type,
                "verified_only": "true", "limit": limit,
            },
        )

    def get_api_audit_events(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self.request(
            "GET", "/v1/system/audit-events",
            query={"limit": limit, "offset": offset},
            operator=True,
        )

    # ------------------------------------------------------------------ #
    # C1/C2 capabilities (published at pinned commit 907aa19; guarded by
    # capability discovery so older pinned upstreams degrade explicitly)
    # ------------------------------------------------------------------ #
    def get_interaction_graph(self, request_id: str) -> dict[str, Any]:
        """C1 message-level interaction graph. The response self-describes
        availability: available=false with limitations[] is an honest upstream
        answer, not an error."""
        return self.request("GET", f"/v1/investigations/{_quote(request_id)}/interaction-graph")

    def list_experiments(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """C2 read-only experiment index."""
        return self.request(
            "GET", "/v1/experiments",
            query={"limit": limit, "offset": offset},
        )

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/experiments/{_quote(experiment_id)}")

    def compare_experiments(self, run_ids: list[str]) -> dict[str, Any]:
        """C2 controlled comparison; the upstream contract requires run_ids."""
        return self.request("POST", "/v1/experiments/compare", body={"run_ids": run_ids})

    def get_run_timeline(self, run_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/runs/{_quote(run_id)}/timeline")

    # ------------------------------------------------------------------ #
    # D-round capabilities retained by the pinned I7 API / 1.1.0rc1
    # ------------------------------------------------------------------ #
    def get_readiness(self) -> dict[str, Any]:
        """Layered readiness checks (agentguard_api / warden_connectivity /
        contract_source / ...), each with status, source and blockers."""
        return self.request("GET", "/v1/system/readiness")

    def get_investigation_options(self) -> dict[str, Any]:
        """Real resource discovery: per-audit-mode submittable flag and
        blockers[] - the create form renders these verbatim."""
        return self.request("GET", "/v1/investigations/options")

    def get_investigation_timeline(self, request_id: str) -> dict[str, Any]:
        """Persisted investigation timeline keyed by the base request id."""
        return self.request("GET", f"/v1/investigations/{_quote(request_id)}/timeline")

    def list_reports(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self.request("GET", "/v1/reports", query={"limit": limit, "offset": offset})

    def get_run_findings(self, run_id: str) -> dict[str, Any]:
        """E1 risk findings linked to a WARDEN run."""
        return self.request("GET", f"/v1/runs/{_quote(run_id)}/findings")

    def get_run_hypotheses(self, run_id: str) -> dict[str, Any]:
        """E1 falsifiable hypotheses for a WARDEN run."""
        return self.request("GET", f"/v1/runs/{_quote(run_id)}/hypotheses")

    def get_run_investigation(self, run_id: str) -> dict[str, Any]:
        """D3 multi-round investigation journal (rounds, decisions, budget)."""
        return self.request("GET", f"/v1/runs/{_quote(run_id)}/investigation")

    def list_strategy_evaluations(
        self,
        *,
        data_partition: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List persisted strategy evaluation records from AgentGuard Research."""
        return self.request(
            "GET",
            "/v1/research/strategy-evaluations",
            query={"data_partition": data_partition, "limit": limit, "offset": offset},
        )

    def get_strategy_evaluation(self, evaluation_id: str) -> dict[str, Any]:
        """Read one persisted strategy evaluation artifact by its registry ID."""
        return self.request(
            "GET", f"/v1/research/strategy-evaluations/{_quote(evaluation_id)}"
        )

    # ------------------------------------------------------------------ #
    # J2.1: AgentGuard RC5 research registry (BFF project ownership is local)
    # ------------------------------------------------------------------ #
    def get_research_capabilities(self) -> dict[str, Any]:
        return self.request("GET", "/v1/research/capabilities")

    def list_studies(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        track: str | None = None,
        sort_by: str = "registered_at",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        return self.request(
            "GET", "/v1/studies",
            query={
                "limit": limit, "offset": offset, "track": track,
                "sort_by": sort_by, "sort_order": sort_order,
            },
        )

    def register_study(
        self,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Register a protocol. POST is never retried by the HTTP client."""
        return self.request(
            "POST", "/v1/studies", body=payload, request_id=request_id,
            operator=True, idempotency_key=idempotency_key,
        )

    def get_study(self, study_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}")

    def submit_study_run(self, study_id: str, arm_id: str, key: str) -> dict[str, Any]:
        return self.request("POST", f"/v1/studies/{_quote(study_id)}/runs",
                            body={"arm_id": arm_id}, operator=True, idempotency_key=key)

    def list_study_runs(self, study_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}/runs")

    def submit_study_batch(self, study_id: str, key: str) -> dict[str, Any]:
        return self.request("POST", f"/v1/studies/{_quote(study_id)}/run-batches",
                            operator=True, idempotency_key=key, timeout_seconds=120)

    def list_study_batches(self, study_id: str, *, limit=50, offset=0) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}/run-batches",
                            query={"limit": limit, "offset": offset})

    def submit_replicate_batch(self, study_id: str, replicate_id: str, key: str) -> dict[str, Any]:
        return self.request("POST", f"/v1/studies/{_quote(study_id)}/replicate-batches",
                            body={"replicate_id": replicate_id}, operator=True,
                            idempotency_key=key, timeout_seconds=120)

    def get_batch_comparison(self, study_id: str, batch_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}/comparisons/batches/{_quote(batch_id)}")

    def get_submission_intent(self, study_id: str, key: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}/submission-intents/{_quote(key)}")

    def get_execution_contract(self, study_id: str, arm_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}/arms/{_quote(arm_id)}/execution-contract")

    def get_study_run(self, study_id: str, workflow_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}/runs/{_quote(workflow_id)}")

    def get_experiment_view(self, study_id: str, workflow_id: str, section: str,
                            **query) -> dict[str, Any]:
        if section not in {"visualization", "timeline"}:
            raise ValueError("Unknown experiment view")
        return self.request("GET",
            f"/v1/studies/{_quote(study_id)}/runs/{_quote(workflow_id)}/{section}", query=query)

    def get_study_comparison(self, study_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}/comparison")

    def get_study_integrity(self, study_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/studies/{_quote(study_id)}/integrity")

    def list_study_analyses(
        self,
        study_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        evidence_mode: str | None = None,
        sort_order: str = "asc",
    ) -> dict[str, Any]:
        return self.request(
            "GET", f"/v1/studies/{_quote(study_id)}/analyses",
            query={
                "limit": limit, "offset": offset,
                "evidence_mode": evidence_mode, "sort_order": sort_order,
            },
        )

    # ------------------------------------------------------------------ #
    # E6: investigation service (loop-scoped)
    # ------------------------------------------------------------------ #
    def get_risk_analysis(self, request_id: str) -> dict[str, Any]:
        """E6 risk analysis summary for a base investigation."""
        return self.request("GET", f"/v1/investigations/{_quote(request_id)}/risk-analysis")

    def list_investigation_loops(self, base_request_id: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List the persisted loop registry; count is page-scoped in I7."""
        return self.request(
            "GET", "/v1/investigation-loops",
            query={"base_request_id": base_request_id, "limit": limit, "offset": offset})

    def get_investigation_loop(self, loop_id: str) -> dict[str, Any]:
        """E6 get a single investigation loop by loop_id."""
        return self.request("GET", f"/v1/investigation-loops/{_quote(loop_id)}")

    def get_investigation_decisions(self, loop_id: str) -> dict[str, Any]:
        """E6 get per-round decisions for a loop."""
        return self.request("GET", f"/v1/investigation-loops/{_quote(loop_id)}/decisions")

    def get_investigation_evidence_changes(self, loop_id: str) -> dict[str, Any]:
        """E6 get evidence delta across rounds for a loop."""
        return self.request("GET", f"/v1/investigation-loops/{_quote(loop_id)}/evidence-changes")

    def get_investigation_loop_budget(self, loop_id: str) -> dict[str, Any]:
        """E6 get budget consumption for a loop."""
        return self.request("GET", f"/v1/investigation-loops/{_quote(loop_id)}/budget")

    def create_investigation_loop(
        self,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Create one loop with the separate Operator credential and stable key.

        POST is never retried by this client. The service layer persists the
        key before calling this method and reconciles any ambiguous result.
        """
        return self.request(
            "POST",
            "/v1/investigation-loops",
            body=payload,
            request_id=request_id,
            operator=True,
            loop_idempotency_key=idempotency_key,
        )

    # ------------------------------------------------------------------ #
    # capability discovery
    # ------------------------------------------------------------------ #
    def discover_operations(self) -> dict[str, bool]:
        """Fetch /openapi.json once and record which tracked operations exist.

        Result is cached per client instance; `unknown` values stay False with
        the discovery failure recorded in last_discovery_error so callers can
        distinguish "not published" from "discovery failed".
        """
        if self._discovered is not None:
            return self._discovered
        tracked = [
            "GET /v1/investigations/{request_id}/interaction-graph",
            "GET /v1/investigations/{request_id}/timeline",
            "GET /v1/experiments",
            "GET /v1/experiments/{experiment_id}",
            "POST /v1/experiments/compare",
            "GET /v1/runs/{run_id}/findings",
            "GET /v1/runs/{run_id}/hypotheses",
            "GET /v1/runs/{run_id}/investigation",
            "GET /v1/system/readiness",
            "GET /v1/investigations/options",
            "GET /v1/reports",
            "GET /v1/investigation-loops",
            "POST /v1/investigation-loops",
            "GET /v1/investigations/{request_id}",
            "GET /v1/investigations/{request_id}/risk-analysis",
            "GET /v1/investigation-loops/{loop_id}",
            "GET /v1/investigation-loops/{loop_id}/decisions",
            "GET /v1/investigation-loops/{loop_id}/evidence-changes",
            "GET /v1/investigation-loops/{loop_id}/budget",
            "GET /v1/defense-policies/{request_id}",
            "GET /v1/research/strategy-evaluations",
            "GET /v1/research/strategy-evaluations/{evaluation_id}",
            "GET /v1/research/capabilities",
            "GET /v1/studies",
            "POST /v1/studies",
            "GET /v1/studies/{study_id}",
            "GET /v1/studies/{study_id}/integrity",
            "GET /v1/studies/{study_id}/analyses",
            "GET /v1/studies/{study_id}/runs",
            "POST /v1/studies/{study_id}/runs",
            "GET /v1/studies/{study_id}/runs/{workflow_id}",
        ]
        try:
            response = self._http.get("/openapi.json")
            raw = response.content
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("openapi payload too large")
            import json

            paths = json.loads(raw.decode("utf-8")).get("paths", {})
            actual = {f"{method.upper()} {path}" for path, ops in paths.items() for method in ops}
            self._discovered = {op: op in actual for op in tracked}
            self._discovery_error = None
        except Exception as exc:  # noqa: BLE001 - discovery must never break a request
            self._discovered = {op: False for op in tracked}
            self._discovery_error = f"{type(exc).__name__}"
            logger.warning("capability discovery failed (%s); tracked ops default to unpublished",
                           type(exc).__name__)
        return self._discovered

    @property
    def discovery_error(self) -> str | None:
        return self._discovery_error


class _TransientStatus(AgentGuardError):
    """A retryable 5xx status on an idempotent request."""

    def __init__(self, status_code: int, payload: dict[str, Any], request_id: str | None) -> None:
        detail = payload.get("detail")
        code = _safe_error_code(detail.get("error")) if isinstance(detail, dict) else "API_REQUEST_REJECTED"
        super().__init__(status_code, code, _safe_error_message(status_code, code), request_id)


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
