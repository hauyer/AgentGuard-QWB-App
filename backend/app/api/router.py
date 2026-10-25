"""BFF API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    audit,
    auth,
    dashboard,
    demo,
    evidence,
    experiments,
    findings,
    graph,
    investigations,
    loop_creation,
    projects,
    strategy_evaluations,
    system,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router, tags=["system"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(investigations.router, tags=["investigations"])
api_router.include_router(loop_creation.router, tags=["investigations"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(evidence.router, tags=["evidence"])
api_router.include_router(findings.router, tags=["findings"])
api_router.include_router(experiments.router, tags=["experiments"])
api_router.include_router(strategy_evaluations.router, tags=["research"])
api_router.include_router(demo.router, tags=["demo"])
api_router.include_router(audit.router, tags=["audit"])
api_router.include_router(auth.router, tags=["auth"])
