"""Route dependencies: current user, role enforcement and CSRF."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.security import verify_csrf, verify_session
from app.services.auth_service import AppUser, find_user, has_role, local_dev_user

USER_KEY = "qwb_current_user"


def _settings(request: Request):
    return request.app.state.settings


def get_current_user(request: Request) -> AppUser:
    settings = _settings(request)
    if not settings.auth_enabled:
        return local_dev_user(settings)
    session = request.cookies.get(settings.session_cookie_name)
    username = verify_session(settings, session)
    if username is None:
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "请先登录"})
    user = find_user(settings, username)
    if user is None:
        # Session signature is valid but the account is gone or deactivated.
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "会话无效"})
    return user


def require_role(required: str):
    def _dependency(request: Request, user: Annotated[AppUser, Depends(get_current_user)]) -> AppUser:
        if not has_role(required, user.role):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "PERMISSION_DENIED",
                    "message": f"当前角色 {user.role} 无权执行该操作（需要 {required} 及以上）",
                },
            )
        return user

    return _dependency


def require_csrf(request: Request, user: Annotated[AppUser, Depends(get_current_user)]) -> AppUser:
    """Double-submit CSRF check for mutating requests. Skipped when auth is
    disabled (dev-only implicit session has no cookie to protect)."""
    settings = _settings(request)
    if not settings.auth_enabled:
        return user
    cookie = request.cookies.get(settings.csrf_cookie_name)
    header = request.headers.get("x-csrf-token")
    if not verify_csrf(settings, cookie, header):
        raise HTTPException(
            status_code=403,
            detail={"error": "CSRF_MISMATCH", "message": "CSRF 校验失败，请刷新页面后重试"},
        )
    return user


def require_role_csrf(required: str):
    """Combined role + CSRF gate for mutating routes (e.g. create investigation)."""

    def _dependency(request: Request, user: Annotated[AppUser, Depends(get_current_user)]) -> AppUser:
        user = require_csrf(request, user)
        if not has_role(required, user.role):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "PERMISSION_DENIED",
                    "message": f"当前角色 {user.role} 无权执行该操作（需要 {required} 及以上）",
                },
            )
        return user

    return _dependency


CurrentUserDep = Annotated[AppUser, Depends(get_current_user)]
CsrfProtectedUser = Annotated[AppUser, Depends(require_csrf)]
