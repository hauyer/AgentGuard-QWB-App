"""Application audit (B8).

Business-operation audit for BFF mutations (create investigation, defense
preview, ...). The in-memory bounded buffer keeps the BFF usable without a
database; when DATABASE_URL is configured the same events should be persisted
to app_audit_events (see app/models/app.py + migration 0001).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

MAX_EVENTS = 200


class AuditService:
    def __init__(self, capacity: int = MAX_EVENTS) -> None:
        self._events: list[dict] = []
        self._capacity = capacity

    def record(
        self,
        *,
        actor: str,
        role: str | None,
        action: str,
        target: str | None,
        detail: str | None = None,
    ) -> None:
        event = {
            "actor": actor,
            "role": role,
            "action": action,
            "target": target,
            "detail": detail,
            "at": datetime.now(UTC).isoformat(),
        }
        self._events.append(event)
        if len(self._events) > self._capacity:
            self._events = self._events[-self._capacity :]
        logger.info("audit action=%s actor=%s target=%s", action, actor, target)

    def recent(self, *, limit: int = 100) -> list[dict]:
        return list(reversed(self._events[-limit:]))
