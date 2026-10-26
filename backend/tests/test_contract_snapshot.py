"""The checked-in AgentGuard snapshot is a reproducible, offline contract input."""

from __future__ import annotations

import importlib.util
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
    assert len(openapi["paths"]) == 84
    operations = contract_check._operations(openapi)
    assert "POST /v1/investigation-loops" in operations
    assert "GET /v1/research/strategy-evaluations" in operations
    assert "GET /v1/research/strategy-evaluations/{evaluation_id}" in operations
    contract_check._validate_live_shapes(openapi, contract_check.load_contract())


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
