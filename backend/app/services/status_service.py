"""System status aggregation for the BFF.

Rule: AgentGuard health does NOT imply WARDEN or model runtime availability.
Each layer is probed through its own endpoint and reported separately. When an
upstream probe fails, the response carries an explicit error and the feature is
marked unavailable - never a fabricated default.
"""

from __future__ import annotations

import logging

from app.core.data_mode import effective_data_mode
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.schemas.system import (
    AgentGuardCapabilities,
    AgentGuardHealth,
    AgentGuardStatus,
    ErrorInfo,
    FeatureAvailability,
    SystemStatus,
    WardenStatusSummary,
)

logger = logging.getLogger(__name__)

APP_NAME = "agentguard-qwb-app"
APP_VERSION = "0.1.0"

# feature name -> whether it depends on more than AgentGuard reachability
_FEATURES: dict[str, str] = {
    "system.status": "BFF reads AgentGuard health and capabilities",
    "investigations.list": "GET /v1/investigations",
    "investigations.create": "POST /v1/investigations (requires WARDEN configured)",
    "evidence.view": "GET /v1/evidence/investigations/{request_id}",
    "defense.preview": "POST /v1/defense-policies/{request_id}/preview",
    "defense.execute": "defense execution is unsupported until AgentGuard exposes a verified external executor",
    "reports.read": "GET /v1/reports/{run_id}",
    "experiences.read": "GET /v1/experiences",
    "audit.events.read": "GET /v1/system/audit-events (operator token)",
    "interaction.graph": "message-level graph API is not yet exposed by AgentGuard public API",
}


def _capabilities_from(payload: dict) -> AgentGuardCapabilities:
    return AgentGuardCapabilities(
        provider_id=payload.get("provider_id"),
        provider_version=payload.get("provider_version"),
        backend_mode=payload.get("backend_mode"),
        capabilities=payload.get("capabilities") or {},
        supported_target_types=payload.get("supported_target_types") or [],
        supported_operations=payload.get("supported_operations") or [],
        limitations=payload.get("limitations") or [],
    )


def _warden_from(payload: dict) -> WardenStatusSummary:
    return WardenStatusSummary(
        status=str(payload.get("status", "unknown")),
        kernel=payload.get("kernel"),
        base_url=payload.get("base_url"),
        error_code=payload.get("error_code"),
        reason=payload.get("reason"),
        health=payload.get("health"),
        authoritative_for=payload.get("authoritative_for") or [],
    )


def build_system_status(client: AgentGuardClient, *, data_mode_override: str | None = None) -> SystemStatus:
    agentguard_status: AgentGuardStatus
    capabilities: AgentGuardCapabilities | None = None
    warden = WardenStatusSummary(status="unknown")

    try:
        health_payload = client.health()
    except AgentGuardError as exc:
        logger.warning("AgentGuard health probe failed: %s [%s]", exc.code, exc.request_id)
        features = [
            FeatureAvailability(name=name, available=False, reason="AgentGuard unreachable")
            for name in _FEATURES
        ]
        return SystemStatus(
            app={"name": APP_NAME, "version": APP_VERSION, "status": "ok"},
            data_mode=effective_data_mode(data_mode_override, agentguard_available=False),
            agentguard=AgentGuardStatus(
                reachable=False,
                error=ErrorInfo(code=exc.code, message=str(exc), request_id=exc.request_id),
            ),
            warden=WardenStatusSummary(
                status="unavailable",
                reason="AgentGuard unreachable; WARDEN status cannot be probed",
            ),
            features=features,
            unavailable_features=features,
        )

    agentguard_status = AgentGuardStatus(
        reachable=True,
        health=AgentGuardHealth(**{
            "status": health_payload.get("status", "unknown"),
            "service": health_payload.get("service"),
            "version": health_payload.get("version"),
        }),
    )

    # Capabilities: best effort - failure degrades the manifest, not the whole status.
    try:
        capabilities = _capabilities_from(client.capabilities())
        agentguard_status.capabilities = capabilities
    except AgentGuardError as exc:
        logger.warning("AgentGuard capabilities probe failed: %s", exc.code)
        agentguard_status.error = ErrorInfo(code=exc.code, message=str(exc), request_id=exc.request_id)

    # WARDEN status: must be probed independently; health alone never implies it.
    try:
        warden = _warden_from(client.kernel_status())
    except AgentGuardError as exc:
        logger.warning("AgentGuard kernel status probe failed: %s", exc.code)
        warden = WardenStatusSummary(
            status="unavailable",
            error_code=exc.code,
            reason=str(exc),
        )

    warden_available = warden.status == "available"
    data_mode = effective_data_mode(data_mode_override, agentguard_available=True)

    features: list[FeatureAvailability] = []
    for name, _description in _FEATURES.items():
        if name == "system.status":
            available = True
            reason = None
        elif name == "investigations.create":
            available = warden_available
            reason = None if warden_available else "WARDEN is not available (kernel status != available)"
        elif name == "defense.execute":
            available = False
            reason = "external defense executor is not verified; unsupported until AgentGuard exposes it"
        elif name == "interaction.graph":
            available = False
            reason = "message-level interaction graph API is not yet exposed by AgentGuard public API"
        elif name == "audit.events.read":
            available = True
            reason = (
                "requires a configured operator token"
                if not client._settings.agentguard_operator_api_token
                else None
            )
        else:
            available = True
            reason = None
        features.append(FeatureAvailability(name=name, available=available, reason=reason))

    unavailable = [feature for feature in features if not feature.available]
    return SystemStatus(
        app={"name": APP_NAME, "version": APP_VERSION, "status": "ok"},
        data_mode=data_mode,
        agentguard=agentguard_status,
        warden=warden,
        capabilities=capabilities,
        features=features,
        unavailable_features=unavailable,
    )
