"""Application configuration for the AgentGuard-QWB-App BFF.

The BFF is the only component allowed to talk to AgentGuard. The upstream base
URL is fixed server-side; the frontend can never influence it (SSRF guard).
"""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server-side configuration. Values come from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- AgentGuard upstream (fixed server-side) ---
    agentguard_base_url: str = "http://127.0.0.1:8000"
    agentguard_api_token: str | None = None
    agentguard_operator_api_token: str | None = None
    agentguard_api_timeout: float = 15.0

    # --- BFF application ---
    app_host: str = "127.0.0.1"
    app_port: int = 8001
    app_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    app_data_mode: str = ""
    database_url: str | None = None
    demo_fixtures_dir: str = ""

    # --- application auth (B8) ---
    # auth_enabled=false grants an implicit local admin session for development
    # only; production must set AUTH_ENABLED=true and a strong APP_SECRET_KEY.
    auth_enabled: bool = False
    app_secret_key: str = ""
    session_cookie_name: str = "qwb_session"
    csrf_cookie_name: str = "qwb_csrf"
    session_max_age_seconds: int = 8 * 60 * 60
    # Set SESSION_COOKIE_SECURE=true when serving over HTTPS (reverse proxy).
    # The flag is off by default so local HTTP development works out of the box.
    session_cookie_secure: bool = False

    @field_validator("agentguard_base_url")
    @classmethod
    def validate_agentguard_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("AGENTGUARD_BASE_URL contains an invalid port") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError(
                "AGENTGUARD_BASE_URL must be an HTTP(S) origin without credentials, path, query, or fragment"
            )
        return value.rstrip("/") or value

    @field_validator("agentguard_api_timeout")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if not 0 < value <= 120:
            raise ValueError("AGENTGUARD_API_TIMEOUT must be in the range (0, 120]")
        return value

    @field_validator("app_cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        for origin in origins:
            if origin == "*":
                raise ValueError("APP_CORS_ORIGINS must not contain a wildcard origin")
        return ",".join(origins)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
