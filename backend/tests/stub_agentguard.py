"""Stub AgentGuard service implementing the documented public API contract.

Used only in tests and offline verification. Every response shape follows the
AgentGuard contract pinned at commit 00d12bee352060ea6014eebea8400edd7c74a029
(docs/api/AGENTGUARD_API_MATRIX.md). This stub never implies real WARDEN/model
availability: kernel status is explicitly configurable and defaults to
not_configured.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

APP_VERSION = "0.1.0-stub"

CAPABILITIES_MANIFEST: dict = {
    "schema_version": "0.1",
    "provider_id": "stub-warden",
    "provider_version": "0.3.0",
    "backend_mode": "synthetic",
    "capabilities": {
        "probe_training": False,
        "sae_available": False,
        "activation_hooks": False,
        "causal_audit": False,
    },
    "supported_target_types": ["message", "tool_call", "tool_result"],
    "supported_operations": ["block"],
    "limitations": ["Stub service: capabilities are not real WARDEN capabilities."],
}

GOVERNED_EVIDENCE_ITEM: dict = {
    "schema_version": "0.1",
    "evidence_id": "ev-stub-000000000001",
    "source_system": "warden",
    "warden_run_id": "run-stub-0001",
    "warden_plan_id": "plan-stub-0001",
    "target_type": "tool_call",
    "target_ref": "agent-a:tool-1",
    "scenario_id": "scenario-stub",
    "artifact_refs": [],
    "evidence_type": "observation",
    "evidence_level": "synthetic",
    "risk_type": "unknown",
    "confidence": None,
    "limitations": ["Stub evidence; no artifact integrity verified."],
    "verification_status": "unverified",
    "run_status": "unknown",
    "model_version": "unknown",
    "scenario_version": "unknown",
    "causal_validation": None,
}


class StubAuditRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=256)
    contract_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=512)
    runtime_id: str = Field(min_length=1, max_length=256)
    mode: Literal["observation", "capture_only", "detection", "causal_audit", "defense_evaluation"] = "causal_audit"
    probe_id: str | None = None
    sae_id: str | None = None
    capture_targets: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    authorization_ref: str | None = None
    scenario_id: str | None = None
    risk_type: str | None = None
    start_run: bool = True
    wait_for_completion: bool = False
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    poll_interval_seconds: float = Field(default=0.5, ge=0.1, le=10.0)


def create_stub_app(
    *,
    kernel_status: str = "not_configured",
    warden_available: bool = False,
    capabilities_status: int = 200,
) -> FastAPI:
    app = FastAPI(title="AgentGuard Stub")

    state = {"kernel_status": kernel_status, "warden_available": warden_available}
    # request_ids the stub will acknowledge as existing (B11 contract fidelity:
    # GET on an unknown id must 404, matching the real AgentGuard service)
    known_investigations: set[str] = {"inv-stub-0001"}

    @app.get("/v1/system/health")
    def health() -> dict:
        return {"status": "ok", "service": "agentguard", "version": APP_VERSION}

    @app.get("/v1/system/capabilities")
    def capabilities() -> dict:
        if capabilities_status >= 400:
            raise HTTPException(status_code=capabilities_status, detail={"error": "INTERNAL"})
        return CAPABILITIES_MANIFEST

    @app.get("/v1/kernel/status")
    def kernel_status_route() -> dict:
        if state["kernel_status"] == "available":
            return {
                "status": "available",
                "kernel": "WARDEN",
                "base_url": "http://stub-warden:9100",
                "health": {"status": "ok"},
                "authoritative_for": ["probe", "sae", "causal_audit", "low_level_evidence"],
            }
        return {
            "status": state["kernel_status"],
            "kernel": "WARDEN",
            "base_url": None,
            "authoritative_for": ["probe", "sae", "causal_audit", "low_level_evidence"],
            "reason": "Stub: WARDEN is not configured.",
        }

    @app.get("/v1/scenarios")
    def scenarios() -> dict:
        return {
            "items": [
                {
                    "scenario_id": "scenario-stub",
                    "name": "Stub scenario",
                    "description": "Fixed offline fixture for contract tests.",
                    "risk_types": ["unknown"],
                }
            ]
        }

    @app.post("/v1/investigations")
    def create_investigation(request: StubAuditRequest) -> dict:
        if not state["warden_available"]:
            raise HTTPException(
                status_code=503,
                detail={"error": "WARDEN_NOT_CONFIGURED", "message": "Stub WARDEN is not configured"},
            )
        known_investigations.add(request.request_id)
        return {
            "request_id": request.request_id,
            "status": "planned",
            "submission_status": "planned",
            "plan": {"plan_id": f"plan-{request.request_id}"},
            "run": None,
            "message": "Stub accepted the audit request.",
        }

    @app.get("/v1/investigations")
    def list_investigations(limit: int = 50, offset: int = 0) -> dict:
        items = [{
            "request_id": "inv-stub-0001",
            "status": "completed",
            "workflow_status": "completed",
            "revision": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "plan_id": "plan-stub-0001",
            "run_id": "run-stub-0001",
            "error_code": None,
        }]
        return {"items": items, "count": len(items), "offset": offset, "limit": limit,
                "next_offset": None}

    @app.get("/v1/investigations/{request_id}")
    def get_investigation(request_id: str) -> dict:
        # Contract fidelity (B11): the real service returns 404 for unknown
        # request_ids - the stub must not validate arbitrary IDs either.
        known = known_investigations
        if request_id not in known:
            from fastapi import HTTPException

            raise HTTPException(status_code=404,
                                detail={"error": "NOT_FOUND", "message": "unknown workflow"})
        return {
            "request_id": request_id,
            "status": "completed",
            "workflow_status": "completed",
            "revision": 1,
            "statistics": {},
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "plan_id": "plan-stub-0001",
            "run_id": "run-stub-0001",
            "result": {"status": "completed"},
            "error_code": None,
            "error_message": None,
        }

    @app.get("/v1/evidence/investigations/{request_id}")
    def get_evidence(request_id: str) -> dict:
        return {
            "request_id": request_id,
            "workflow_status": "completed",
            "run_status": "unknown",
            "items": [GOVERNED_EVIDENCE_ITEM],
            "limitations": ["Stub evidence: no completed-run verification was performed."],
        }

    @app.get("/v1/defense-policies/{request_id}")
    def get_defense_policies(request_id: str) -> dict:
        return {
            "schema_version": "0.1",
            "run_id": request_id,
            "status": "preview_only",
            "candidates": [],
            "policy_notes": ["Stub: no defense candidates without evidence."],
            "execution_performed": False,
            "evidence_mode": "synthetic",
        }

    @app.post("/v1/defense-policies/{request_id}/preview")
    def preview_defense_policies(request_id: str) -> dict:
        return get_defense_policies(request_id)

    @app.get("/v1/reports/{run_id}")
    def get_report(run_id: str) -> dict:
        return {
            "run_id": run_id,
            "experiment_id": "exp-stub-0001",
            "scenario_id": "scenario-stub",
            "status": "completed",
            "policy_profile": "read_only",
            "findings": [],
            "intervention_history": [],
            "evidence": [],
        }

    @app.get("/v1/experiences")
    def experiences() -> dict:
        return {
            "schema_version": "0.2",
            "query": "",
            "items": [],
            "total": 0,
            "recommendation_note": "Stub: no verified experiences.",
        }

    @app.get("/v1/system/audit-events")
    def audit_events(
        x_agentguard_operator_token: str | None = Header(default=None, alias="X-AgentGuard-Operator-Token"),
    ) -> dict:
        if x_agentguard_operator_token != "operator-secret":
            raise HTTPException(status_code=403, detail={"error": "OPERATOR_TOKEN_REQUIRED"})
        return {"items": [], "count": 0, "offset": 0, "limit": 100}

    @app.post("/v1/defense-policies/{request_id}/execute")
    def execute_defense(request_id: str) -> dict:
        raise HTTPException(
            status_code=501,
            detail={"error": "UNSUPPORTED", "message": "External defense executor is unsupported."},
        )

    return app
