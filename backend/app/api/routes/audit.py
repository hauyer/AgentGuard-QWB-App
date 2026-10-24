"""Application audit route (B8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_role

router = APIRouter()

Operator = Annotated[object, Depends(require_role("operator"))]


@router.get("/audit/events")
def audit_events(
    request: Request,
    _user: Operator,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    events = request.app.state.audit_service.recent(limit=limit)
    return {"count": len(events), "items": events}
