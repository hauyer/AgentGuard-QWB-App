"""BFF API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import auth, dashboard, investigations, system

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router, tags=["system"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(investigations.router, tags=["investigations"])
api_router.include_router(auth.router, tags=["auth"])
