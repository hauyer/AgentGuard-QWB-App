"""AgentGuard connector tests: headers, errors, size limits, retries, redirects."""

from __future__ import annotations

import json

import httpx
import pytest
from conftest import make_settings

from app.integrations.agentguard_client import (
    GET_RETRY_ATTEMPTS,
    MAX_RESPONSE_BYTES,
    AgentGuardClient,
    AgentGuardError,
    AgentGuardUnavailable,
)


class _RecordingTransport(httpx.MockTransport):
    """MockTransport that records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        super().__init__(self._record)

    def _record(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)

    def _handler(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError("subclass must define _handler")


def _transport_returning(*responses: httpx.Response) -> _RecordingTransport:
    queue = list(responses)

    class T(_RecordingTransport):
        def _handler(self, request: httpx.Request) -> httpx.Response:
            if queue:
                return queue.pop(0)
            return httpx.Response(200, json={"status": "ok"})

    return T()


def test_sends_token_and_request_id_headers() -> None:
    settings = make_settings(agentguard_api_token="api-secret", agentguard_operator_api_token="operator-secret")
    transport = _transport_returning(
        httpx.Response(200, json={"status": "ok", "service": "agentguard", "version": "1"})
    )
    with AgentGuardClient(settings, transport=transport) as client:
        client.health(request_id="audit-42")
        client.get_api_audit_events()
    assert transport.requests[0].headers["X-AgentGuard-Token"] == "api-secret"
    assert transport.requests[0].headers["X-Request-ID"] == "audit-42"
    assert transport.requests[1].headers["X-AgentGuard-Operator-Token"] == "operator-secret"
    # The general token is also sent on operator requests (same as AgentGuard SDK).
    assert transport.requests[1].headers["X-AgentGuard-Token"] == "api-secret"


def test_does_not_send_token_when_unset() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, json={"status": "ok"}))
    with AgentGuardClient(settings, transport=transport) as client:
        client.health()
    assert "X-AgentGuard-Token" not in transport.requests[0].headers


def test_error_mapping_preserves_agentguard_error_code() -> None:
    settings = make_settings()
    transport = _transport_returning(
        httpx.Response(
            503,
            json={"detail": {"error": "WARDEN_NOT_CONFIGURED", "message": "no kernel"}},
            headers={"X-Request-ID": "req-1"},
        )
    )
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.create_investigation({"request_id": "x"})
    error = exc_info.value
    assert error.status_code == 503
    assert error.code == "WARDEN_NOT_CONFIGURED"
    assert error.request_id == "req-1"
    assert "no kernel" in str(error)


def test_network_failure_maps_to_unavailable() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    settings = make_settings()
    with AgentGuardClient(settings, transport=httpx.MockTransport(fail)) as client, pytest.raises(
        AgentGuardUnavailable
    ) as exc_info:
        client.health()
    assert exc_info.value.code == "API_UNREACHABLE"
    assert exc_info.value.status_code == 0


def test_timeout_maps_to_unavailable() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    settings = make_settings()
    with AgentGuardClient(settings, transport=httpx.MockTransport(slow)) as client, pytest.raises(
        AgentGuardUnavailable
    ) as exc_info:
        client.health()
    assert exc_info.value.code == "API_UNREACHABLE"


def test_response_over_size_limit_is_rejected() -> None:
    big = "x" * (MAX_RESPONSE_BYTES + 1)
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, content=big.encode()))
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.health()
    assert exc_info.value.code == "API_RESPONSE_TOO_LARGE"


def test_invalid_json_is_rejected() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, content=b"not-json"))
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.health()
    assert exc_info.value.code == "API_BAD_RESPONSE"


def test_non_object_json_is_rejected() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, json=[1, 2, 3]))
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.health()
    assert exc_info.value.code == "API_BAD_RESPONSE"


def test_get_retries_transient_failure_then_succeeds() -> None:
    settings = make_settings()
    transport = _transport_returning(
        httpx.Response(503, json={"detail": {"error": "TEMPORARY"}}),
        httpx.Response(200, json={"status": "ok", "service": "agentguard", "version": "1"}),
    )
    with AgentGuardClient(settings, transport=transport) as client:
        payload = client.health()
    assert payload["status"] == "ok"
    assert len(transport.requests) == 2


def test_get_exhausts_retries_on_persistent_failure() -> None:
    settings = make_settings()
    transport = _transport_returning(
        *[httpx.Response(503, json={"detail": {"error": "TEMPORARY"}})] * (GET_RETRY_ATTEMPTS + 1),
    )
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.health()
    assert exc_info.value.status_code == 503
    assert len(transport.requests) == GET_RETRY_ATTEMPTS + 1


def test_post_is_never_retried() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(503, json={"detail": {"error": "TEMPORARY"}}))
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.create_investigation({"request_id": "x"})
    assert exc_info.value.code == "TEMPORARY"
    assert len(transport.requests) == 1


def test_redirect_is_not_followed() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(302, headers={"Location": "http://evil.example/"}))
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.health()
    assert exc_info.value.status_code == 302


def test_rejects_unversioned_or_unsafe_path() -> None:
    settings = make_settings()
    with AgentGuardClient(settings, transport=httpx.MockTransport(_dummy)) as client:
        with pytest.raises(ValueError):
            client.request("GET", "/admin/delete?x=1")
        with pytest.raises(ValueError):
            client.request("TRACE", "/v1/system/health")


def test_request_ids_are_generated_when_not_supplied() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, json={"status": "ok"}))
    with AgentGuardClient(settings, transport=transport) as client:
        client.health()
    assert transport.requests[0].headers["X-Request-ID"]


def test_quotes_resource_identifiers() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, json={"request_id": "a/b", "status": "planned"}))
    with AgentGuardClient(settings, transport=transport) as client:
        client.get_investigation("a/b")
    assert transport.requests[0].url.raw_path == b"/v1/investigations/a%2Fb"


def test_body_is_json_encoded() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, json={"status": "planned"}))
    with AgentGuardClient(settings, transport=transport) as client:
        client.create_investigation({"request_id": "r", "mode": "observation"})
    body = json.loads(transport.requests[0].content.decode())
    assert body == {"request_id": "r", "mode": "observation"}


def _dummy(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={})
