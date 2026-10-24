"""Application auth routes (login / logout / me)."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import CsrfProtectedUser
from app.core.security import issue_session, new_csrf_token
from app.services.auth_service import AppUser, find_user, verify_credentials

router = APIRouter()

# B16 login throttling: per-username sliding window, in-process (single-BFF
# deployment; a multi-replica deployment should move this to shared storage).
MAX_LOGIN_FAILURES = 10
FAILURE_WINDOW_SECONDS = 300.0
_login_failures: dict[str, list[float]] = {}


def _prune_failures(username: str, now: float) -> list[float]:
    recent = [stamp for stamp in _login_failures.get(username, [])
              if now - stamp < FAILURE_WINDOW_SECONDS]
    if recent:
        _login_failures[username] = recent
    else:
        _login_failures.pop(username, None)
    return recent


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
    now = time.monotonic()
    recent_failures = _prune_failures(body.username, now)
    if len(recent_failures) >= MAX_LOGIN_FAILURES:
        # Audited (username only - never the password) and rate limited.
        request.app.state.audit_service.record(
            actor=body.username, role=None, action="auth.login.rate_limited",
            target=body.username, detail=f"failures={len(recent_failures)} window={FAILURE_WINDOW_SECONDS}s")
        raise HTTPException(
            status_code=429,
            detail={"error": "TOO_MANY_ATTEMPTS",
                    "message": "登录失败次数过多，请 5 分钟后重试"})
    user = verify_credentials(settings, body.username, body.password)
    if user is None:
        _login_failures.setdefault(body.username, []).append(now)
        request.app.state.audit_service.record(
            actor=body.username, role=None, action="auth.login.failed",
            target=body.username, detail="invalid credentials")
        # Never reveal whether the username exists.
        raise HTTPException(status_code=401, detail={"error": "INVALID_CREDENTIALS", "message": "用户名或密码错误"})
    _login_failures.pop(body.username, None)
    request.app.state.audit_service.record(
        actor=user.username, role=user.role, action="auth.login.success", target=user.username)
    response = _json_response(_me_payload(settings, user))
    csrf = new_csrf_token(settings)
    response.set_cookie(
        settings.session_cookie_name,
        issue_session(settings, user.username),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf,
        max_age=settings.session_max_age_seconds,
        httponly=False,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
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
        return _me_payload(settings, find_user(settings, username))
    return _me_payload(settings, None)
