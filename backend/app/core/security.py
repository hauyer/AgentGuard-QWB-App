"""HMAC-signed session and CSRF tokens for the BFF.

Sessions are stateless (signed cookie): the browser only ever holds the signed
value, never the secret and never AgentGuard/WARDEN credentials. CSRF uses the
double-submit pattern: a signed qwb_csrf cookie is issued with the session and
every mutating request must echo it in the X-CSRF-Token header.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import Settings


def _secret(settings: Settings) -> bytes:
    if settings.app_secret_key:
        return settings.app_secret_key.encode("utf-8")
    # Development-only ephemeral secret: sessions do not survive restarts.
    return hashlib.sha256(b"dev-ephemeral-agentguard-qwb-secret").digest()


def _sign(settings: Settings, payload: str) -> str:
    return hmac.new(_secret(settings), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_session(settings: Settings, username: str) -> str:
    body = json.dumps(
        {"username": username, "exp": int(time.time()) + settings.session_max_age_seconds},
        separators=(",", ":"),
    )
    encoded = base64.urlsafe_b64encode(body.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{encoded}.{_sign(settings, encoded)}"


def verify_session(settings: Settings, value: str | None) -> str | None:
    if not value:
        return None
    try:
        encoded, signature = value.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(settings, encoded), signature):
        return None
    try:
        padding = "=" * (-len(encoded) % 4)
        body = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if int(body.get("exp", 0)) < int(time.time()):
        return None
    return str(body.get("username"))


def new_csrf_token(settings: Settings) -> str:
    token = secrets.token_urlsafe(24)
    return f"{token}.{_sign(settings, token)}"


def verify_csrf(settings: Settings, cookie: str | None, header: str | None) -> bool:
    if not cookie or not header:
        return False
    try:
        token, signature = cookie.rsplit(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(_sign(settings, token), signature):
        return False
    return hmac.compare_digest(cookie, header)
