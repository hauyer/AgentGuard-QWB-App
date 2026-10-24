"""Provenance metadata attached to every BFF business response.

meta.data_mode is always present; fixture fields appear only when the response
was served from the offline demo fixtures, so the UI can label replay data and
never mistake it for a live AgentGuard response.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DataModeValue = Literal["live", "recorded", "synthetic", "unavailable"]


class MetaInfo(BaseModel):
    data_mode: DataModeValue
    fixture_id: str | None = None
    source: str | None = None
    agentguard_version: str | None = None
    agentguard_commit: str | None = None
    collected_at: str | None = None
    sanitized: bool | None = None
    not_provable: list[str] = Field(default_factory=list)


def live_meta() -> MetaInfo:
    return MetaInfo(data_mode="live")


def fixture_meta(entry: dict) -> MetaInfo:
    return MetaInfo(
        data_mode=entry.get("data_mode") or "synthetic",
        fixture_id=entry.get("fixture_id"),
        source=entry.get("source"),
        agentguard_version=entry.get("agentguard_version"),
        agentguard_commit=entry.get("agentguard_commit"),
        collected_at=entry.get("collected_at"),
        sanitized=entry.get("sanitized"),
        not_provable=entry.get("not_provable") or [],
    )
