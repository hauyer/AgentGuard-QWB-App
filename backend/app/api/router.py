"""BFF API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import auth, dashboard, evidence, graph, investigations, system

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router, tags=["system"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(investigations.router, tags=["investigations"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(evidence.router, tags=["evidence"])
api_router.include_router(auth.router, tags=["auth"])
