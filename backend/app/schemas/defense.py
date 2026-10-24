"""Defense policy response contracts (B5).

The BFF only reads and previews defense candidates. Execution is never
simulated: DefenseCandidate.execution_supported is false until AgentGuard's
public API, permission model and an externally verified executor exist.
POST /defense-policies/{id}/preview persists/updates a preview only and never
performs a defense action.
"""

from __future__ import annotations

from typing import Any


def normalize_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": item.get("candidate_id"),
        "risk": item.get("risk"),
        "target": item.get("target"),
        "operation_type": item.get("operation_type"),
        "rationale": item.get("rationale"),
        "authorization_required": item.get("authorization_required"),
        "estimated_cost": item.get("estimated_cost"),
        "related_evidence": item.get("related_evidence") or [],
        "status": item.get("status"),
        "execution_supported": bool(item.get("execution_supported")),
        "execution_reason": item.get("execution_reason"),
    }


def normalize_defense_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "run_id": payload.get("run_id"),
        "status": payload.get("status"),
        "candidates": [normalize_candidate(item) for item in payload.get("candidates", [])],
        "policy_notes": payload.get("policy_notes") or [],
        "execution_performed": bool(payload.get("execution_performed")),
        "evidence_mode": payload.get("evidence_mode"),
    }
