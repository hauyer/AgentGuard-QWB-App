"""Application audit route (B8, pagination + persistence in B9)."""

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
    offset: int = Query(default=0, ge=0),
    actor: str | None = Query(default=None, min_length=1, max_length=128),
    action: str | None = Query(default=None, min_length=1, max_length=64),
) -> dict:
    items, total = request.app.state.audit_service.query(
        limit=limit, offset=offset, actor=actor, action=action
    )
    return {
        "count": len(items),
        "total": total,
        "offset": offset,
        "limit": limit,
        "persisted": request.app.state.audit_service.persisted,
        "items": items,
    }
