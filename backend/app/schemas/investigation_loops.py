"""Application request schema matching AgentGuard's I-stage loop contract."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateInvestigationLoopRequest(BaseModel):
    """Strict AgentGuard create payload plus a BFF correlation token.

    Ownership fields such as ``project_id`` and ``verified_source`` are
    deliberately absent and unknown request fields are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    submission_id: UUID
    strategy: Literal["fixed_order", "risk_score", "information_value", "experience", "llm"] = (
        "information_value"
    )
    max_actions: int = Field(default=8, ge=1, le=100)
    max_seconds: float = Field(default=300.0, gt=0.0, le=3600.0)
    max_model_calls: int = Field(default=4, ge=0, le=64)
    no_new_evidence_rounds: int = Field(default=2, ge=1, le=10)
    data_partition: Literal["training", "validation", "test", "held_out_family"] = "held_out_family"
    authorization_ref: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def check_budget_envelope(self) -> CreateInvestigationLoopRequest:
        if self.max_seconds > 600 and self.max_actions > 20:
            raise ValueError(
                "max_seconds > 600 requires max_actions <= 20 under the AgentGuard budget envelope"
            )
        return self


class ReconcileInvestigationLoopSubmissionRequest(BaseModel):
    """Explicit operator choice for resolving an ambiguous upstream POST."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["resume", "associate_loop", "confirm_not_created"] = "resume"
    loop_id: str | None = Field(default=None, min_length=1, max_length=256)
    operator_note: str | None = Field(default=None, min_length=10, max_length=500)

    @model_validator(mode="after")
    def validate_action_fields(self) -> ReconcileInvestigationLoopSubmissionRequest:
        if self.action == "associate_loop" and not self.loop_id:
            raise ValueError("loop_id is required when action=associate_loop")
        if self.action != "associate_loop" and self.loop_id is not None:
            raise ValueError("loop_id is only allowed when action=associate_loop")
        if self.action == "resume" and self.operator_note is not None:
            raise ValueError("operator_note is not allowed when action=resume")
        if self.action != "resume" and not self.operator_note:
            raise ValueError("operator_note is required for manual reconciliation")
        return self
