"""Offline pin validation plus an optional live AgentGuard compatibility check.

Usage:
    python scripts/check_agentguard_contract.py [--base-url URL] [--token TOKEN]

The repository snapshot, its canonical hash, endpoint inventory and key request
shape are checked on every run. The optional live check then verifies the
reachable API's version, endpoint inventory and health. A missing live service
returns 42 after the offline check passes; it is never reported as a live pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "contracts" / "agentguard-version.json"
SKIP_STATUS = 42  # pytest-style skip exit code
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def load_contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_json(url: str, token: str | None, timeout: float = 8.0) -> dict:
    headers = {"Accept": "application/json"}
    if token:
        headers["X-AgentGuard-Token"] = token
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError(f"response exceeded {MAX_RESPONSE_BYTES} bytes")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("response must be a JSON object")
    return payload


def _operations(openapi: dict) -> set[str]:
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI paths must be an object")
    return {
        f"{method.upper()} {path}"
        for path, operations in paths.items()
        if isinstance(path, str) and isinstance(operations, dict)
        for method in operations
        if isinstance(method, str) and method.lower() in HTTP_METHODS
    }


def _validate_required_headers(openapi: dict, assertions: dict) -> None:
    paths = openapi.get("paths", {})
    required = assertions.get("required_headers", {})
    present = assertions.get("headers_present", {})
    for operation_key in set(required) | set(present):
        method, path = operation_key.split(" ", 1)
        operation = paths.get(path, {}).get(method.lower())
        if not isinstance(operation, dict):
            raise ValueError(f"header-contract operation is missing: {operation_key}")
        headers = {
            item.get("name"): item
            for item in operation.get("parameters", [])
            if isinstance(item, dict) and item.get("in") == "header"
        }
        for name in present.get(operation_key, []):
            if name not in headers:
                raise ValueError(f"{operation_key} must declare header {name}")
        for name in required.get(operation_key, []):
            parameter = headers.get(name)
            if not isinstance(parameter, dict) or parameter.get("required") is not True:
                raise ValueError(f"{operation_key} must require header {name}")


def _validate_422_response(openapi: dict, operation_key: str, *, custom: bool) -> None:
    method, path = operation_key.split(" ", 1)
    operation = openapi.get("paths", {}).get(path, {}).get(method.lower())
    if not isinstance(operation, dict):
        raise ValueError(f"pinned operation is missing: {operation_key}")
    response = operation.get("responses", {}).get("422")
    if response is None:
        return
    schema = response.get("content", {}).get("application/json", {}).get("schema", {})
    if not custom:
        if schema.get("$ref") != "#/components/schemas/HTTPValidationError":
            raise ValueError(f"{operation_key} validation error schema differs from the pinned contract")
        return

    alternatives = schema.get("oneOf", [])
    has_validation_errors = False
    has_typed_error = False
    for alternative in alternatives:
        detail = alternative.get("properties", {}).get("detail", {})
        if detail.get("type") == "array":
            item = detail.get("items", {})
            has_validation_errors = {"type", "loc", "msg"} <= set(item.get("required", []))
        elif detail.get("type") == "object":
            has_typed_error = "error" in detail.get("required", [])
    if not has_validation_errors or not has_typed_error:
        raise ValueError(f"{operation_key} must preserve typed API errors and sanitized validation errors")


def _validate_live_shapes(openapi: dict, contract: dict) -> None:
    """Check the live schema portions consumed by the application."""
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI paths must be an object")
    schemas = openapi.get("components", {}).get("schemas", {})
    assertions = contract.get("contract_assertions", {})
    for operation_key, expected in assertions.get("request_models", {}).items():
        method, path = operation_key.split(" ", 1)
        operation = paths.get(path, {}).get(method.lower())
        if not isinstance(operation, dict):
            raise ValueError(f"request-model operation is missing: {operation_key}")
        schema_name = expected["schema"]
        request_schema = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        if request_schema.get("$ref") != f"#/components/schemas/{schema_name}":
            raise ValueError(f"{operation_key} no longer references {schema_name}")
        model_schema = schemas.get(schema_name, {})
        required = set(expected.get("required_fields", []))
        if not required <= set(model_schema.get("required", [])):
            raise ValueError(f"{schema_name} required fields differ from the pinned contract")
        if expected.get("rejects_extra_fields") and model_schema.get("additionalProperties") is not False:
            raise ValueError(f"{schema_name} no longer rejects undeclared fields")

    for operation_key, expected_parameters in assertions.get("pagination_parameters", {}).items():
        method, path = operation_key.split(" ", 1)
        operation = paths.get(path, {}).get(method.lower())
        if not isinstance(operation, dict):
            raise ValueError(f"pagination operation is missing: {operation_key}")
        parameters = {
            item.get("name"): item
            for item in operation.get("parameters", [])
            if isinstance(item, dict) and item.get("in") == "query"
        }
        if not set(expected_parameters) <= set(parameters):
            raise ValueError(f"{operation_key} pagination parameters differ from the pinned contract")
        if "limit" in expected_parameters:
            limits = parameters["limit"].get("schema", {})
            if limits.get("minimum") != 1 or limits.get("maximum") != 500:
                raise ValueError(f"{operation_key} limit bounds differ from the pinned contract")
        if "offset" in expected_parameters and parameters["offset"].get("schema", {}).get("minimum") != 0:
            raise ValueError(f"{operation_key} offset bounds differ from the pinned contract")

    _validate_required_headers(openapi, assertions)
    validation_schema = assertions.get("validation_error_schema")
    if validation_schema:
        custom_operations = set(assertions.get("custom_validation_error_operations", []))
        for operation_key in contract["supported_endpoints"]:
            _validate_422_response(openapi, operation_key, custom=operation_key in custom_operations)


def validate_snapshot(contract: dict | None = None) -> dict:
    """Validate the checked-in snapshot against the immutable pin metadata."""
    contract = contract or load_contract()
    pinned = contract["pinned_agentguard"]
    metadata = contract["openapi"]
    snapshot_path = (ROOT / metadata["snapshot"]).resolve()
    try:
        snapshot_path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("OpenAPI snapshot must be inside the QWB-App checkout") from exc
    if not snapshot_path.is_file():
        raise ValueError(f"pinned OpenAPI snapshot is missing: {snapshot_path}")
    try:
        openapi = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"pinned OpenAPI snapshot is unreadable: {exc}") from exc
    if not isinstance(openapi, dict):
        raise ValueError("pinned OpenAPI snapshot must be a JSON object")

    canonical = json.dumps(openapi, sort_keys=True).encode("utf-8")
    actual_hash = hashlib.sha256(canonical).hexdigest()
    if actual_hash != metadata["sha256_canonical_json"]:
        raise ValueError(
            "pinned OpenAPI canonical SHA-256 mismatch: "
            f"expected {metadata['sha256_canonical_json']}, got {actual_hash}"
        )
    raw_hash = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    expected_raw_hash = metadata.get("sha256_file")
    if expected_raw_hash and raw_hash != expected_raw_hash:
        raise ValueError(
            "pinned OpenAPI file SHA-256 mismatch: "
            f"expected {expected_raw_hash}, got {raw_hash}"
        )
    paths = openapi.get("paths")
    if not isinstance(paths, dict) or len(paths) != metadata["path_count"]:
        raise ValueError(
            f"pinned OpenAPI path count mismatch: expected {metadata['path_count']}, "
            f"got {len(paths) if isinstance(paths, dict) else 'invalid'}"
        )
    version = openapi.get("info", {}).get("version") if isinstance(openapi.get("info"), dict) else None
    if version != pinned["upstream_version"]:
        raise ValueError(
            f"snapshot version mismatch: expected {pinned['upstream_version']}, got {version!r}"
        )

    operations = _operations(openapi)
    missing = set(contract["supported_endpoints"]) - operations
    if missing:
        raise ValueError("pinned endpoints missing from snapshot: " + ", ".join(sorted(missing)))

    schemas = openapi.get("components", {}).get("schemas", {})
    assertions = contract.get("contract_assertions", {})
    for operation_key, model_expectation in assertions.get("request_models", {}).items():
        method, path = operation_key.split(" ", 1)
        operation = paths.get(path, {}).get(method.lower())
        if not isinstance(operation, dict):
            raise ValueError(f"request-model operation is missing: {operation_key}")
        request_schema = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        schema_name = model_expectation["schema"]
        if request_schema.get("$ref") != f"#/components/schemas/{schema_name}":
            raise ValueError(f"{operation_key} no longer references {schema_name}")
        model_schema = schemas.get(schema_name, {})
        missing_fields = set(model_expectation.get("required_fields", [])) - set(model_schema.get("required", []))
        if missing_fields:
            raise ValueError(f"{schema_name} is missing required fields: {', '.join(sorted(missing_fields))}")
        if model_expectation.get("rejects_extra_fields") and model_schema.get("additionalProperties") is not False:
            raise ValueError(f"{schema_name} must reject undeclared fields")

    for operation_key, required_parameters in assertions.get("pagination_parameters", {}).items():
        method, path = operation_key.split(" ", 1)
        operation = paths.get(path, {}).get(method.lower())
        if not isinstance(operation, dict):
            raise ValueError(f"pagination operation is missing: {operation_key}")
        parameters = {
            parameter.get("name"): parameter
            for parameter in operation.get("parameters", [])
            if isinstance(parameter, dict) and parameter.get("in") == "query"
        }
        missing_parameters = set(required_parameters) - set(parameters)
        if missing_parameters:
            raise ValueError(
                f"{operation_key} is missing pagination parameters: {', '.join(sorted(missing_parameters))}"
            )
        if "limit" in required_parameters:
            limit_schema = parameters["limit"].get("schema", {})
            if limit_schema.get("minimum") != 1 or limit_schema.get("maximum") != 500:
                raise ValueError(f"{operation_key} limit bounds differ from the pinned contract")
        if "offset" in required_parameters:
            offset_schema = parameters["offset"].get("schema", {})
            if offset_schema.get("minimum") != 0:
                raise ValueError(f"{operation_key} offset bounds differ from the pinned contract")

    _validate_required_headers(openapi, assertions)
    validation_schema = assertions.get("validation_error_schema")
    if validation_schema:
        custom_operations = set(assertions.get("custom_validation_error_operations", []))
        for operation_key in contract["supported_endpoints"]:
            _validate_422_response(openapi, operation_key, custom=operation_key in custom_operations)

    for capability, prefix in contract.get("unsupported_capabilities", {}).items():
        if not isinstance(prefix, str) or not prefix.startswith("/"):
            raise ValueError(f"invalid unsupported capability path for {capability}")
        if any(path.startswith(prefix) for path in paths):
            raise ValueError(f"snapshot unexpectedly publishes unsupported capability {capability}: {prefix}")

    auth = contract.get("auth", {})
    if auth.get("general") != "X-AgentGuard-Token" or auth.get("operator") != "X-AgentGuard-Operator-Token":
        raise ValueError("pinned authentication header contract is missing or changed")
    return openapi


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("AGENTGUARD_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.environ.get("AGENTGUARD_API_TOKEN"))
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--offline-only", action="store_true", help="validate the pinned repository snapshot only")
    args = parser.parse_args()

    contract = load_contract()
    pinned = contract["pinned_agentguard"]
    print(f"pinned: {pinned['repository']} @ {pinned['commit']} ({pinned['branch']})")
    try:
        snapshot = validate_snapshot(contract)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        print(f"FAIL: offline pin validation failed: {exc}")
        return 1
    print(
        "PASS: repository snapshot matches the pinned canonical SHA, version, "
        f"{len(snapshot['paths'])} paths, supported operations and request shape."
    )
    if args.offline_only:
        return 0

    base = args.base_url.rstrip("/")
    try:
        openapi = fetch_json(f"{base}/openapi.json", args.token, args.timeout)
    except (HTTPError, URLError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"SKIP: live AgentGuard unreachable or invalid at {base} ({exc}); offline pin validation passed, "
              "but no Live check ran.")
        return SKIP_STATUS

    live_version = openapi.get("info", {}).get("version") if isinstance(openapi.get("info"), dict) else None
    if live_version != pinned["upstream_version"]:
        print(f"FAIL: live OpenAPI version is {live_version!r}, expected {pinned['upstream_version']!r}.")
        return 1

    expected = set(contract["supported_endpoints"])
    try:
        actual = _operations(openapi)
        pinned_operations = _operations(snapshot)
    except ValueError as exc:
        print(f"FAIL: live OpenAPI is invalid: {exc}")
        return 1
    if len(openapi.get("paths", {})) != contract["openapi"]["path_count"] or actual != pinned_operations:
        missing_from_live = pinned_operations - actual
        added_to_live = actual - pinned_operations
        print(
            "FAIL: live OpenAPI operation inventory differs from the pinned snapshot "
            f"(missing={len(missing_from_live)}, added={len(added_to_live)})."
        )
        return 1
    missing = expected - actual
    if missing:
        print(f"FAIL: {len(missing)} pinned endpoints missing from live OpenAPI:")
        for path in sorted(missing):
            print(f"  - {path}")
        return 1

    try:
        _validate_live_shapes(openapi, contract)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        print(f"FAIL: live OpenAPI request contract differs from the pin: {exc}")
        return 1

    for capability, prefix in contract.get("unsupported_capabilities", {}).items():
        if any(path.startswith(prefix) for path in openapi.get("paths", {})):
            print(f"FAIL: live OpenAPI publishes {capability} absent from the pinned snapshot; review the pin.")
            return 1

    try:
        health = fetch_json(f"{base}/v1/system/health", args.token, args.timeout)
    except (HTTPError, URLError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: live health endpoint could not be verified ({exc}).")
        return 1
    if health.get("status") != "ok":
        print(f"FAIL: health status is {health.get('status')!r}")
        return 1

    if health.get("version") != pinned["upstream_version"]:
        print(
            f"FAIL: live health version is {health.get('version')!r}, "
            f"expected {pinned['upstream_version']!r}"
        )
        return 1
    print(
        f"PASS: live API version {live_version} exposes all {len(expected)} pinned operations; "
        "health is ok. The API does not expose a verifiable commit SHA."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
