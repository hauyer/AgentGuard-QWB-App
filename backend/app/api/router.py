"""BFF API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import dashboard, system

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router, tags=["system"])
api_router.include_router(dashboard.router, tags=["dashboard"])
