"""Evidence response contracts (B5).

These document the BFF's evidence response shape. The BFF normalises
AgentGuard/fixture payloads into this shape; it never fabricates fields.
evidence_level values: synthetic | observational | interventional |
causal_validated. The UI must never label observational evidence as
"causal path confirmed".
"""

from __future__ import annotations

from typing import Any, Literal

EvidenceLevel = Literal["synthetic", "observational", "interventional", "causal_validated"]
VerificationStatus = Literal["verified", "unverified", "blocked", "failed", "unsupported"]

EVIDENCE_LEVELS = ("synthetic", "observational", "interventional", "causal_validated")
VERIFICATION_STATUSES = ("verified", "unverified", "blocked", "failed", "unsupported")


def normalize_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    """Pass-through with explicit defaults; never invents values."""
    return {
        "evidence_id": item.get("evidence_id"),
        "source_system": item.get("source_system"),
        "warden_run_id": item.get("warden_run_id"),
        "warden_plan_id": item.get("warden_plan_id"),
        "target_type": item.get("target_type"),
        "target_ref": item.get("target_ref"),
        "scenario_id": item.get("scenario_id"),
        "artifact_refs": item.get("artifact_refs") or [],
        "evidence_type": item.get("evidence_type"),
        "evidence_level": item.get("evidence_level") if item.get("evidence_level") in EVIDENCE_LEVELS else "synthetic",
        "risk_type": item.get("risk_type"),
        "confidence": item.get("confidence"),
        "limitations": item.get("limitations") or [],
        "verification_status": (
            item.get("verification_status")
            if item.get("verification_status") in VERIFICATION_STATUSES
            else "unverified"
        ),
        "run_status": item.get("run_status"),
        "model_version": item.get("model_version"),
        "causal_validation": item.get("causal_validation"),
        "hypothesis": item.get("hypothesis"),
    }


def normalize_evidence_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalise a per-investigation evidence payload."""
    result: dict[str, Any] = {
        "request_id": payload.get("request_id"),
        "workflow_status": payload.get("workflow_status"),
        "run_status": payload.get("run_status"),
        "limitations": payload.get("limitations") or [],
        "items": [normalize_evidence_item(item) for item in payload.get("items", [])],
    }
    return result
