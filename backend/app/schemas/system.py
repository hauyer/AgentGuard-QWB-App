"""Response schemas for the application status API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentGuardHealth(BaseModel):
    status: str
    service: str | None = None
    version: str | None = None


class AgentGuardCapabilities(BaseModel):
    provider_id: str | None = None
    provider_version: str | None = None
    backend_mode: str | None = None
    capabilities: dict[str, bool] = Field(default_factory=dict)
    supported_target_types: list[str] = Field(default_factory=list)
    supported_operations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ErrorInfo(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class AgentGuardStatus(BaseModel):
    reachable: bool
    health: AgentGuardHealth | None = None
    capabilities: AgentGuardCapabilities | None = None
    error: ErrorInfo | None = None


class WardenStatusSummary(BaseModel):
    status: str = "unknown"
    kernel: str | None = None
    base_url: str | None = None
    error_code: str | None = None
    reason: str | None = None
    health: dict[str, Any] | None = None
    authoritative_for: list[str] = Field(default_factory=list)


class FeatureAvailability(BaseModel):
    name: str
    available: bool
    reason: str | None = None


class SystemStatus(BaseModel):
    app: dict[str, str]
    data_mode: Literal["live", "recorded", "synthetic", "unavailable"]
    agentguard: AgentGuardStatus
    warden: WardenStatusSummary
    capabilities: AgentGuardCapabilities | None = None
    features: list[FeatureAvailability] = Field(default_factory=list)
    unavailable_features: list[FeatureAvailability] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
