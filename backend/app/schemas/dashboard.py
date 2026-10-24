"""Dashboard response schemas (B2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.meta import MetaInfo
from app.schemas.system import SystemStatus


class InvestigationSummary(BaseModel):
    available: bool = False
    sample_based: bool = False
    total: int | None = None
    running: int | None = None
    completed: int | None = None
    blocked: int | None = None
    failed: int | None = None
    pending: int | None = None
    recent_request_id: str | None = None
    recent_status: str | None = None
    error: str | None = None


class EvidenceSummary(BaseModel):
    available: bool = False
    sample_based: bool = False
    by_level: dict[str, int] = Field(default_factory=dict)
    by_verification: dict[str, int] = Field(default_factory=dict)
    recent_count: int | None = None
    error: str | None = None


class PolicySummary(BaseModel):
    available: bool = False
    sample_based: bool = False
    pending_approval: int | None = None
    approved: int | None = None
    unsupported: int | None = None
    verified_historical: int | None = None
    error: str | None = None


class DependencyBlocker(BaseModel):
    id: str
    title: str
    impact: str
    status: str = "open"


class AuditCapability(BaseModel):
    name: str
    enabled: bool
    note: str | None = None


class DashboardResponse(BaseModel):
    system: SystemStatus
    investigation_summary: InvestigationSummary
    evidence_summary: EvidenceSummary
    policy_summary: PolicySummary
    dependency_blockers: list[DependencyBlocker] = Field(default_factory=list)
    audit_capabilities: list[AuditCapability] = Field(default_factory=list)
    meta: MetaInfo
