"""The checked-in AgentGuard snapshot is a reproducible, offline contract input."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_agentguard_contract.py"
SPEC = importlib.util.spec_from_file_location("agentguard_contract_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
contract_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract_check)


def test_checked_in_snapshot_matches_the_pin() -> None:
    openapi = contract_check.validate_snapshot()
    assert len(openapi["paths"]) == 86
    operations = contract_check._operations(openapi)
    assert "POST /v1/investigation-loops" in operations
    assert "GET /v1/research/strategy-evaluations" in operations
    assert "GET /v1/research/strategy-evaluations/{evaluation_id}" in operations
    assert "GET /v1/system/identity" in operations
    assert "POST /v1/investigation-loops/{loop_id}/reconcile" in operations
    contract = contract_check.load_contract()
    assert "GET /v1/system/identity" not in contract["supported_endpoints"]
    assert "POST /v1/investigation-loops/{loop_id}/reconcile" not in contract["supported_endpoints"]
    contract_check._validate_live_shapes(openapi, contract_check.load_contract())


def test_rc3_diff_matches_retained_rc2_snapshot() -> None:
    contract = contract_check.load_contract()
    openapi = contract_check.validate_snapshot(contract)
    contract_check._validate_pinned_diff(openapi, contract)


def test_rc3_changes_only_the_declared_openapi_version() -> None:
    contract = contract_check.load_contract()
    openapi = contract_check.validate_snapshot(contract)
    previous = contract['previous_contract']
    baseline = json.loads(
        (REPO_ROOT / previous['snapshot']).read_text(encoding='utf-8')
    )
    assert baseline['info']['version'] == '1.1.0rc2'
    assert openapi['info']['version'] == '1.1.0rc3'
    contract_check._validate_pinned_diff(openapi, contract)


def test_rc3_publishes_study_but_not_four_layer_arm_contracts() -> None:
    openapi = contract_check.validate_snapshot()
    paths = openapi['paths']
    assert {'post', 'get'} <= set(paths['/v1/studies'])
    assert 'get' in paths['/v1/studies/{study_id}']
    assert 'post' in paths['/v1/studies/{study_id}/analyses']
    assert 'post' in paths['/v1/runs/{run_id}/experiments/paired']
    assert 'post' in paths['/v1/runs/{run_id}/interventions']

    schemas = openapi['components']['schemas']
    registration_fields = schemas['StudyRegistrationRequest']['properties']
    assert 'track' not in registration_fields
    assert 'arms' not in registration_fields
    assert set(schemas['PairedExperimentRunRequest']['properties']) == {
        'schema_version', 'design_id', 'action_id', 'authorization_ref',
    }

    contract = contract_check.load_contract()
    candidates = {
        item['operation'] for item in contract['candidate_endpoints']['published_not_exposed']
    }
    assert 'POST /v1/studies' in candidates
    assert 'POST /v1/runs/{run_id}/experiments/paired' in candidates
    assert 'POST /v1/runs/{run_id}/interventions' in candidates
    assert candidates.isdisjoint(contract['supported_endpoints'])
    assert '/v1/research/strategy-evaluations' in paths
    assert '/v1/research/strategy-evaluations/{evaluation_id}' in paths


def test_pinned_diff_rejects_supported_response_drift() -> None:
    contract = contract_check.load_contract()
    openapi = deepcopy(contract_check.validate_snapshot(contract))
    openapi["paths"]["/v1/investigations"]["post"]["responses"]["200"] = {
        "description": "unexpected response contract"
    }
    with pytest.raises(ValueError, match="supported operation changed responses"):
        contract_check._validate_pinned_diff(openapi, contract)


def test_rc3_diff_rejects_changes_outside_info_version() -> None:
    contract = contract_check.load_contract()
    openapi = deepcopy(contract_check.validate_snapshot(contract))
    openapi['info']['description'] = 'unreviewed OpenAPI change'
    with pytest.raises(ValueError, match='changed outside info.version'):
        contract_check._validate_pinned_diff(openapi, contract)


def test_snapshot_digest_mismatch_fails_closed() -> None:
    contract = contract_check.load_contract()
    contract["openapi"]["sha256_canonical_json"] = "0" * 64
    with pytest.raises(ValueError, match="canonical SHA-256 mismatch"):
        contract_check.validate_snapshot(contract)


def test_live_shape_checker_rejects_request_contract_drift() -> None:
    openapi = contract_check.validate_snapshot()
    openapi["components"]["schemas"]["WardenAuditRequest"]["required"].remove("runtime_id")
    with pytest.raises(ValueError, match="required fields differ"):
        contract_check._validate_live_shapes(openapi, contract_check.load_contract())


def test_loop_creation_requires_upstream_idempotency_header() -> None:
    openapi = contract_check.validate_snapshot()
    post = openapi["paths"]["/v1/investigation-loops"]["post"]
    header = next(
        item for item in post["parameters"]
        if item.get("in") == "header" and item.get("name") == "X-Loop-Idempotency-Key"
    )
    assert header["required"] is True
    declared_headers = {
        item["name"] for item in post["parameters"] if item.get("in") == "header"
    }
    assert {
        "X-AgentGuard-Operator-Token", "X-Approval-Token", "X-AgentGuard-Token",
    } <= declared_headers
    request = openapi["components"]["schemas"]["InvestigationLoopCreateRequest"]
    assert request["required"] == ["base_request_id"]
    assert request["additionalProperties"] is False
