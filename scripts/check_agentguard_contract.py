"""Offline pin validation plus an optional live AgentGuard compatibility check.

Usage:
    python scripts/check_agentguard_contract.py [--base-url URL] [--token TOKEN]

The repository snapshot, its raw and canonical hashes, endpoint inventory and
key request shape are checked on every run. Canonicalization matches AgentGuard:
sorted object keys, compact JSON separators, unescaped Unicode, then UTF-8.
The optional live check then verifies the
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


def _canonical_openapi_bytes(openapi: dict) -> bytes:
    """Match AgentGuard's canonical identity algorithm: sorted keys, compact
    separators, unescaped Unicode, and UTF-8 bytes.
    """
    return json.dumps(
        openapi, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


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

    detail = schema.get("properties", {}).get("detail", {})
    envelope_options = schema.get("oneOf", [])
    alternatives = detail.get("oneOf", [])
    if envelope_options:
        alternatives = []
        for envelope in envelope_options:
            nested_detail = envelope.get("properties", {}).get("detail", {})
            alternatives.extend(nested_detail.get("oneOf", []) or [nested_detail])
    has_validation_errors = any(
        item.get("type") == "array"
        and item.get("items", {}).get("type") == "object"
        for item in alternatives
    )
    typed_error = next((
        item.get("properties", {}).get("detail", item)
        for item in alternatives
        if item.get("type") == "object"
        and item.get("properties", {}).get("detail", item).get("type") == "object"
        and "error" in item.get("properties", {}).get("detail", item).get("properties", {})
    ), {})
    typed_properties = typed_error.get("properties", {})
    has_typed_error = (
        "error" in typed_error.get("required", ["error"])
        and
        typed_properties.get("error", {}).get("type") == "string"
        and typed_properties.get("message", {}).get("type") == "string"
    )
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
        validation_operations = assertions.get(
            "validation_error_operations", contract["supported_endpoints"]
        )
        for operation_key in validation_operations:
            _validate_422_response(openapi, operation_key, custom=operation_key in custom_operations)


def _validate_research_contract(openapi: dict, contract: dict) -> None:
    """Validate the RC5 research schemas and the unsafe-analysis boundary."""
    expected = contract.get("research_contract_assertions")
    if not isinstance(expected, dict):
        raise ValueError("RC5 research contract assertions are missing")
    paths = openapi.get("paths", {})
    schemas = openapi.get("components", {}).get("schemas", {})

    def operation(key: str) -> dict:
        method, path = key.split(" ", 1)
        value = paths.get(path, {}).get(method.lower())
        if not isinstance(value, dict):
            raise ValueError(f"research operation is missing: {key}")
        return value

    def response_schema(key: str, status: str, schema_name: str) -> None:
        response = operation(key).get("responses", {}).get(status, {})
        schema = response.get("content", {}).get("application/json", {}).get("schema", {})
        if schema.get("$ref") != f"#/components/schemas/{schema_name}":
            raise ValueError(f"{key} {status} response no longer references {schema_name}")

    cap = expected["capabilities"]
    response_schema(cap["operation"], "200", cap["response_schema"])
    cap_schema = schemas.get(cap["response_schema"], {})
    cap_item_ref = cap_schema.get("properties", {}).get("capabilities", {}).get("items", {}).get("$ref")
    if cap_item_ref != "#/components/schemas/ResearchCapabilityItem":
        raise ValueError("research capability report item schema changed")
    cap_item = schemas.get("ResearchCapabilityItem", {}).get("properties", {}).get("capability", {})
    cap_names = set(cap_item.get("enum", []))
    if cap_names != set(cap["capability_names"]):
        raise ValueError("research capability names differ from the pinned contract")

    study = expected["study_registration"]
    post_study = operation(study["operation"])
    request_schema = post_study.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
    if request_schema.get("$ref") != f"#/components/schemas/{study['request_schema']}":
        raise ValueError("Study registration request schema changed")
    response_schema(study["operation"], "201", study["response_schema"])
    study_headers = {
        item.get("name"): item
        for item in post_study.get("parameters", [])
        if isinstance(item, dict) and item.get("in") == "header"
    }
    key_header = study_headers.get(study["idempotency_header"])
    if not isinstance(key_header, dict) or key_header.get("required") is not study["idempotency_header_required"]:
        raise ValueError("Study registration Idempotency-Key requiredness changed")
    key_schema = key_header.get("schema", {})
    string_schema = key_schema
    if "anyOf" in key_schema:
        string_schema = next((item for item in key_schema["anyOf"] if item.get("type") == "string"), {})
    if string_schema.get("pattern") != study["idempotency_pattern"] or string_schema.get("maxLength") != study["idempotency_max_length"]:
        raise ValueError("Study registration Idempotency-Key format changed")
    if study["conflict_status"] not in post_study.get("responses", {}):
        raise ValueError("Study registration idempotency conflict response is missing")
    registration_properties = schemas.get(study["request_schema"], {}).get("properties", {})
    if not {"track", "arms", "dataset_version", "warden_contract_id", "approval_requirements"} <= set(registration_properties):
        raise ValueError("RC5 Study preregistration metadata fields are missing")

    study_list = expected["study_list"]
    list_parameters = {
        item.get("name"): item
        for item in operation(study_list["operation"]).get("parameters", [])
        if isinstance(item, dict) and item.get("in") == "query"
    }
    if not set(study_list["parameters"]) <= set(list_parameters):
        raise ValueError("Study list filters or pagination parameters changed")
    for name in ("sort_by", "sort_order"):
        if set(list_parameters[name].get("schema", {}).get("enum", [])) != set(study_list[name]):
            raise ValueError(f"Study list {name} allow-list changed")

    detail = expected["study_detail"]
    response_schema(detail["operation"], "200", detail["response_schema"])
    analysis_list = expected["analysis_list"]
    analysis_parameters = {
        item.get("name"): item
        for item in operation(analysis_list["operation"]).get("parameters", [])
        if isinstance(item, dict) and item.get("in") == "query"
    }
    if not set(analysis_list["parameters"]) <= set(analysis_parameters):
        raise ValueError("Study analysis list pagination/filter parameters changed")
    if set(analysis_parameters["evidence_mode"].get("schema", {}).get("anyOf", [{}])[0].get("enum", [])) != set(analysis_list["evidence_mode"]):
        raise ValueError("Study analysis evidence-mode values changed")
    if set(analysis_parameters["sort_order"].get("schema", {}).get("enum", [])) != set(analysis_list["sort_order"]):
        raise ValueError("Study analysis sort-order values changed")

    analysis_write = expected["analysis_write"]
    analysis_post = operation(analysis_write["operation"])
    analysis_request = analysis_post.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
    if analysis_request.get("$ref") != f"#/components/schemas/{analysis_write['request_schema']}":
        raise ValueError("Study analysis request schema changed")
    response_schema(analysis_write["operation"], "201", analysis_write["response_schema"])
    analysis_header = next((
        item for item in analysis_post.get("parameters", [])
        if item.get("in") == "header" and item.get("name") == analysis_write["idempotency_header"]
    ), None)
    if not isinstance(analysis_header, dict) or analysis_header.get("required") is not analysis_write.get(
        "idempotency_header_required", False
    ):
        raise ValueError("Study analysis Idempotency-Key contract changed")
    analysis_key_schema = analysis_header.get("schema", {})
    analysis_key_string = analysis_key_schema
    if "anyOf" in analysis_key_schema:
        analysis_key_string = next(
            (item for item in analysis_key_schema["anyOf"] if item.get("type") == "string"), {}
        )
    if (
        analysis_key_string.get("pattern") != study["idempotency_pattern"]
        or analysis_key_string.get("maxLength") != study["idempotency_max_length"]
    ):
        raise ValueError("Study analysis Idempotency-Key format changed")
    measured_response = analysis_post.get("responses", {}).get(analysis_write["measured_error_status"], {})
    if "Measured outcomes are rejected" not in measured_response.get("description", ""):
        raise ValueError("Measured analysis must remain blocked until source artifacts are verified")
    if analysis_write["operation"] in contract.get("supported_endpoints", []):
        raise ValueError("unverified caller-supplied analysis writes must not be App-supported")


def _validate_pinned_diff(openapi: dict, contract: dict) -> None:
    """Verify the declared OpenAPI delta against the retained previous pin."""
    previous = contract.get("previous_contract")
    diff = contract.get("openapi_diff")
    if not isinstance(previous, dict) or not isinstance(diff, dict):
        raise ValueError("previous OpenAPI pin and diff declaration are required")

    previous_path = (ROOT / previous["snapshot"]).resolve()
    try:
        previous_path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("previous OpenAPI snapshot must be inside the QWB-App checkout") from exc
    if not previous_path.is_file():
        raise ValueError(f"previous OpenAPI snapshot is missing: {previous_path}")
    previous_raw = previous_path.read_bytes()
    if hashlib.sha256(previous_raw).hexdigest() != previous["raw_sha256"]:
        raise ValueError("previous OpenAPI snapshot raw SHA-256 mismatch")
    old = json.loads(previous_raw.decode("utf-8"))
    old_canonical = hashlib.sha256(_canonical_openapi_bytes(old)).hexdigest()
    if old_canonical != previous["canonical_sha256"]:
        raise ValueError("previous OpenAPI snapshot canonical SHA-256 mismatch")
    if len(old.get("paths", {})) != previous["path_count"]:
        raise ValueError("previous OpenAPI snapshot path count mismatch")

    old_operations = _operations(old)
    new_operations = _operations(openapi)
    if len(old_operations) != previous.get("operation_count", len(old_operations)):
        raise ValueError("previous OpenAPI snapshot operation count mismatch")
    if len(new_operations) != contract["openapi"].get("operation_count", len(new_operations)):
        raise ValueError("pinned OpenAPI operation count mismatch")
    actual_added = sorted(new_operations - old_operations)
    actual_removed = sorted(old_operations - new_operations)
    if actual_added != sorted(diff.get("added_operations", [])):
        raise ValueError(f"OpenAPI added-operation diff mismatch: {actual_added}")
    if actual_removed != sorted(diff.get("removed_operations", [])):
        raise ValueError(f"OpenAPI removed-operation diff mismatch: {actual_removed}")

    old_schemas = old.get("components", {}).get("schemas", {})
    new_schemas = openapi.get("components", {}).get("schemas", {})
    actual_modified_schemas = sorted(
        name for name in old_schemas.keys() & new_schemas.keys()
        if old_schemas[name] != new_schemas[name]
    )
    if actual_modified_schemas != sorted(diff.get("modified_schemas", [])):
        raise ValueError(f"OpenAPI modified-schema diff mismatch: {actual_modified_schemas}")

    supported = set(contract["supported_endpoints"])
    legacy_supported = set(contract.get("legacy_supported_endpoints", supported))
    for operation_key in sorted(legacy_supported & old_operations & new_operations):
        method, path = operation_key.split(" ", 1)
        before = old["paths"][path][method.lower()]
        after = openapi["paths"][path][method.lower()]
        if diff.get("assert_full_operation_unchanged_for_legacy_supported") and before != after:
            raise ValueError(f"legacy supported operation changed: {operation_key}")
        for component in diff.get("assert_unchanged_for_supported", []):
            if before.get(component) != after.get(component):
                raise ValueError(f"supported operation changed {component}: {operation_key}")

    actual_modified = sorted(
        key for key in old_operations & new_operations
        if old["paths"][key.split(" ", 1)[1]][key.split(" ", 1)[0].lower()]
        != openapi["paths"][key.split(" ", 1)[1]][key.split(" ", 1)[0].lower()]
    )
    if actual_modified != sorted(diff.get("modified_operations", [])):
        raise ValueError(f"OpenAPI modified-operation diff mismatch: {actual_modified}")

    if diff.get("assert_info_only_version"):
        old_info = dict(old.get("info", {}))
        new_info = dict(openapi.get("info", {}))
        old_version = old_info.pop("version", None)
        new_version = new_info.pop("version", None)
        if old_version != diff.get("from_version") or new_version != diff.get("to_version"):
            raise ValueError("OpenAPI version diff does not match the declared from/to versions")
        if old_info != new_info:
            raise ValueError("OpenAPI info changed outside info.version")

    if diff.get("assert_all_except_info_version"):
        old_comparable = json.loads(json.dumps(old))
        new_comparable = json.loads(json.dumps(openapi))
        old_version = old_comparable.get("info", {}).get("version")
        new_version = new_comparable.get("info", {}).get("version")
        if old_version != diff.get("from_version") or new_version != diff.get("to_version"):
            raise ValueError(
                "OpenAPI version diff does not match the declared from/to versions"
            )
        old_comparable["info"].pop("version", None)
        new_comparable["info"].pop("version", None)
        if old_comparable != new_comparable:
            raise ValueError("OpenAPI changed outside info.version")

    candidate_operations = {
        item["operation"]
        for item in contract.get("candidate_endpoints", {}).get("published_not_exposed", [])
    }
    if not candidate_operations <= new_operations:
        raise ValueError("a candidate endpoint is absent from the pinned OpenAPI snapshot")
    if candidate_operations & supported:
        raise ValueError("candidate endpoints must not also be marked supported by the App")
    for item in contract.get("candidate_endpoints", {}).get("not_published", []):
        if item["operation"] in new_operations:
            raise ValueError(f"endpoint marked not published is present: {item['operation']}")
    for item in contract.get("capability_status", {}).get("published_but_not_app_supported", []):
        if item["operation"] not in new_operations or item["operation"] in supported:
            raise ValueError(f"invalid published-but-not-supported operation: {item['operation']}")


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

    canonical = _canonical_openapi_bytes(openapi)
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
    operation_count = len(_operations(openapi))
    if operation_count != metadata.get("operation_count", operation_count):
        raise ValueError(
            f"pinned OpenAPI operation count mismatch: expected {metadata['operation_count']}, got {operation_count}"
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

    _validate_research_contract(openapi, contract)

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
    _validate_pinned_diff(openapi, contract)
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
