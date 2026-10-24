"""Application audit (B8, persisted in B9).

Business-operation audit for BFF mutations (create investigation, defense
preview, ...). When DATABASE_URL is configured every event is written to the
app_audit_events table (Alembic 0001) - queries paginate over the database and
survive service restarts. Without a database (local development only) the same
interface degrades to a bounded in-memory buffer, and the audit API reports
persisted=false so operators can tell the difference.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.config import Settings
from app.core.db import open_session
from app.models.app import AppAuditEvent

logger = logging.getLogger(__name__)

MAX_EVENTS = 200
MAX_DETAIL_CHARS = 4000


class AuditService:
    def __init__(self, settings: Settings | None = None, *, capacity: int = MAX_EVENTS) -> None:
        self._settings = settings
        self._events: list[dict] = []
        self._capacity = capacity

    def bind(self, settings: Settings) -> None:
        """Attach settings (called from the app lifespan after state is built)."""
        self._settings = settings

    @property
    def persisted(self) -> bool:
        return bool(self._settings and self._settings.database_url)

    def record(
        self,
        *,
        actor: str,
        role: str | None,
        action: str,
        target: str | None,
        detail: str | None = None,
        project_id: int | None = None,
    ) -> None:
        now = datetime.now(UTC)
        if self._settings is not None:
            session = open_session(self._settings)
            if session is not None:
                with session:
                    session.add(
                        AppAuditEvent(
                            actor=actor[:128],
                            role=role,
                            action=action[:64],
                            target=target[:128] if target else None,
                            project_id=project_id,
                            # Bound the row size; never log credentials here.
                            detail=detail[:MAX_DETAIL_CHARS] if detail else None,
                            created_at=now,
                        )
                    )
                    session.commit()
                logger.info("audit action=%s actor=%s target=%s (persisted)", action, actor, target)
                return
        event = {
            "actor": actor,
            "role": role,
            "action": action,
            "target": target,
            "project_id": project_id,
            "detail": detail,
            "at": now.isoformat(),
        }
        self._events.append(event)
        if len(self._events) > self._capacity:
            self._events = self._events[-self._capacity :]
        logger.info("audit action=%s actor=%s target=%s (memory only)", action, actor, target)

    def query(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        actor: str | None = None,
        action: str | None = None,
        project_id: int | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> tuple[list[dict], int]:
        """Return (items newest-first, total_matching)."""
        if self._settings is not None:
            session = open_session(self._settings)
            if session is not None:
                with session:
                    conditions = []
                    if actor:
                        conditions.append(AppAuditEvent.actor == actor)
                    if action:
                        conditions.append(AppAuditEvent.action == action)
                    if project_id is not None:
                        conditions.append(AppAuditEvent.project_id == project_id)
                    for field, value in (("since", since), ("until", until)):
                        if value:
                            try:
                                moment = datetime.fromisoformat(value)
                            except ValueError as exc:
                                raise ValueError(f"audit {field} must be an ISO-8601 timestamp") from exc
                            conditions.append(
                                AppAuditEvent.created_at >= moment if field == "since"
                                else AppAuditEvent.created_at <= moment)
                    total = session.scalar(
                        select(func.count()).select_from(AppAuditEvent).where(*conditions)
                    )
                    rows = session.scalars(
                        select(AppAuditEvent)
                        .where(*conditions)
                        .order_by(AppAuditEvent.created_at.desc(), AppAuditEvent.id.desc())
                        .limit(limit)
                        .offset(offset)
                    ).all()
                    items = [
                        {
                            "id": row.id,
                            "actor": row.actor,
                            "role": row.role,
                            "action": row.action,
                            "target": row.target,
                            "project_id": row.project_id,
                            "detail": row.detail,
                            "at": row.created_at.isoformat() if row.created_at else None,
                        }
                        for row in rows
                    ]
                return items, int(total or 0)
        filtered = self._events
        if actor:
            filtered = [event for event in filtered if event["actor"] == actor]
        if action:
            filtered = [event for event in filtered if event["action"] == action]
        if project_id is not None:
            filtered = [event for event in filtered if event.get("project_id") == project_id]
        total = len(filtered)
        window = list(reversed(filtered))[: limit + offset]
        return window[offset : offset + limit], total
