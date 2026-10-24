"""AgentGuard-QWB-App BFF entry point.

The BFF (Backend for Frontend) owns: application state, server-side credentials,
AgentGuard API calls, response transformation, and audit. It never re-implements
AgentGuard investigation/evidence/experience/defense algorithms.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.integrations.agentguard_client import AgentGuardClient, AgentGuardError
from app.services.demo_service import DemoService
from app.services.status_service import APP_NAME, APP_VERSION

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _resolve_fixtures_dir(configured: str):
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "demo" / "fixtures"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.agentguard_client = AgentGuardClient(settings)
    fixtures_dir = _resolve_fixtures_dir(settings.demo_fixtures_dir)
    app.state.demo_service = DemoService(fixtures_dir)
    logger.info("BFF started; upstream AgentGuard fixed at %s", settings.agentguard_base_url)
    logger.info("Demo fixtures loaded from %s", fixtures_dir)
    try:
        yield
    finally:
        app.state.agentguard_client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AgentGuard-QWB-App BFF",
        version=APP_VERSION,
        description=(
            "Backend-for-frontend for the AgentGuard security audit application platform. "
            "Talks to AgentGuard through its public API only."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def api_health() -> dict[str, str]:
        return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}

    @app.exception_handler(AgentGuardError)
    async def agentguard_error_handler(request: Request, exc: AgentGuardError) -> JSONResponse:
        # Error bodies never include request bodies or upstream credentials.
        detail = {"error": exc.code, "message": str(exc)}
        if exc.request_id:
            detail["request_id"] = exc.request_id
        return JSONResponse(status_code=502 if exc.status_code == 0 else exc.status_code, content={"detail": detail})

    app.include_router(api_router)
    return app


app = create_app()
