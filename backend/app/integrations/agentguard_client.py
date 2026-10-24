"""Unified AgentGuard API client (BFF connector).

Contract baseline: AgentGuard commit 00d12bee352060ea6014eebea8400edd7c74a029
(feature/agentguard-upper-layer-v1), documented in docs/api/AGENTGUARD_API_MATRIX.md.

Safety rules enforced here (mirror the upstream SDK contract):
  * upstream origin is fixed by server config; callers cannot choose arbitrary hosts
  * X-Request-ID is always sent; a caller-supplied value is preserved
  * timeout is bounded (0, 120] seconds
  * responses larger than 4 MiB are rejected
  * POST/PUT/PATCH/DELETE are never auto-retried
  * only idempotent GET requests may be retried, with a bounded backoff
  * redirects are never followed
  * request bodies and tokens are never written to logs
"""

from __future__ import annotations

import logging
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
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=False,
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
    ) -> dict[str, Any]:
        if not path.startswith("/v1/") or "?" in path or "#" in path:
            raise ValueError("path must be a versioned AgentGuard /v1 path")
        method = method.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("unsupported HTTP method")

        headers: dict[str, str] = {
            "Accept": "application/json",
            "X-Request-ID": request_id or str(uuid.uuid4()),
        }
        if self._settings.agentguard_api_token:
            headers["X-AgentGuard-Token"] = self._settings.agentguard_api_token
        if operator and self._settings.agentguard_operator_api_token:
            headers["X-AgentGuard-Operator-Token"] = self._settings.agentguard_operator_api_token

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
                return self._perform(method, path, headers=headers, params=params, json_body=json_body)
            except (AgentGuardUnavailable, _TransientStatus) as exc:
                if not retryable or attempt > GET_RETRY_ATTEMPTS:
                    raise
                delay = GET_RETRY_BACKOFF_SECONDS[min(attempt - 1, len(GET_RETRY_BACKOFF_SECONDS) - 1)]
                logger.warning(
                    "AgentGuard GET %s failed (attempt %s/%s) with %s; retrying in %.1fs",
                    path, attempt, GET_RETRY_ATTEMPTS + 1, exc.code, delay,
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
    ) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, headers=headers, params=params, json=json_body)
        except httpx.TimeoutException as exc:
            raise AgentGuardUnavailable(
                0, "API_UNREACHABLE", f"AgentGuard API request timed out: {type(exc).__name__}"
            ) from exc
        except httpx.NetworkError as exc:
            raise AgentGuardUnavailable(
                0, "API_UNREACHABLE", f"AgentGuard API request failed: {type(exc).__name__}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AgentGuardUnavailable(
                0, "API_UNREACHABLE", f"AgentGuard API request failed: {type(exc).__name__}"
            ) from exc

        response_request_id = response.headers.get("X-Request-ID")
        raw = response.content
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AgentGuardError(
                response.status_code,
                "API_RESPONSE_TOO_LARGE",
                f"AgentGuard API response exceeded {MAX_RESPONSE_BYTES} bytes",
                response_request_id,
            )
        payload: Any = {}
        if raw:
            try:
                payload = response.json()
            except (ValueError, UnicodeDecodeError) as exc:
                raise AgentGuardError(
                    response.status_code,
                    "API_BAD_RESPONSE",
                    "AgentGuard API returned invalid JSON",
                    response_request_id,
                ) from exc
        if not isinstance(payload, dict):
            raise AgentGuardError(
                response.status_code,
                "API_BAD_RESPONSE",
                "AgentGuard API response must be a JSON object",
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
                detail = {"message": "AgentGuard API request was rejected"}
            raise AgentGuardError(
                response.status_code,
                str(detail.get("error", "API_REQUEST_REJECTED")),
                str(detail.get("message", detail.get("error", "AgentGuard API request was rejected"))),
                response_request_id or detail.get("request_id"),
            )
        return payload

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


class _TransientStatus(AgentGuardError):
    """A retryable 5xx status on an idempotent request."""

    def __init__(self, status_code: int, payload: dict[str, Any], request_id: str | None) -> None:
        detail = payload.get("detail")
        code = detail.get("error", "API_TRANSIENT") if isinstance(detail, dict) else "API_TRANSIENT"
        message = (
            detail.get("message", detail.get("error", "AgentGuard API returned a transient failure"))
            if isinstance(detail, dict)
            else "AgentGuard API returned a transient failure"
        )
        super().__init__(status_code, str(code), str(message), request_id)


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
