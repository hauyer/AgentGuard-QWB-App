"""Data source modes.

LIVE        real responses fetched from AgentGuard right now
RECORDED    sanitised historical recordings that keep source provenance
SYNTHETIC   explicitly generated teaching/demo data
UNAVAILABLE no data could be obtained

A mode is never inferred from a healthy AgentGuard alone: WARDEN and model
runtime availability are reported separately by their own endpoints.
"""

from __future__ import annotations

from enum import StrEnum


class DataMode(StrEnum):
    LIVE = "live"
    RECORDED = "recorded"
    SYNTHETIC = "synthetic"
    UNAVAILABLE = "unavailable"


def effective_data_mode(configured: str | None, agentguard_available: bool) -> DataMode:
    """Resolve the effective mode.

    An explicit configured override (recorded/synthetic) wins for demo purposes,
    but an override is only honoured when it is a recognised mode; an unknown
    override falls back to connectivity-derived mode. LIVE requires a reachable
    AgentGuard; nothing else may claim LIVE.
    """
    if configured:
        try:
            return DataMode(configured.strip().lower())
        except ValueError:
            pass
    return DataMode.LIVE if agentguard_available else DataMode.UNAVAILABLE
