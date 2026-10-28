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


class _ChunkedBody(httpx.SyncByteStream):
    def __init__(self, chunks: int) -> None:
        self.chunks = chunks
        self.consumed = 0

    def __iter__(self):
        for _ in range(self.chunks):
            self.consumed += 64 * 1024
            yield b"x" * (64 * 1024)

    def close(self) -> None:
        pass


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


def test_loop_create_sends_operator_and_idempotency_headers_without_retry() -> None:
    settings = make_settings(agentguard_api_token="api-secret", agentguard_operator_api_token="operator-secret")
    transport = _transport_returning(
        httpx.Response(503, json={"detail": {"error": "TRY_AGAIN", "message": "upstream unavailable"}})
    )
    payload = {"schema_version": "1.0", "base_request_id": "inv-1", "strategy": "information_value"}
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError):
        client.create_investigation_loop(
            payload, idempotency_key="stable-key", request_id="stable-submission-id"
        )
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/investigation-loops"
    assert request.headers["X-AgentGuard-Operator-Token"] == "operator-secret"
    assert request.headers["X-Loop-Idempotency-Key"] == "stable-key"
    assert request.headers["X-Request-ID"] == "stable-submission-id"
    assert json.loads(request.content) == payload


def test_rc5_study_create_sends_idempotency_header_and_never_auto_retries() -> None:
    settings = make_settings(agentguard_operator_api_token="operator-secret")
    transport = _transport_returning(
        httpx.Response(503, json={"detail": {"error": "TRY_AGAIN", "message": "upstream unavailable"}})
    )
    payload = {"title": "Preregistered study"}
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError):
        client.register_study(payload, idempotency_key="stable.study-key", request_id="study-request-1")
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/studies"
    assert request.headers["Idempotency-Key"] == "stable.study-key"
    assert request.headers["X-AgentGuard-Operator-Token"] == "operator-secret"
    assert request.headers["X-Request-ID"] == "study-request-1"
    assert json.loads(request.content) == payload


def test_rc5_study_create_rejects_invalid_idempotency_key_before_network() -> None:
    transport = _transport_returning(httpx.Response(201, json={"study_id": "study-1"}))
    with AgentGuardClient(make_settings(), transport=transport) as client, pytest.raises(
        ValueError, match="idempotency_key"
    ):
        client.register_study({"title": "Preregistered study"}, idempotency_key="bad key")
    assert transport.requests == []


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
    assert "not configured" in str(error)
    assert "no kernel" not in str(error)


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
    assert exc_info.value.status_code == 502


def test_streaming_response_is_stopped_when_size_limit_is_crossed() -> None:
    body = _ChunkedBody(100)
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, stream=body))
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.health()
    assert exc_info.value.code == "API_RESPONSE_TOO_LARGE"
    assert body.consumed < body.chunks * 64 * 1024


def test_invalid_json_is_rejected() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, content=b"not-json"))
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.health()
    assert exc_info.value.code == "API_BAD_RESPONSE"
    assert exc_info.value.status_code == 502


def test_non_object_json_is_rejected() -> None:
    settings = make_settings()
    transport = _transport_returning(httpx.Response(200, json=[1, 2, 3]))
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.health()
    assert exc_info.value.code == "API_BAD_RESPONSE"
    assert exc_info.value.status_code == 502


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
    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "API_REDIRECT_REJECTED"


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


@pytest.mark.parametrize("status", [401, 403, 422, 429, 500, 502, 503])
def test_upstream_http_errors_keep_status_but_sanitize_body(status: int) -> None:
    settings = make_settings()
    transport = _transport_returning(
        httpx.Response(
            status,
            json={"detail": {"error": "SECRET TOKEN / private/path", "message": "traceback SECRET TOKEN"}},
            headers={"X-Request-ID": "bad\r\nX-Evil: yes"},
        )
    )
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.create_investigation({"request_id": "x"}, request_id="stable-request-1")
    error = exc_info.value
    assert error.status_code == status
    assert error.code == "API_REQUEST_REJECTED"
    assert error.request_id == "stable-request-1"
    assert "SECRET" not in str(error)
    assert "private/path" not in str(error)
    assert len(transport.requests) == 1


def test_known_upstream_error_message_is_replaced_by_safe_text() -> None:
    settings = make_settings()
    transport = _transport_returning(
        httpx.Response(
            503,
            json={"detail": {"error": "WARDEN_NOT_CONFIGURED", "message": "secret: /srv/internal/token"}},
            headers={"X-Request-ID": "upstream-req-2"},
        )
    )
    with AgentGuardClient(settings, transport=transport) as client, pytest.raises(AgentGuardError) as exc_info:
        client.create_investigation({"request_id": "x"}, request_id="app-req-2")
    assert exc_info.value.code == "WARDEN_NOT_CONFIGURED"
    assert exc_info.value.request_id == "upstream-req-2"
    assert str(exc_info.value) == "WARDEN is not configured on the AgentGuard service."
    assert "/srv/internal/token" not in str(exc_info.value)


def test_post_disconnect_is_ambiguous_and_never_retried_with_same_request_id() -> None:
    seen: list[str] = []

    def disconnect(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["X-Request-ID"])
        raise httpx.ReadError("connection dropped after submit", request=request)

    settings = make_settings()
    with AgentGuardClient(settings, transport=httpx.MockTransport(disconnect)) as client, pytest.raises(
        AgentGuardUnavailable
    ) as exc_info:
        client.create_investigation({"request_id": "x"}, request_id="stable-post-id")
    assert exc_info.value.request_id == "stable-post-id"
    assert seen == ["stable-post-id"]


def test_post_resubmission_preserves_request_id_and_does_not_auto_retry() -> None:
    settings = make_settings()
    transport = _transport_returning(
        httpx.Response(200, json={"request_id": "stable-post-id"}),
        httpx.Response(200, json={"request_id": "stable-post-id"}),
    )
    with AgentGuardClient(settings, transport=transport) as client:
        client.create_investigation({"request_id": "stable-post-id"}, request_id="stable-post-id")
        client.create_investigation({"request_id": "stable-post-id"}, request_id="stable-post-id")
    assert len(transport.requests) == 2
    assert [request.headers["X-Request-ID"] for request in transport.requests] == [
        "stable-post-id", "stable-post-id"
    ]


def test_client_ignores_proxy_environment_and_keeps_token_server_side(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://untrusted-proxy.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted-proxy.invalid:8080")
    settings = make_settings(agentguard_api_token="api-secret")
    transport = _transport_returning(httpx.Response(200, json={"status": "ok"}))
    with AgentGuardClient(settings, transport=transport) as client:
        assert client._http._trust_env is False
        client.health()
    request = transport.requests[0]
    assert request.headers["X-AgentGuard-Token"] == "api-secret"
    assert "api-secret" not in request.url.__str__()


def test_rejects_untrusted_request_id_characters() -> None:
    settings = make_settings()
    with (
        AgentGuardClient(settings, transport=httpx.MockTransport(_dummy)) as client,
        pytest.raises(ValueError, match="request_id"),
    ):
        client.health(request_id="bad\r\nX-Evil: yes")


def _dummy(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={})
