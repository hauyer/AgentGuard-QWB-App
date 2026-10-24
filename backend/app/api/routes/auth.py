"""Application auth routes (login / logout / me)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import CsrfProtectedUser
from app.core.security import issue_session, new_csrf_token
from app.services.auth_service import AppUser, verify_credentials

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def _me_payload(settings, user: AppUser | None) -> dict:
    return {
        "authenticated": user is not None,
        "auth_enabled": settings.auth_enabled,
        "user": user.to_public() if user else None,
        "message": None if user else ("认证未启用：本地开发模式" if not settings.auth_enabled else "未登录"),
    }


def _json_response(payload: dict, status_code: int = 200) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False),
        media_type="application/json",
        status_code=status_code,
    )


@router.post("/auth/login")
def login(request: Request, body: LoginRequest) -> Response:
    settings = request.app.state.settings
    if not settings.auth_enabled:
        return _json_response(_me_payload(settings, None))
    user = verify_credentials(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail={"error": "INVALID_CREDENTIALS", "message": "用户名或密码错误"})
    response = _json_response(_me_payload(settings, user))
    csrf = new_csrf_token(settings)
    response.set_cookie(
        settings.session_cookie_name,
        issue_session(settings, user.username),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    response.set_cookie(settings.csrf_cookie_name, csrf, httponly=False, samesite="lax", secure=False, path="/")
    return response


@router.post("/auth/logout")
def logout(request: Request, _user: CsrfProtectedUser) -> Response:
    settings = request.app.state.settings
    response = _json_response(_me_payload(settings, None))
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return response


@router.get("/auth/me")
def me(request: Request) -> dict:
    settings = request.app.state.settings
    if not settings.auth_enabled:
        from app.services.auth_service import local_dev_user

        return _me_payload(settings, local_dev_user(settings))
    from app.core.security import verify_session

    session = request.cookies.get(settings.session_cookie_name)
    username = verify_session(settings, session)
    if username:
        from app.services.auth_service import DEMO_USERS

        return _me_payload(settings, DEMO_USERS.get(username))
    return _me_payload(settings, None)
