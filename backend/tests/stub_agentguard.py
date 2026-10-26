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
    strategy_evaluations_available: bool = False,
    investigation_loop_report_available: bool = False,
    e2e_isolation_loops: bool = False,
    report_empty_evidence: bool = False,
    report_long_text: bool = False,
) -> FastAPI:
    app = FastAPI(title="AgentGuard Stub")

    state = {"kernel_status": kernel_status, "warden_available": warden_available}
    # request_ids the stub will acknowledge as existing (B11 contract fidelity:
    # GET on an unknown id must 404, matching the real AgentGuard service)
    known_investigations: set[str] = {"inv-stub-0001", "inv-stub-graph-0002"}

    @app.get("/v1/system/health")
    def health() -> dict:
        return {"status": "ok", "service": "agentguard", "version": "1.1.0rc1"}

    @app.get("/v1/system/readiness")
    def readiness() -> dict:
        return {
            "schema_version": "1.0",
            "checks": [
                {"schema_version": "1.0", "name": "agentguard_api", "status": "available",
                 "source": "agentguard:self", "blockers": [], "diagnostics": {}},
                {"schema_version": "1.0", "name": "warden_connectivity", "status": "available",
                 "source": "warden:diagnostics", "blockers": [], "diagnostics": {}},
                {"schema_version": "1.0", "name": "contract_source", "status": "unknown",
                 "source": "warden:diagnostics", "blockers": ["NO_THREAT_CONTRACTS"], "diagnostics": {}},
                {"schema_version": "1.0", "name": "agent_runtime", "status": "blocked",
                 "source": "agentguard:self", "blockers": ["COMPONENT_UNAVAILABLE:agent.runtime"],
                 "diagnostics": {}},
            ],
        }

    @app.get("/v1/investigations/options")
    def investigation_options() -> dict:
        return {
            "schema_version": "1.0",
            "available": False,
            "error_code": None,
            "modes": [
                {"schema_version": "1.0", "mode": "observation", "plan_creation": "blocked",
                 "run_execution": "unavailable", "submittable": False,
                 "blockers": ["NO_THREAT_CONTRACTS", "COMPONENT_UNAVAILABLE:agent.runtime"], "note": ""},
                {"schema_version": "1.0", "mode": "detection", "plan_creation": "blocked",
                 "run_execution": "unavailable", "submittable": False,
                 "blockers": ["NO_THREAT_CONTRACTS"], "note": ""},
            ],
        }

    @app.get("/v1/investigations/{request_id}/timeline")
    def investigation_timeline(request_id: str) -> dict:
        if request_id not in known_investigations:
            raise HTTPException(status_code=404,
                                detail={"error": "WORKFLOW_NOT_FOUND", "message": "unknown workflow"})
        return {
            "request_id": request_id,
            "events": [
                {"event_type": "workflow_created", "at": datetime.now(UTC).isoformat()},
                {"event_type": "plan_submitted", "at": datetime.now(UTC).isoformat(),
                 "message": "plan submitted to WARDEN"},
            ],
        }

    @app.get("/v1/reports")
    def list_reports(limit: int = 50, offset: int = 0) -> dict:
        items = [{
            "run_id": "run-stub-0001", "experiment_id": "exp-stub-0001",
            "scenario_id": "scenario-stub", "status": "completed",
            "backend_mode": "synthetic", "created_at": datetime.now(UTC).isoformat(),
        }]
        return {"schema_version": "1.0", "items": items, "count": len(items),
                "offset": offset, "limit": limit, "next_offset": None}

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

    @app.get("/v1/investigations/{request_id}/interaction-graph")
    def interaction_graph(request_id: str) -> dict:
        """C1 contract: the response self-describes availability. The stub can
        serve an empty (honest) graph or a small populated one depending on the
        workflow id, mirroring both real upstream states."""
        if request_id not in known_investigations:
            raise HTTPException(status_code=404,
                                detail={"error": "NOT_FOUND", "message": "unknown workflow"})
        if request_id == "inv-stub-graph-0002":
            return {
                "schema_version": "1.0",
                "request_id": request_id,
                "available": True,
                "data_status": "available",
                "source": "warden_message_metadata",
                "run_id": "run-stub-0002",
                "scenario_id": "scenario-stub",
                "nodes": [
                    {"node_id": "agent-a", "node_type": "agent"},
                    {"node_id": "tool-1", "node_type": "tool"},
                    {"node_id": "agent-b", "node_type": "agent"},
                ],
                "edges": [
                    {"source": "agent-a", "target": "tool-1", "event_type": "tool_call",
                     "message_id": "msg-0001", "evidence_refs": ["ev-stub-000000000001"]},
                    {"source": "tool-1", "target": "agent-b", "event_type": "tool_result",
                     "message_id": "msg-0002", "evidence_refs": []},
                ],
                "candidate_paths": [{"nodes": ["agent-a", "tool-1", "agent-b"], "score": 0.42}],
                "limitations": ["Stub graph: synthetic edges from message metadata."],
            }
        return {
            "schema_version": "1.0",
            "request_id": request_id,
            "available": False,
            "data_status": "unavailable",
            "source": "none",
            "run_id": None,
            "scenario_id": "scenario-stub",
            "nodes": [],
            "edges": [],
            "candidate_paths": [],
            "limitations": [
                "GRAPH_SOURCE_UNAVAILABLE: no authorized message-level metadata is recorded "
                "for this workflow; no edges were constructed."
            ],
        }

    @app.get("/v1/experiments")
    def list_experiments_index(limit: int = 50, offset: int = 0) -> dict:
        items = [
            {
                "schema_version": "1.0",
                "experiment_id": "exp-stub-0001",
                "run_id": "run-stub-0001",
                "scenario_id": "scenario-stub",
                "execution_status": "completed",
                "raw_status": "completed",
                "data_source": "synthetic_report",
                "evidence_level": "synthetic",
                "metrics_available": False,
            },
            {
                "schema_version": "1.0",
                "experiment_id": "exp-stub-0002",
                "run_id": "run-stub-0002",
                "scenario_id": "scenario-stub",
                "execution_status": "completed",
                "raw_status": "completed",
                "data_source": "synthetic_report",
                "evidence_level": "synthetic",
                "metrics_available": True,
            },
        ]
        return {"schema_version": "1.0", "items": items, "count": len(items),
                "offset": offset, "limit": limit, "next_offset": None}

    @app.post("/v1/experiments/compare")
    def compare_experiments(body: dict) -> dict:
        run_ids = body.get("run_ids") or []
        return {
            "schema_version": "1.0",
            "run_ids": run_ids,
            "comparison": {"note": "Stub comparison; metrics are synthetic."},
        }

    @app.get("/v1/runs/{run_id}/timeline")
    def run_timeline(run_id: str) -> dict:
        if run_id != "run-stub-0001":
            raise HTTPException(status_code=404, detail="run_id not found")
        return {
            "run_id": run_id,
            "events": [
                {"event_type": "plan_submitted", "at": datetime.now(UTC).isoformat(),
                 "message": "plan submitted to WARDEN"},
                {"event_type": "run_started", "at": datetime.now(UTC).isoformat()},
            ],
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

    if strategy_evaluations_available:
        evaluation = {
            "schema_version": "1.0",
            "comparison_id": "comparison-contract-001",
            "base_request_ids": ["inv-stub-0001"],
            "strategies": ["risk_score"],
            "repetitions": 1,
            "data_partition": "test",
            "runs": [{
                "schema_version": "1.0",
                "experiment_id": "exp-evaluation-001",
                "run_label": "risk_score-1",
                "strategy": "risk_score",
                "repetition": 1,
                "base_request_id": "inv-stub-0001",
                "seed": None,
                "budget": {"max_rounds": 3, "max_model_calls": 5, "max_elapsed_seconds": 30},
                "execution_status": "completed",
                "stop_reason": None,
                "rounds_executed": 2,
                "steps_to_first_evidence": None,
                "effective_action_ratio": None,
                "blocked_ratio": None,
                "unsupported_ratio": None,
                "redundant_action_count": 0,
                "evidence_refs_collected": 0,
                "hypotheses_raised": 0,
                "model_calls_used": 0,
                "elapsed_seconds": 1.25,
                "strategy_degraded": False,
                "loop_report_artifact_id": None,
                "limitations": ["Contract fixture only; no live evaluation was run."],
                "source_commit": None,
            }],
            "aggregates": [{
                "schema_version": "1.0",
                "strategy": "risk_score",
                "repetitions": 1,
                "completed_runs": 1,
                "blocked_runs": 0,
                "mean_rounds": 2.0,
                "mean_steps_to_first_evidence": None,
                "mean_effective_action_ratio": None,
                "mean_redundant_actions": None,
                "mean_evidence_refs": None,
                "mean_elapsed_seconds": 1.25,
                "degradation_rate": 0.0,
                "notes": [],
            }],
            "risk_identification_metrics": None,
            "defense_effectiveness_metrics": None,
            "limitations": ["Contract fixture only; no live evaluation was run."],
            "source_commit": None,
            "executed_at": "2026-10-25T00:00:00+00:00",
            "report_artifact_id": "artifact-evaluation-001",
        }

        @app.get("/v1/research/strategy-evaluations")
        def list_strategy_evaluations(
            data_partition: str | None = None, limit: int = 50, offset: int = 0,
        ) -> dict:
            entries = [{
                "evaluation_id": "eval-strategy-001",
                "comparison_id": evaluation["comparison_id"],
                "report_artifact_id": evaluation["report_artifact_id"],
                "data_partition": evaluation["data_partition"],
                "source_commit": evaluation["source_commit"],
                "executed_at": evaluation["executed_at"],
                "status": "available",
            }]
            if data_partition and data_partition != evaluation["data_partition"]:
                entries = []
            page = entries[offset:offset + limit]
            return {"schema_version": "1.0", "items": page, "count": len(page),
                    "offset": offset, "limit": limit}

        @app.get("/v1/research/strategy-evaluations/{evaluation_id}")
        def get_strategy_evaluation(evaluation_id: str) -> dict:
            if evaluation_id == "eval-artifact-missing":
                raise HTTPException(status_code=410,
                                    detail={"error": "EVALUATION_ARTIFACT_UNAVAILABLE"})
            if evaluation_id != "eval-strategy-001":
                raise HTTPException(status_code=404, detail={"error": "EVALUATION_NOT_FOUND"})
            return evaluation

    if investigation_loop_report_available:
        report_decision = {
            "decision_id": "decision-report-001",
            "round_index": 1,
            "phase": "COMPLETED",
            "strategy": "risk_score",
            "candidate_actions": ["read_evidence"],
            "selected_action_id": "read_evidence",
            "selection_reason": "合同 Stub 中的实际选择原因。",
            "evidence_refs": ["ev-report-001"],
            "evidence_refs_before": [],
            "evidence_refs_after": ["ev-report-001"],
            "new_evidence_count": 1,
            "cost_estimate": None,
            "actual_cost": None,
            "remaining_budget": 2,
            "result_status": "completed",
            "new_evidence": True,
            "stop_reason": "BUDGET_EXHAUSTED",
        }

        @app.get("/v1/investigations/{request_id}/risk-analysis")
        def report_risk_analysis(request_id: str) -> dict:
            text = ("风险分析中的中文长文本。" * 200)[:2048] if report_long_text else "观测到可疑工具调用。"
            findings = []
            for index in range(24 if report_long_text else 1):
                findings.append({
                    "finding_id": f"finding-report-{index + 1:03d}",
                    "investigation_id": request_id,
                    "risk_type": "tool_use_pattern_candidate",
                    "detection_method": "tool_use_pattern_candidate",
                    "description": text,
                    "target_ref": "tool-1",
                    "supporting_evidence_refs": ["ev-support-001"],
                    "contradicting_evidence_refs": ["ev-contradict-001"],
                    "confidence": None,
                    "status": "candidate",
                    "evidence_level": "observational",
                    "verification_status": "unverified",
                    "severity": "medium",
                })
            return {
                "schema_version": "1.0",
                "investigation_id": request_id,
                "run_id": "run-stub-0001",
                "available": True,
                "findings": findings,
                "hypotheses": [{
                    "hypothesis_id": "hypothesis-report-001",
                    "investigation_id": request_id,
                    "finding_id": "finding-report-001",
                    "statement": "工具调用模式可能需要进一步核验。",
                    "expected_effect": "更多证据可能改变风险判断。",
                    "supporting_evidence": ["ev-support-001"],
                    "contradicting_evidence": ["ev-contradict-001"],
                    "next_check": "read_evidence",
                    "required_capabilities": [],
                    "intervention_supported": False,
                    "stop_condition": "证据不足时停止推断。",
                    "status": "proposed",
                }],
                "data_source": "warden_observation",
                "evidence_level": "observational",
                "limitations": ["该 Stub 不提供真实 WARDEN 或模型运行。"],
            }

        @app.get("/v1/investigation-loops")
        def report_list_loops(base_request_id: str, limit: int = 20, offset: int = 0) -> dict:
            items = []
            if base_request_id == "inv-stub-0001":
                items = [{
                    "loop_id": "loop-stub-001",
                    "base_request_id": base_request_id,
                    "phase": "STOPPED",
                    "strategy": "risk_score",
                    "rounds_executed": 1,
                    "stop_reason": "BUDGET_EXHAUSTED",
                }]
            elif e2e_isolation_loops and base_request_id == "inv-stub-graph-0002":
                items = [{
                    "loop_id": "loop-stub-002",
                    "base_request_id": base_request_id,
                    "phase": "STOPPED",
                    "strategy": "risk_score",
                    "rounds_executed": 1,
                    "stop_reason": "BUDGET_EXHAUSTED",
                }]
            return {"schema_version": "1.0", "items": items, "count": len(items),
                    "limit": limit, "offset": offset}

        @app.get("/v1/investigation-loops/{loop_id}")
        def report_get_loop(loop_id: str) -> dict:
            phase = "BLOCKED" if "blocked" in loop_id else "FAILED" if "failed" in loop_id else "STOPPED"
            base_request_id = (
                "inv-stub-graph-0002"
                if e2e_isolation_loops and loop_id == "loop-stub-002"
                else "inv-stub-0001"
            )
            return {
                "schema_version": "1.0",
                "loop_id": loop_id,
                "base_request_id": base_request_id,
                "phase": phase,
                "strategy": "risk_score",
                "stop_reason": "UPSTREAM_UNAVAILABLE" if phase == "FAILED" else "BUDGET_EXHAUSTED",
                "degradation": None,
                "metrics": {"rounds_executed": 1, "elapsed_seconds": 1.5,
                            "model_calls_used": 0, "steps_to_first_evidence": None},
                "limitations": ["调查 Loop 来源于确定性合同 Stub。"],
            }

        @app.get("/v1/investigation-loops/{loop_id}/decisions")
        def report_loop_decisions(loop_id: str) -> dict:
            items = [] if "blocked" in loop_id or "failed" in loop_id else [report_decision]
            return {"schema_version": "1.0", "loop_id": loop_id, "items": items,
                    "count": len(items), "limitations": []}

        @app.get("/v1/investigation-loops/{loop_id}/evidence-changes")
        def report_loop_evidence_changes(loop_id: str) -> dict:
            items = [] if report_empty_evidence or "blocked" in loop_id or "failed" in loop_id else [report_decision]
            return {"schema_version": "1.0", "loop_id": loop_id, "items": items,
                    "count": len(items), "limitations": []}

        @app.get("/v1/investigation-loops/{loop_id}/budget")
        def report_loop_budget(loop_id: str) -> dict:
            return {
                "schema_version": "1.0",
                "loop_id": loop_id,
                "budget": {"max_actions": 3, "max_seconds": 60, "max_model_calls": 5},
                "metrics": {"rounds_executed": 1, "elapsed_seconds": 1.5,
                            "model_calls_used": 0, "steps_to_first_evidence": None},
                "remaining": {"actions_left": 2, "seconds_left": 58.5, "model_calls_left": 5},
            }

    return app
